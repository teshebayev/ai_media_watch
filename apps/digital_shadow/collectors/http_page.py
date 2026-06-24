"""HttpPageCollector — тянет видимый текст публичных страниц (форум/барахолка/объявление).

Только публичные GET, таймаут, лимит длины (§0). Для DarkNet/Tor — передать SOCKS-прокси
(`proxy="socks5h://127.0.0.1:9050"`); интерфейс не меняется. ПДн не сохраняем (маски/хэши).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import AsyncIterator

import httpx

from .base import Collector, RawItem

_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_STRIP_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(html: str) -> str:
    html = _TAG_RE.sub(" ", html)
    return _WS_RE.sub(" ", _STRIP_RE.sub(" ", html)).strip()


class HttpPageCollector(Collector):
    source_type = "clearweb"

    def __init__(self, urls: list[str], *, proxy: str | None = None, timeout: float = 10.0,
                 max_chars: int = 4000):
        self.urls = urls
        self.proxy = proxy            # socks5h://127.0.0.1:9050 → Tor (.onion)
        self.timeout = timeout
        self.max_chars = max_chars

    async def collect(self, query: str | None = None) -> AsyncIterator[RawItem]:
        async with httpx.AsyncClient(
            proxy=self.proxy, timeout=self.timeout, follow_redirects=True,
            headers={"User-Agent": "DigitalShadow-OSINT/0.1"},
        ) as client:
            for url in self.urls:
                try:
                    r = await client.get(url)
                    r.raise_for_status()
                    text = strip_html(r.text)[: self.max_chars]
                except Exception:  # noqa: BLE001 — недоступная страница пропускается
                    continue
                if not text or (query and query.lower() not in text.lower()):
                    continue
                src = "darknet" if ".onion" in url else self.source_type
                yield RawItem(
                    id="url_" + hashlib.sha1(url.encode()).hexdigest()[:12],
                    source_type=src, source_url=url, text=text,
                )
