"""Paste/leak-коллектор: мониторинг paste-сайтов на утечки БД РК (pastebin-подобные, leak-форумы).

СКЕЛЕТ (TODO). Ищем признаки слива баз РК (см. leak_detector). Сырой текст → RawItem.
ПДн из дампов НЕ сохраняем: фиксируем факт/метаданные + маскированные индикаторы (§0).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from .base import Collector, RawItem


class PasteSiteCollector(Collector):
    source_type = "paste"

    def __init__(self, feeds: list[str] | None = None):
        self.feeds = feeds or []   # RSS/ленты последних паст

    async def collect(self, query: str | None = None) -> AsyncIterator[RawItem]:
        # TODO: тянуть последние пасты по self.feeds → фильтр по KZ-индикаторам → yield RawItem
        return
        yield  # pragma: no cover
