"""Qdrant-клиент + ленивая инициализация коллекции scam_cases."""

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from backend.app.config import get_settings


def make_qdrant_client() -> AsyncQdrantClient:
    s = get_settings()
    return AsyncQdrantClient(url=s.qdrant_url)


async def ensure_collection(client: AsyncQdrantClient) -> None:
    s = get_settings()
    existing = {c.name for c in (await client.get_collections()).collections}
    if s.qdrant_collection not in existing:
        await client.create_collection(
            collection_name=s.qdrant_collection,
            vectors_config=VectorParams(size=s.embedding_dim, distance=Distance.COSINE),
        )
