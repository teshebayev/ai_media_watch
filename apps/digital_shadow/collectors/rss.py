"""RssCollector — мониторинг публичных RSS/Atom-лент (новости/форумы/paste-агрегаторы).

Легально и без тяжёлых зависимостей: httpx + stdlib xml. Каждый item ленты → RawItem
(title + summary). Полезно для непрерывного мониторинга по фидам.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator

import httpx

from .base import Collector, RawItem

_STRIP_RE = re.compile(r"<[^>]+>")


def _text(el) -> str:
    return _STRIP_RE.sub(" ", (el.text or "")).strip() if el is not None else ""


def parse_feed(xml_text: str) -> list[dict]:
    """Достать (title, summary, link) из RSS 2.0 или Atom (по localname, без неймспейс-магии)."""
    items: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1].lower()

    for node in root.iter():
        if local(node.tag) in ("item", "entry"):
            fields = {local(c.tag): c for c in node}
            title = _text(fields.get("title"))
            summary = _text(
                fields.get("description") or fields.get("summary") or fields.get("content"))
            link_el = fields.get("link")
            link = (link_el.get("href") if link_el is not None and link_el.get("href")
                    else _text(link_el))
            items.append({"title": title, "summary": summary, "link": link})
    return items


class RssCollector(Collector):
    source_type = "clearweb"

    def __init__(self, feeds: list[str], *, timeout: float = 10.0):
        self.feeds = feeds
        self.timeout = timeout

    async def collect(self, query: str | None = None) -> AsyncIterator[RawItem]:
        async with httpx.AsyncClient(
            timeout=self.timeout, follow_redirects=True,
            headers={"User-Agent": "DigitalShadow-OSINT/0.1"},
        ) as client:
            for feed in self.feeds:
                try:
                    r = await client.get(feed)
                    r.raise_for_status()
                    entries = parse_feed(r.text)
                except Exception:  # noqa: BLE001
                    continue
                for e in entries:
                    text = (e["title"] + ". " + e["summary"]).strip(". ")
                    if not text or (query and query.lower() not in text.lower()):
                        continue
                    yield RawItem(
                        id="rss_" + hashlib.sha1((e["link"] or text).encode()).hexdigest()[:12],
                        source_type=self.source_type, source_url=e["link"] or feed,
                        title=e["title"], text=text,
                    )
