"""Наполнить Qdrant-коллекцию `shadow_listings` известными листингами из датасета.

Каждый элемент: эмбеддинг текста (multilingual-e5, через core) + payload {category, label}.
label = "bad" для всех категорий кроме unknown (legit-контрпримеры). Сигнал
`similar_to_known_listing` срабатывает на близость к bad-листингам.

Запуск:
    python -m apps.digital_shadow.index_listings --data data/shadow/all.jsonl
"""

from __future__ import annotations

import argparse
import json

from apps.digital_shadow.similarity import SHADOW_COLLECTION
from backend.app.config import get_settings


def _load(path: str) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            text = d.get("text") or d.get("combined_text")
            cat = d.get("gold_category") or d.get("category")
            if text and cat:
                out.append({"text": text, "category": cat,
                            "label": "legit" if cat == "unknown" else "bad"})
    return out


def main() -> None:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams

    from core import similarity_service

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/shadow/all.jsonl")
    args = ap.parse_args()
    s = get_settings()

    recs = _load(args.data)
    if not recs:
        print("нет листингов для индексации (пустой/некорректный датасет)")
        return
    print(f"Загружено листингов: {len(recs)} (bad={sum(r['label']=='bad' for r in recs)})")
    vectors = [similarity_service.embed(r["text"]) for r in recs]

    client = QdrantClient(url=s.qdrant_url)
    if SHADOW_COLLECTION not in {c.name for c in client.get_collections().collections}:
        client.create_collection(
            SHADOW_COLLECTION,
            vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE))
    client.upsert(SHADOW_COLLECTION, points=[
        PointStruct(id=i, vector=v, payload=recs[i]) for i, v in enumerate(vectors)])
    print(f"Проиндексировано: {len(recs)} → коллекция '{SHADOW_COLLECTION}'")


if __name__ == "__main__":
    main()
