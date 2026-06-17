"""Ingest Service: URL → текст (в потоке, т.к. yt-dlp/httpx синхронные)."""

from __future__ import annotations

import asyncio

from src.ingest.url_fetcher import cleanup_media_path as _cleanup
from src.ingest.url_fetcher import ingest as _ingest


async def ingest_url(url: str, deep: bool = False) -> dict:
    return await asyncio.to_thread(_ingest, url, deep)


def cleanup_media_path(media_path: str | None) -> None:
    """Удалить временную папку скачанного видео (после deepfake-анализа)."""
    _cleanup(media_path)
