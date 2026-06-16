"""DI-провайдеры: достаём клиентов из app.state (создаются в lifespan main.py)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request

from backend.app.clients.db import get_sessionmaker
from backend.app.config import get_settings


def get_llm(request: Request):
    return request.app.state.llm


def get_qdrant(request: Request):
    return request.app.state.qdrant


def get_neo4j(request: Request):
    return request.app.state.neo4j


async def get_db() -> AsyncIterator:
    """Async-сессия Postgres. None, если БД выключена (ENABLE_DB=false)."""
    if not get_settings().enable_db:
        yield None
        return
    async with get_sessionmaker()() as session:
        yield session
