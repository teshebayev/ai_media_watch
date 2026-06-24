"""FileCollector — оператор кладёт собранные вручную/экспортированные листинги в JSONL,
коллектор отдаёт их в пайплайн. Самый надёжный «реальный» путь: легально, без краулинга.

Формат строки (как ShadowItem; минимум — text): {"id","source_type","source_url","platform",
"language","title","text"}. Лишние поля (gold_*) игнорируются — можно скармливать те же
датасеты, что для eval.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from .base import Collector, RawItem


class FileCollector(Collector):
    source_type = "clearweb"

    def __init__(self, path: str):
        self.path = path

    async def collect(self, query: str | None = None) -> AsyncIterator[RawItem]:
        with open(self.path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                text = d.get("text") or d.get("combined_text") or ""
                if query and query.lower() not in text.lower():
                    continue
                yield RawItem(
                    id=str(d.get("id") or f"file_{i}"),
                    source_type=d.get("source_type", self.source_type),
                    source_url=d.get("source_url"),
                    platform=d.get("platform"),
                    title=d.get("title"),
                    text=text,
                    language=d.get("language", "ru"),
                )
