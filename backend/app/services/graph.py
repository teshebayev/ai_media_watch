"""Graph Service: Shadow Graph в Neo4j (ТЗ §12).

MERGE узлов/связей после entity extraction + запрос повторяемости (graph_entity_reuse).
Телефоны/карты — только хэш/маска (ТЗ §0). Управляется флагом ENABLE_GRAPH.
"""

from __future__ import annotations

from neo4j import AsyncDriver

from backend.app.config import get_settings
from backend.app.schemas.models import Entities

UPSERT_VIDEO_DOMAIN = """
MERGE (v:Video {id: $id})
MERGE (d:Domain {name: $domain})
MERGE (v)-[:MENTIONS]->(d)
"""

UPSERT_VIDEO_TELEGRAM = """
MERGE (v:Video {id: $id})
MERGE (t:TelegramUsername {name: $tg})
MERGE (v)-[:MENTIONS]->(t)
"""

UPSERT_VIDEO_PROMO = """
MERGE (v:Video {id: $id})
MERGE (p:PromoCode {code: $code})
MERGE (v)-[:HAS_PROMO]->(p)
"""

# Повторяемость домена (главная фича демо). Аналогично для telegram/promo.
# Повторяемость любой сущности (домен/telegram/промокод) среди источников
# любого типа (Video/Post/Call), а не только Video.
REUSE_QUERY = """
MATCH (e) WHERE e.name = $value OR e.code = $value
MATCH (e)<-[]-(s)
RETURN count(DISTINCT s) AS uses
"""


async def upsert_entities(driver: AsyncDriver, record_id: str, entities: Entities) -> None:
    s = get_settings()
    if not s.enable_graph:
        return
    async with driver.session() as session:
        for domain in entities.domains:
            await session.run(UPSERT_VIDEO_DOMAIN, id=record_id, domain=domain)
        for tg in entities.telegram_usernames:
            await session.run(UPSERT_VIDEO_TELEGRAM, id=record_id, tg=tg)
        for code in entities.promo_codes:
            await session.run(UPSERT_VIDEO_PROMO, id=record_id, code=code)


async def entity_reuse(driver: AsyncDriver, value: str) -> int:
    s = get_settings()
    if not s.enable_graph:
        return 0
    async with driver.session() as session:
        result = await session.run(REUSE_QUERY, value=value)
        record = await result.single()
        return record["uses"] if record else 0


# --- Визуализация: подграф nodes/edges -------------------------------------

# Окрестность сущности: сама сущность ← источники, упоминающие её → их др. сущности.
NEIGHBORHOOD_QUERY = """
MATCH (e) WHERE e.name = $value OR e.code = $value
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
    return f"{props.get('id', node.element_id)}"


def _node_dict(node) -> dict:
    labels = list(node.labels)
    props = dict(node)
    label_text = props.get("name") or props.get("code") or props.get("id") or "?"
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
        result = await session.run(NEIGHBORHOOD_QUERY, value=value, limit=limit)
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
