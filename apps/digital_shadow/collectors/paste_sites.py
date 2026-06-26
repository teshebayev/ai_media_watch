"""Paste/leak-коллектор: мониторинг paste-сайтов на утечки БД РК (pastebin-подобные, leak-форумы).

Тянет последние пасты по списку публичных фидов/URL, оставляет ТОЛЬКО релевантные —
с признаками слива базы РК (breach-лексика + KZ-привязка, см. leak_detector). Сырой текст
паст с реальными ПДн как есть не персистим — дальше по пайплайну ИИН/телефоны маскируются;
здесь фиксируем факт + источник (§0).

Тестируемость/офлайн: можно передать `fetch` (async callable url→text) — тогда без сети.
По умолчанию — httpx GET (публичные страницы, таймаут, лимит длины).
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator, Awaitable, Callable

from apps.digital_shadow.leak_detector import detect_leak_signals

from .base import Collector, RawItem
from .http_page import strip_html


def is_kz_leak_relevant(text: str) -> bool:
    """Релевантна ли паста: есть ли признаки слива/продажи базы РК (breach + KZ)."""
    return bool(detect_leak_signals(text))


class PasteSiteCollector(Collector):
    source_type = "paste"

    def __init__(self, feeds: list[str] | None = None, *,
                 fetch: Callable[[str], Awaitable[str | None]] | None = None,
                 timeout: float = 10.0, max_chars: int = 8000, kz_only: bool = True):
        self.feeds = feeds or []                 # URL последних паст / лент
        self._fetch = fetch                      # инъекция для офлайн-тестов
        self.timeout = timeout
        self.max_chars = max_chars
        self.kz_only = kz_only                   # оставлять только утечки БД РК

    async def _get(self, url: str) -> str | None:
        if self._fetch is not None:
            return await self._fetch(url)
        import httpx
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, follow_redirects=True,
                headers={"User-Agent": "DigitalShadow-OSINT/0.1"},
            ) as client:
                r = await client.get(url)
                r.raise_for_status()
                return strip_html(r.text)
        except Exception:  # noqa: BLE001 — недоступная паста пропускается
            return None

    async def collect(self, query: str | None = None) -> AsyncIterator[RawItem]:
        for url in self.feeds:
            text = await self._get(url)
            if not text:
                continue
            text = text[: self.max_chars]
            if self.kz_only and not is_kz_leak_relevant(text):
                continue                          # не про утечку БД РК → пропуск
            if query and query.lower() not in text.lower():
                continue
            yield RawItem(
                id="paste_" + hashlib.sha1(url.encode()).hexdigest()[:12],
                source_type=self.source_type, source_url=url, text=text,
            )
