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
    import torch
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams
    from sentence_transformers import SentenceTransformer

    collection = os.getenv("QDRANT_COLLECTION", "scam_cases")
    model_name = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-base")
    dim = int(os.getenv("EMBEDDING_DIM", "768"))
    enc_batch = int(os.getenv("INDEX_ENCODE_BATCH", "256"))
    # Qdrant ограничивает JSON-payload одного upsert ~32 МБ; кириллица в ensure_ascii
    # раздувается (~19 КБ/точку с полным combined_text), поэтому батч держим небольшим.
    upsert_batch = int(os.getenv("INDEX_UPSERT_BATCH", "800"))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    encoder = SentenceTransformer(model_name, device=device)
    client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"), timeout=120)

    if collection not in {c.name for c in client.get_collections().collections}:
        client.create_collection(
            collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )

    # читаем все записи в память (только текст+payload, без векторов)
    recs, texts = [], []
    with open(dataset_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            recs.append(rec)
            # e5: документы префиксуются "passage: "
            texts.append(f"passage: {rec.get('combined_text') or rec.get('transcript') or ''}")

    print(f"Кодирование {len(texts)} текстов (device={device}, batch={enc_batch})…")
    vectors = encoder.encode(
        texts, batch_size=enc_batch, normalize_embeddings=True, show_progress_bar=True
    )

    total = 0
    for start in range(0, len(recs), upsert_batch):
        chunk = [
            PointStruct(id=start + j, vector=vectors[start + j].tolist(), payload=rec)
            for j, rec in enumerate(recs[start:start + upsert_batch])
        ]
        client.upsert(collection, points=chunk)
        total += len(chunk)
        print(f"  upsert {total}/{len(recs)}", flush=True)
    print(f"Проиндексировано точек: {total} → коллекция '{collection}'")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
