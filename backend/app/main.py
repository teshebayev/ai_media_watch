"""FastAPI-приложение FakeFace FinGuard. Оркестратор пайплайна (план, этап 3).

Клиенты vLLM/Qdrant/Neo4j создаются в lifespan и кладутся в app.state (DI через Depends).
"""

from __future__ import annotations

import pathlib
import sys
from contextlib import asynccontextmanager

# Делаем корень репозитория импортируемым, чтобы работал `import src...`
# (src/extraction, src/risk — общий код со студенческими скриптами).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from backend.app.api import analyze, graph, health, knowledge, search, sessions  # noqa: E402
from backend.app.clients.llm import make_llm_client  # noqa: E402
from backend.app.clients.neo4j import ensure_constraints, make_neo4j_driver  # noqa: E402
from backend.app.clients.qdrant import ensure_collection, make_qdrant_client  # noqa: E402
from backend.app.config import get_settings  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    app.state.llm = make_llm_client()
    app.state.qdrant = make_qdrant_client()
    app.state.neo4j = make_neo4j_driver()

    # Best-effort инициализация: не валим старт, если внешний сервис ещё не поднялся.
    if s.enable_similarity:
        try:
            await ensure_collection(app.state.qdrant)
        except Exception:  # noqa: BLE001
            pass
    if s.enable_graph:
        try:
            await ensure_constraints(app.state.neo4j)
        except Exception:  # noqa: BLE001
            pass
    if s.enable_kb:
        # Коллекция KB-агента + автоиндексация карточек, если пусто (идемпотентно).
        try:
            from backend.app.services import knowledge as kb

            await kb.ensure_kb_collection(app.state.qdrant)
            if await kb.kb_count(app.state.qdrant) == 0:
                await kb.index_cards(app.state.qdrant)
        except Exception:  # noqa: BLE001
            pass

    yield

    await app.state.neo4j.close()
    await app.state.qdrant.close()
    await app.state.llm.close()
    if s.enable_db:
        from backend.app.clients.db import get_engine
        await get_engine().dispose()


app = FastAPI(title="FakeFace FinGuard", version="0.1.0", lifespan=lifespan)

# CORS — чтобы статический фронт (file:// или другой порт) мог ходить в API.
# Для хакатона разрешаем всё; в проде сузить до конкретных origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(graph.router)
app.include_router(search.router)
app.include_router(sessions.router)
app.include_router(knowledge.router)


@app.get("/")
async def root() -> dict:
    return {"service": "FakeFace FinGuard", "docs": "/docs", "health": "/health"}
