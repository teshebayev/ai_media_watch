"""Ingest Service: URL → текст (в потоке, т.к. yt-dlp/httpx синхронные)."""

from __future__ import annotations

import asyncio

from src.ingest.url_fetcher import ingest as _ingest


async def ingest_url(url: str, deep: bool = False) -> dict:
    return await asyncio.to_thread(_ingest, url, deep)
