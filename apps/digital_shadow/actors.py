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
WITH e, collect(DISTINCT {sid: elementId(s), skind: labels(s)[0], scat: s.category}) AS srcs
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


def _real_category(scat) -> str | None:
    """Значимая шадоу-категория источника (для кросс-категорийного анализа):
    отбрасываем пустое/unknown — они не свидетельствуют о связи разных видов активности."""
    return scat if scat and scat != "unknown" else None


def _cluster_risk(*, sources: int, size: int, etypes: int, skinds: int,
                  ncats: int, cross_product: bool) -> int:
    """Риск кластера 0..100 (эвристика в стиле шадоу-весов: малые инкременты + клампы).

    Сеть дропов/кошельков опаснее, когда: широкий охват источников (sources), много
    скоординированной инфраструктуры (size), разнотипные индикаторы (кошелёк+домен+@ник →
    etypes), разные классы источников (skinds), а САМОЕ ТЯЖЁЛОЕ — общий индикатор связывает
    РАЗНЫЕ виды нелегальной активности (ncats: наркотики↔дропы↔утечки) и есть мост
    Media↔Shadow (cross_product).
    """
    score = 0
    score += min(30, 5 * max(0, sources - 1))     # охват источников
    score += min(18, 4 * max(0, size - 1))        # объём скоординированной инфраструктуры
    score += min(12, 6 * max(0, etypes - 1))      # разнотипность индикаторов
    score += min(8, 4 * max(0, skinds - 1))       # разнообразие классов источников
    score += min(25, 12 * max(0, ncats - 1))      # кросс-категорийность (главный сигнал сети)
    if cross_product:
        score += 15                               # мост контент↔тень
    return min(100, score)


def _build_clusters(edges: list[dict], *, max_clusters: int = 50) -> list[dict]:
    """Чистая агрегация двудольных рёбер в кластеры (union-find).

    edge: {entity, etype, sid, skind}. Узел сущности — ('E', etype, entity) (тип в ключе,
    чтобы промокод и домен с одинаковой строкой не схлопывались), источник — ('S', sid).
    Возвращает кластеры {entities, sources, kinds, cross_product, size, hub, risk},
    отсортированные по кросс-продуктовости, риску и размеру убыв.

    hub — «вожак» сети: сущность кластера с наибольшим числом источников (степень в
    двудольном графе). risk — агрегированный риск сети (_cluster_risk).
    """
    uf = _UnionFind()
    for e in edges:
        uf.union(("E", e["etype"], e["entity"]), ("S", e["sid"]))

    groups: dict = {}
    for e in edges:
        root = uf.find(("E", e["etype"], e["entity"]))
        g = groups.setdefault(
            root, {"entities": {}, "sources": set(), "kinds": set(), "etypes": set(),
                   "cats": set()})
        # для каждой сущности храним её источники → степень (для hub)
        g["entities"].setdefault((e["entity"], e["etype"]), set()).add(e["sid"])
        g["sources"].add(e["sid"])
        g["kinds"].add(e["skind"])
        g["etypes"].add(e["etype"])
        cat = _real_category(e.get("scat"))
        if cat:
            g["cats"].add(cat)

    clusters = []
    for g in groups.values():
        kinds = sorted(g["kinds"])
        cats = sorted(g["cats"])
        cross = ("ShadowItem" in kinds) and bool(_MEDIA & set(kinds))
        cross_category = len(cats) >= 2     # общий индикатор связывает ≥2 вида активности
        # hub — сущность с макс. числом источников; тай-брейк по (значение, тип) для детерминизма
        (hub_val, hub_type), hub_srcs = max(
            g["entities"].items(), key=lambda kv: (len(kv[1]), kv[0]))
        clusters.append({
            "entities": [{"value": v, "type": t} for (v, t) in sorted(g["entities"])],
            "sources": len(g["sources"]),
            "kinds": kinds,
            "categories": cats,
            "cross_product": cross,
            "cross_category": cross_category,
            "size": len(g["entities"]),
            "hub": {"value": hub_val, "type": hub_type, "sources": len(hub_srcs)},
            "risk": _cluster_risk(
                sources=len(g["sources"]), size=len(g["entities"]),
                etypes=len(g["etypes"]), skinds=len(g["kinds"]),
                ncats=len(cats), cross_product=cross),
        })
    # кросс-категорийные и кросс-продуктовые, рисковые и крупные — выше
    clusters.sort(
        key=lambda c: (c["cross_category"], c["cross_product"], c["risk"], c["size"],
                       c["sources"]), reverse=True)
    return clusters[:max_clusters]


# ── Скоринг акторов (риск отдельной сущности в сети) ─────────────────────────
# Степень в сети («с кем связан») и охват дают приоритет аналитику: какой именно
# кошелёк/домен/@ник — центральный узел, а не просто часто встречается.
def _actor_risk(*, uses: int, co_actors: int, skinds: int, ncats: int,
                cross_product: bool) -> int:
    """Риск актора 0..100. uses — охват (в скольких источниках); co_actors — степень
    (с сколькими др. сущностями делит источник = вложенность в сеть); skinds —
    разнообразие классов источников; ncats — в скольких РАЗНЫХ видах активности засветился
    (общий кошелёк в наркотиках и дропах = тяжелее); cross_product — мост Media↔Shadow."""
    score = 0
    score += min(35, 7 * max(0, uses - 1))        # охват / повторяемость
    score += min(22, 5 * co_actors)               # вложенность в сеть (степень)
    score += min(13, 5 * max(0, skinds - 1))      # разнообразие классов источников
    score += min(20, 10 * max(0, ncats - 1))      # кросс-категорийность
    if cross_product:
        score += 15                               # мост контент↔тень
    return min(100, score)


def _score_actors(edges: list[dict], *, limit: int = 20) -> list[dict]:
    """Чистый скоринг акторов по двудольным рёбрам {entity, etype, sid, skind}.

    Для каждой сущности считаем: источники (uses), классы источников (kinds),
    co_actors (число РАЗНЫХ др. сущностей, делящих с ней хотя бы один источник) и
    итоговый actor_risk. Сортировка по риску и охвату убыв."""
    # сущность → источники; источник → сущности (для co_actors)
    ent_srcs: dict = {}
    ent_kinds: dict = {}
    ent_cats: dict = {}
    src_ents: dict = {}
    for e in edges:
        key = (e["entity"], e["etype"])
        ent_srcs.setdefault(key, set()).add(e["sid"])
        ent_kinds.setdefault(key, set()).add(e["skind"])
        ent_cats.setdefault(key, set())
        cat = _real_category(e.get("scat"))
        if cat:
            ent_cats[key].add(cat)
        src_ents.setdefault(e["sid"], set()).add(key)

    out = []
    for key, srcs in ent_srcs.items():
        co: set = set()
        for sid in srcs:
            co |= src_ents.get(sid, set())
        co.discard(key)                            # себя не считаем
        kinds = sorted(ent_kinds[key])
        cats = sorted(ent_cats[key])
        cross = ("ShadowItem" in kinds) and bool(_MEDIA & set(kinds))
        value, etype = key
        out.append({
            "entity": value,
            "type": etype,
            "uses": len(srcs),
            "co_actors": len(co),
            "kinds": kinds,
            "categories": cats,
            "cross_product": cross,
            "cross_category": len(cats) >= 2,
            "actor_risk": _actor_risk(
                uses=len(srcs), co_actors=len(co), skinds=len(kinds),
                ncats=len(cats), cross_product=cross),
        })
    out.sort(key=lambda a: (a["actor_risk"], a["uses"], a["co_actors"]), reverse=True)
    return out[:limit]


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
                        "sid": src["sid"], "skind": src["skind"],
                        "scat": src.get("scat")})
    except Exception as e:  # noqa: BLE001 — граф недоступен → пустой результат
        logger.warning("actor_clusters: граф недоступен: %s", e)
        return []
    return _build_clusters(edges, max_clusters=max_clusters)


async def _fetch_edges(driver, *, min_uses: int, limit: int) -> list[dict]:
    """Двудольные рёбра «сущность ← источник» из общего графа (та же выборка, что у
    кластеров: top-N сущностей по повторяемости, затем все их источники)."""
    edges: list[dict] = []
    async with driver.session() as session:
        result = await session.run(
            CLUSTER_EDGES_QUERY, entity_labels=_ENTITY_LABELS, min_uses=min_uses, limit=limit)
        async for rec in result:
            for src in rec["srcs"]:
                edges.append({
                    "entity": rec["entity"], "etype": rec["etype"],
                    "sid": src["sid"], "skind": src["skind"]})
    return edges


async def actor_scores(driver, *, limit: int = 20, min_uses: int = 2,
                       scan: int = 500) -> list[dict]:
    """Скоринг акторов из общего графа: риск отдельной сущности по охвату + степени в сети.

    scan — сколько top-сущностей просканировать для расчёта связей (детерминированно по uses);
    limit — сколько вернуть после скоринга. Граф недоступен → []."""
    if driver is None:
        return []
    min_uses = max(1, int(min_uses))
    scan = max(1, min(int(scan), _MAX_ENTITIES))
    limit = max(1, int(limit))
    try:
        edges = await _fetch_edges(driver, min_uses=min_uses, limit=scan)
    except Exception as e:  # noqa: BLE001 — граф недоступен → пустой результат
        logger.warning("actor_scores: граф недоступен: %s", e)
        return []
    return _score_actors(edges, limit=limit)
