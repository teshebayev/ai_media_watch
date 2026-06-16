"""Индексация ai_media_watch_dataset.jsonl в Qdrant (план, этап 4).

Читает unified JSONL → эмбеддинг combined_text (multilingual-e5) → upsert в коллекцию
scam_cases. Payload = весь объект (label, fraud_type, risk_level, entities).
Запускать каждый раз, когда студенты доливают разметку.

Запуск (когда Qdrant поднят):
    python -m src.index_dataset data/processed/ai_media_watch_dataset.jsonl
"""

from __future__ import annotations

import json
import os
import sys


def main(dataset_path: str) -> None:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams
    from sentence_transformers import SentenceTransformer

    collection = os.getenv("QDRANT_COLLECTION", "scam_cases")
    model_name = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-base")
    dim = int(os.getenv("EMBEDDING_DIM", "768"))

    encoder = SentenceTransformer(model_name)
    client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))

    if collection not in {c.name for c in client.get_collections().collections}:
        client.create_collection(
            collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )

    points = []
    with open(dataset_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            text = rec.get("combined_text") or rec.get("transcript") or ""
            # e5: документы префиксуются "passage: "
            vec = encoder.encode(f"passage: {text}", normalize_embeddings=True).tolist()
            points.append(PointStruct(id=i, vector=vec, payload=rec))

    if points:
        client.upsert(collection, points=points)
    print(f"Проиндексировано точек: {len(points)} → коллекция '{collection}'")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
