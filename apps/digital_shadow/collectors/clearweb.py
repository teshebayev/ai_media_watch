"""Clearweb-коллектор: открытые форумы / барахолки / объявления / соцобъявления (httpx).

СКЕЛЕТ (TODO студенту/команде). Только публичные страницы, GET, таймаут, лимит, уважение
robots.txt; ПДн не сохранять (маски/хэши, §0). Реализовать парсинг конкретных площадок.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from .base import Collector, RawItem


class ClearwebCollector(Collector):
    source_type = "clearweb"

    def __init__(self, sources: list[str] | None = None, timeout: float = 10.0):
        # sources — список URL/шаблонов поиска по площадкам
        self.sources = sources or []
        self.timeout = timeout

    async def collect(self, query: str | None = None) -> AsyncIterator[RawItem]:
        # TODO: httpx.AsyncClient → GET по self.sources/query → извлечь объявления →
        #       yield RawItem(... source_type="clearweb", source_url=..., text=...)
        # Заглушка: пустой поток, чтобы пайплайн собирался без сети.
        return
        yield  # pragma: no cover
