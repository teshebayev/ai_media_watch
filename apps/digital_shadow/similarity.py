"""Семантическое сходство с известными «плохими» листингами (Qdrant, Фаза 3).

Переиспользует эмбеддер общего движка (core.similarity_service) и отдельную коллекцию
`shadow_listings` (наполняется scripts/index_listings... → apps.digital_shadow.index_listings).
Новый элемент → nearest-neighbor; если рядом известный bad с cos-sim ≥ порога → сигнал
`similar_to_known_listing`. Ловит перефразировки, которые правила/лексикон пропускают.

Best-effort: нет Qdrant/эмбеддера/коллекции → тихо пропускаем (с warning).
"""

from __future__ import annotations

import logging

from backend.app.config import get_settings

logger = logging.getLogger(__name__)

SHADOW_COLLECTION = "shadow_listings"
SIM_THRESHOLD = 0.80


def _is_similar(neighbors: list[dict], threshold: float = SIM_THRESHOLD) -> bool:
    """Чистая проверка: есть ли сосед-‘bad’ с score ≥ порога. (для теста без сети)."""
    return any(
        n.get("score", 0.0) >= threshold and (n.get("payload") or {}).get("label") == "bad"
        for n in neighbors
    )


async def similar_listing(client, text: str, *, threshold: float = SIM_THRESHOLD,
                          limit: int = 5) -> tuple[bool, float]:
    """(matched, top_score). Best-effort: клиент/эмбеддер/коллекция недоступны → (False, 0.0)."""
    if client is None or not get_settings().enable_similarity or not (text or "").strip():
        return (False, 0.0)
    try:
        from core import similarity_service

        resp = await client.query_points(
            collection_name=SHADOW_COLLECTION, query=similarity_service.embed(text),
            limit=limit, with_payload=True)
        neighbors = [{"score": p.score, "payload": p.payload} for p in resp.points]
    except Exception as e:  # noqa: BLE001 — нет Qdrant/коллекции/модели → пропускаем
        logger.warning("similar_listing недоступно: %s", e)
        return (False, 0.0)
    top = max((n["score"] for n in neighbors), default=0.0)
    return (_is_similar(neighbors, threshold), round(top, 3))
