"""Similarity Service: поиск похожих известных scam-кейсов в Qdrant.

Если ≥3 соседей с label=scam и score>0.8 → сигнал similar_to_known_scam.
Эмбеддинги — multilingual-e5 (ru/kz/en). Модель грузится лениво и переиспользуется.
Управляется флагом ENABLE_SIMILARITY.
"""

from __future__ import annotations

from functools import lru_cache

from qdrant_client import AsyncQdrantClient

from backend.app.config import get_settings

SCORE_THRESHOLD = 0.8
MIN_SCAM_NEIGHBORS = 3


@lru_cache
def _get_encoder():
    # Импортируем внутри функции: sentence-transformers тяжёлый, не нужен при выключенном флаге.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_settings().embedding_model)


def embed(text: str) -> list[float]:
    # e5 требует префикс "query: " для поисковых запросов.
    return _get_encoder().encode(f"query: {text}", normalize_embeddings=True).tolist()


async def search_similar(client: AsyncQdrantClient, text: str, limit: int = 5) -> list[dict]:
    s = get_settings()
    if not s.enable_similarity:
        return []
    # qdrant-client 1.12+: .search устарел → query_points (возвращает .points)
    resp = await client.query_points(
        collection_name=s.qdrant_collection,
        query=embed(text),
        limit=limit,
        with_payload=True,
    )
    return [{"score": p.score, "payload": p.payload} for p in resp.points]


def similarity_signal(neighbors: list[dict]) -> bool:
    scam = [
        n for n in neighbors
        if n["score"] > SCORE_THRESHOLD and (n.get("payload") or {}).get("label") == "scam"
    ]
    return len(scam) >= MIN_SCAM_NEIGHBORS
