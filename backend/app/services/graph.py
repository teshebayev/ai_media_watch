"""Graph Service: Shadow Graph в Neo4j (ТЗ §12).

MERGE узлов/связей после entity extraction + запрос повторяемости (graph_entity_reuse).
Телефоны/карты — только хэш/маска (ТЗ §0). Управляется флагом ENABLE_GRAPH.
"""

from __future__ import annotations

import logging

from neo4j import AsyncDriver

from backend.app.config import get_settings
from backend.app.schemas.models import Entities
from backend.app.services.entity_norm import normalize_entity_value, normalized_variants

logger = logging.getLogger(__name__)

# Источник = узел контента. Лейбл зависит от продукта: Media Watch → Video/Post/Call,
# Digital Shadow → ShadowItem. Берём из контролируемого списка (НЕ из пользовательского ввода —
# лейбл нельзя параметризовать в Cypher, поэтому подставляем строкой только из allowlist).
_SOURCE_LABELS = {"Video", "Post", "Call", "ShadowItem", "Source"}

# Повторяемость любой сущности среди источников ЛЮБОГО типа (Video/Post/Call/ShadowItem) —
# так находки Media Watch и Digital Shadow связываются по общим узлам (домен/кошелёк/telegram).
# Ключи узлов разные: Domain/TelegramUsername.name, PromoCode.code, Wallet.address.
# Значение нормализуется (entity_norm) → ищем по каноническим формам ($values).
REUSE_QUERY = """
MATCH (e) WHERE e.name IN $values OR e.code IN $values OR e.address IN $values
MATCH (e)<-[]-(s)
RETURN count(DISTINCT s) AS uses
"""


async def upsert_entities(
    driver: AsyncDriver, record_id: str, entities: Entities, *, source_label: str = "Video",
    node_props: dict | None = None,
) -> None:
    """Записать сущности записи в Shadow Graph. source_label — тип узла-источника
    (Media Watch: Video/Post/Call; Digital Shadow: ShadowItem). Кошельки и telegram —
    общие узлы → кросс-продуктовая связка.

    node_props — свойства узла-источника (напр. {"category","source_type"} для Shadow):
    хранятся на узле → кросс-КАТЕГОРИЙНЫЙ анализ (один кошелёк в наркотиках и дропах).
    Берём только скалярные значения (str/int/float/bool) — без вложенных структур в графе."""
    s = get_settings()
    if not s.enable_graph:
        return
    label = source_label if source_label in _SOURCE_LABELS else "Source"
    props = {k: v for k, v in (node_props or {}).items()
             if isinstance(v, (str, int, float, bool)) and v is not None}
    async with driver.session() as session:
        if props:
            # один MERGE узла-источника со свойствами; ниже MERGE'и сольются в него
            await session.run(
                f"MERGE (s:{label} {{id:$id}}) SET s += $props", id=record_id, props=props)
        for domain in entities.domains:
            await session.run(
                f"MERGE (s:{label} {{id:$id}}) MERGE (d:Domain {{name:$v}}) "
                "MERGE (s)-[:MENTIONS]->(d)",
                id=record_id, v=normalize_entity_value("domain", domain))
        for tg in entities.telegram_usernames:
            await session.run(
                f"MERGE (s:{label} {{id:$id}}) MERGE (t:TelegramUsername {{name:$v}}) "
                "MERGE (s)-[:MENTIONS]->(t)",
                id=record_id, v=normalize_entity_value("telegram", tg))
        for code in entities.promo_codes:
            await session.run(
                f"MERGE (s:{label} {{id:$id}}) MERGE (p:PromoCode {{code:$v}}) "
                "MERGE (s)-[:HAS_PROMO]->(p)",
                id=record_id, v=normalize_entity_value("promo", code))
        for wallet in entities.crypto_wallets:
            await session.run(
                f"MERGE (s:{label} {{id:$id}}) MERGE (w:Wallet {{address:$v}}) "
                "MERGE (s)-[:MENTIONS]->(w)",
                id=record_id, v=normalize_entity_value("wallet", wallet))


def _reuse_values(value: str, kind: str | None) -> list[str]:
    """Канонические формы значения для поиска узла. С известным kind — одна форма,
    иначе — все варианты (kind-агностично)."""
    return [normalize_entity_value(kind, value)] if kind else normalized_variants(value)


async def entity_reuse(driver: AsyncDriver, value: str, *, kind: str | None = None) -> int:
    s = get_settings()
    if not s.enable_graph:
        return 0
    async with driver.session() as session:
        result = await session.run(REUSE_QUERY, values=_reuse_values(value, kind))
        record = await result.single()
        return record["uses"] if record else 0


# --- Визуализация: подграф nodes/edges -------------------------------------

# Окрестность сущности: сама сущность ← источники, упоминающие её → их др. сущности.
# Значение нормализуется (entity_norm) → ищем по каноническим формам ($values).
NEIGHBORHOOD_QUERY = """
MATCH (e) WHERE e.name IN $values OR e.code IN $values OR e.address IN $values
MATCH (e)<-[r1]-(s)
OPTIONAL MATCH (s)-[r2]->(x) WHERE x <> e
RETURN e, s, x, r1, r2
LIMIT $limit
"""

# Overview: топ повторяемых сущностей и их источники (стартовый кластер для демо).
OVERVIEW_QUERY = """
MATCH (e) WHERE (e:Domain OR e:PromoCode OR e:TelegramUsername)
MATCH (e)<-[r]-(s)
WITH e, count(s) AS uses WHERE uses > 1
ORDER BY uses DESC LIMIT $entities
MATCH (e)<-[r]-(s)
RETURN e, s, r
LIMIT $limit
"""


def _node_key(node) -> str:
    props = dict(node)
    if "name" in props:
        return f"{props['name']}"
    if "code" in props:
        return f"{props['code']}"
    if "address" in props:          # кошельки идентифицируются адресом, а не name/code
        return f"{props['address']}"
    return f"{props.get('id', node.element_id)}"


def _node_dict(node) -> dict:
    labels = list(node.labels)
    props = dict(node)
    # порядок резолвинга подписи: name → code → address (кошельки) → id
    label_text = (props.get("name") or props.get("code")
                  or props.get("address") or props.get("id") or "?")
    return {
        "id": _node_key(node),
        "label": label_text,
        "type": labels[0] if labels else "Node",
        "fraud_type": props.get("fraud_type"),
        "risk_level": props.get("risk_level"),
    }


def _collect(records) -> dict:
    nodes: dict[str, dict] = {}
    edges: dict[tuple, dict] = {}

    def add_node(n):
        if n is not None:
            d = _node_dict(n)
            nodes.setdefault(d["id"], d)

    def add_edge(rel):
        if rel is None:
            return
        a, b = _node_key(rel.start_node), _node_key(rel.end_node)
        edges.setdefault((a, b, rel.type), {"from": a, "to": b, "label": rel.type})

    for rec in records:
        for key in ("e", "s", "x"):
            if key in rec.keys():
                add_node(rec.get(key))
        for key in ("r", "r1", "r2"):
            if key in rec.keys():
                add_edge(rec.get(key))
    return {"nodes": list(nodes.values()), "edges": list(edges.values())}


async def neighborhood(driver: AsyncDriver, value: str, limit: int = 150) -> dict:
    s = get_settings()
    if not s.enable_graph:
        return {"nodes": [], "edges": []}
    async with driver.session() as session:
        result = await session.run(
            NEIGHBORHOOD_QUERY, values=normalized_variants(value), limit=limit)
        records = [r async for r in result]
    return _collect(records)


async def overview(driver: AsyncDriver, entities: int = 8, limit: int = 200) -> dict:
    s = get_settings()
    if not s.enable_graph:
        return {"nodes": [], "edges": []}
    async with driver.session() as session:
        result = await session.run(OVERVIEW_QUERY, entities=entities, limit=limit)
        records = [r async for r in result]
    return _collect(records)


# Подграф конкретного типа источника (напр. ShadowItem): источники + ВСЕ их сущности
# (включая кошельки). В отличие от overview не отдаёт приоритет узлам с высокой
# повторяемостью → новые теневые листинги не теряются за доминирующими Media-узлами.
SOURCE_SUBGRAPH_QUERY = """
MATCH (s)-[r]->(e) WHERE $label IN labels(s)
RETURN s, e, r LIMIT $limit
"""


async def source_subgraph(driver: AsyncDriver, source_label: str, limit: int = 250) -> dict:
    """nodes/edges для всех источников заданного типа и их сущностей. source_label —
    из контролируемого allowlist (защита от инъекции лейбла)."""
    s = get_settings()
    if not s.enable_graph or source_label not in _SOURCE_LABELS:
        return {"nodes": [], "edges": []}
    async with driver.session() as session:
        result = await session.run(SOURCE_SUBGRAPH_QUERY, label=source_label, limit=limit)
        records = [r async for r in result]
    return _collect(records)


# --- Объяснимость связи: кратчайший путь между двумя сущностями ---------------
def _node_caption(node) -> str:
    """Короткая подпись узла для объяснения: 'Wallet bc1qxy…' / 'ShadowItem dn_drug_001'."""
    props = dict(node)
    label = list(node.labels)[0] if node.labels else "Node"
    val = props.get("name") or props.get("code") or props.get("address") or props.get("id") or "?"
    cat = props.get("category")
    tail = f" [{cat}]" if cat and cat != "unknown" else ""
    return f"{label} {val}{tail}"


def _explain_path(path) -> list[str]:
    """Человекочитаемая цепочка: почему A и B связаны (по шагам пути)."""
    nodes = list(path.nodes)
    if len(nodes) < 2:
        return []
    steps: list[str] = []
    sources = [n for n in nodes if set(n.labels) & _SOURCE_LABELS]
    if len(nodes) == 3 and sources:
        # A ← источник → B: общий источник упомянул обе сущности
        return [f"Обе сущности упоминаются в одном источнике: {_node_caption(sources[0])}"]
    for a, b in zip(nodes, nodes[1:], strict=False):
        a_src = bool(set(a.labels) & _SOURCE_LABELS)
        link = ("упоминает" if a_src else "упомянут(а) в")
        steps.append(f"{_node_caption(a)} → {link} → {_node_caption(b)}")
    return steps


async def explain_link(driver: AsyncDriver, a: str, b: str, *, max_hops: int = 5) -> dict:
    """Кратчайший путь между сущностями a и b в общем графе + объяснение «почему связаны».

    Возвращает {found, hops, explanation[], nodes[], edges[]}. Сущности матчатся по
    нормализованным формам (entity_norm). max_hops клампится (1..6) — int инлайнится в
    шаблон пути (параметр Cypher там не допускается; значение валидируется как целое)."""
    s = get_settings()
    if not s.enable_graph:
        return {"found": False, "explanation": [], "nodes": [], "edges": []}
    hops = max(1, min(int(max_hops), 6))
    query = (
        "MATCH (a) WHERE a.name IN $va OR a.code IN $va OR a.address IN $va "
        "MATCH (b) WHERE b.name IN $vb OR b.code IN $vb OR b.address IN $vb "
        "WITH a, b WHERE a <> b "
        f"MATCH p = shortestPath((a)-[*..{hops}]-(b)) "
        "RETURN p LIMIT 1"
    )
    async with driver.session() as session:
        result = await session.run(
            query, va=normalized_variants(a), vb=normalized_variants(b))
        rec = await result.single()
    if rec is None:
        return {"found": False, "explanation": [
            "Прямой связи в пределах заданного числа шагов не найдено."],
            "nodes": [], "edges": []}
    path = rec["p"]
    sub = _collect([{ "e": n } for n in path.nodes] +
                   [{ "r": r } for r in path.relationships])
    return {
        "found": True,
        "hops": len(list(path.relationships)),
        "explanation": _explain_path(path),
        "nodes": sub["nodes"],
        "edges": sub["edges"],
    }
