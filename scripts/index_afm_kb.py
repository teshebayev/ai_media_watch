#!/usr/bin/env python3
"""Проиндексировать базу знаний AFM в Qdrant (гибридный поиск: dense e5 + sparse BM25).

Запуск (локально, Qdrant на хосте):
    QDRANT_URL=http://localhost:6333 .venv/bin/python scripts/index_afm_kb.py

По умолчанию пересоздаёт коллекцию (--recreate). Чтобы только досыпать: --no-recreate.
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend.app.clients.qdrant import make_qdrant_client  # noqa: E402
from backend.app.config import get_settings  # noqa: E402
from backend.app.services import knowledge as kb  # noqa: E402


async def main(recreate: bool) -> None:
    s = get_settings()
    client = make_qdrant_client()
    print(f"Qdrant: {s.qdrant_url} · коллекция: {s.kb_collection} · эмбеддер: {s.embedding_model}")
    n = await kb.index_cards(client, recreate=recreate)
    total = await kb.kb_count(client)
    await client.close()
    print(f"✓ Проиндексировано карточек: {n} (в коллекции всего: {total})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-recreate", dest="recreate", action="store_false", help="не пересоздавать коллекцию")
    ap.set_defaults(recreate=True)
    asyncio.run(main(ap.parse_args().recreate))
