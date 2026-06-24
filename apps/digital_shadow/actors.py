"""Профили акторов: топ повторяющихся сущностей (кошельки/домены/@ник/промокоды) в графе.

«Актор» = сущность, всплывающая в нескольких источниках. Помечаем кросс-продуктовые
(сущность есть и у Media :Video/:Post/:Call, и у :ShadowItem) — главный OSINT-сигнал.
Источник данных — общий Neo4j (driver из core/backend).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_MEDIA = {"Video", "Post", "Call"}
# Акторы — только реальные сущности, НЕ узлы риск-сигналов/прочего.
_ENTITY_LABELS = ["Domain", "Wallet", "TelegramUsername", "PromoCode"]

TOP_ACTORS_QUERY = """
MATCH (e)<-[]-(s)
WHERE any(l IN labels(e) WHERE l IN $entity_labels)
WITH e, collect(DISTINCT labels(s)[0]) AS kinds, count(DISTINCT s) AS uses
WHERE uses >= $min_uses
RETURN coalesce(e.name, e.code, e.address) AS entity,
       labels(e)[0] AS type, kinds, uses
ORDER BY uses DESC LIMIT $limit
"""


async def top_actors(driver, *, limit: int = 20, min_uses: int = 2) -> list[dict]:
    """Вернуть топ сущностей по повторяемости. cross_product=True, если сущность связывает
    контент (Media) и теневые источники (Shadow)."""
    if driver is None:
        return []
    out: list[dict] = []
    async with driver.session() as session:
        result = await session.run(
            TOP_ACTORS_QUERY, min_uses=min_uses, limit=limit, entity_labels=_ENTITY_LABELS)
        async for rec in result:
            kinds = rec["kinds"] or []
            out.append({
                "entity": rec["entity"],
                "type": rec["type"],
                "kinds": kinds,
                "uses": rec["uses"],
                "cross_product": ("ShadowItem" in kinds) and bool(_MEDIA & set(kinds)),
            })
    return out


async def cross_product(driver, *, limit: int = 50) -> list[dict]:
    """Только кросс-продуктовые сущности (мост Media ↔ Shadow)."""
    actors = await top_actors(driver, limit=200, min_uses=2)
    return [a for a in actors if a["cross_product"]][:limit]


# ── Кластеры акторов (связные компоненты по со-упоминанию) ───────────────────
# Двудольные рёбра «сущность ← источник» для сущностей с повторяемостью ≥ min_uses.
# Кластер = связная компонента: источники, делящие ≥1 сущность, и их сущности.
# Bounded по ЧИСЛУ сущностей (top-N по повторяемости, детерминированно ORDER BY uses),
# затем для каждой берём ВСЕ её источники (collect) — рёбра компоненты не теряются.
CLUSTER_EDGES_QUERY = """
MATCH (e)<-[]-(s)
WHERE any(l IN labels(e) WHERE l IN $entity_labels)
WITH e, count(DISTINCT s) AS uses
WHERE uses >= $min_uses
WITH e, uses ORDER BY uses DESC LIMIT $limit
MATCH (e)<-[]-(s)
WITH e, collect(DISTINCT {sid: elementId(s), skind: labels(s)[0]}) AS srcs
RETURN coalesce(e.name, e.code, e.address) AS entity, labels(e)[0] AS etype, srcs
"""


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _build_clusters(edges: list[dict], *, max_clusters: int = 50) -> list[dict]:
    """Чистая агрегация двудольных рёбер в кластеры (union-find).

    edge: {entity, etype, sid, skind}. Узел сущности — ('E', etype, entity) (тип в ключе,
    чтобы промокод и домен с одинаковой строкой не схлопывались), источник — ('S', sid).
    Возвращает кластеры {entities, sources, kinds, cross_product, size}, отсортированные по
    кросс-продуктовости и размеру убыв.
    """
    uf = _UnionFind()
    for e in edges:
        uf.union(("E", e["etype"], e["entity"]), ("S", e["sid"]))

    groups: dict = {}
    for e in edges:
        root = uf.find(("E", e["etype"], e["entity"]))
        g = groups.setdefault(root, {"entities": {}, "sources": set(), "kinds": set()})
        g["entities"][(e["entity"], e["etype"])] = None  # ключ — (значение, тип)
        g["sources"].add(e["sid"])
        g["kinds"].add(e["skind"])

    clusters = []
    for g in groups.values():
        kinds = sorted(g["kinds"])
        clusters.append({
            "entities": [{"value": v, "type": t} for (v, t) in sorted(g["entities"])],
            "sources": len(g["sources"]),
            "kinds": kinds,
            "cross_product": ("ShadowItem" in kinds) and bool(_MEDIA & set(kinds)),
            "size": len(g["entities"]),
        })
    # кросс-продуктовые и крупные — выше
    clusters.sort(key=lambda c: (c["cross_product"], c["size"], c["sources"]), reverse=True)
    return clusters[:max_clusters]


# Серверные пределы (защита от DoS даже при обходе валидации на уровне API).
_MAX_ENTITIES = 5000
_MAX_CLUSTERS = 500


async def actor_clusters(driver, *, limit: int = 500, min_uses: int = 2,
                         max_clusters: int = 50) -> list[dict]:
    """Кластеры связанных акторов из общего графа. Сущности bound'ятся top-N
    (детерминированно по uses), все их источники собираются → рёбра компоненты не
    теряются. Компоненты считаем в Python (_build_clusters)."""
    if driver is None:
        return []
    # клампим вход независимо от API-слоя
    limit = max(1, min(int(limit), _MAX_ENTITIES))
    min_uses = max(1, int(min_uses))
    max_clusters = max(1, min(int(max_clusters), _MAX_CLUSTERS))
    edges: list[dict] = []
    try:
        async with driver.session() as session:
            result = await session.run(
                CLUSTER_EDGES_QUERY, entity_labels=_ENTITY_LABELS,
                min_uses=min_uses, limit=limit)
            async for rec in result:
                for src in rec["srcs"]:
                    edges.append({
                        "entity": rec["entity"], "etype": rec["etype"],
                        "sid": src["sid"], "skind": src["skind"]})
    except Exception as e:  # noqa: BLE001 — граф недоступен → пустой результат
        logger.warning("actor_clusters: граф недоступен: %s", e)
        return []
    return _build_clusters(edges, max_clusters=max_clusters)
