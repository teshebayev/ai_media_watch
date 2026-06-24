"""Профили акторов: топ повторяющихся сущностей (кошельки/домены/@ник/промокоды) в графе.

«Актор» = сущность, всплывающая в нескольких источниках. Помечаем кросс-продуктовые
(сущность есть и у Media :Video/:Post/:Call, и у :ShadowItem) — главный OSINT-сигнал.
Источник данных — общий Neo4j (driver из core/backend).
"""

from __future__ import annotations

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
