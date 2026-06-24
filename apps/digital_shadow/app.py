"""Digital Shadow — end-to-end сервис (OSINT/DarkNet мониторинг).

Самостоятельный FastAPI на общем движке `core`. Поднимает РЕАЛЬНУЮ инфраструктуру в lifespan:
  - Neo4j  — тот же граф, что у AI Media Watch (кросс-продуктовая теневая сеть);
  - Postgres — журнал находок (переиспользует таблицу analysis_sessions, modality="shadow").

Сквозной путь: коллектор → pipeline (сущности → сигналы → риск → приоритет) →
upsert в общий граф + повторяемость → персист в Postgres → отдача находки.

Запуск (отдельный порт, не мешает основному API :8088):
    uvicorn apps.digital_shadow.app:app --port 8090

Эндпоинты:
  GET  /shadow/health           — статус + подключён ли граф/БД
  POST /shadow/analyze          — анализ одного элемента (ShadowItem) → ShadowFinding (+граф +БД)
  POST /shadow/collect/mock     — синтетические даркнет-листинги → находки (демо, по убыв. угрозы)
  GET  /shadow/clusters         — кластеры связанных акторов (мосты Media↔Shadow)
  GET  /shadow/graph            — обзор теневого графа (общий Neo4j) для визуализации
  GET  /shadow/sessions         — последние сохранённые находки (из Postgres)
"""

from __future__ import annotations

import pathlib
import sys
from contextlib import asynccontextmanager

# Корень репозитория импортируемым (как в backend.main) — чтобы работали core/backend/src.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from apps.digital_shadow import actors as actors_svc  # noqa: E402
from apps.digital_shadow import persistence  # noqa: E402
from apps.digital_shadow.collectors import DarknetMockCollector  # noqa: E402
from apps.digital_shadow.pipeline import analyze_item  # noqa: E402
from apps.digital_shadow.schemas import ShadowFinding, ShadowItem  # noqa: E402
from backend.app.clients.neo4j import ensure_constraints, make_neo4j_driver  # noqa: E402
from backend.app.config import get_settings  # noqa: E402
from core import graph_service  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    # Граф — общий с AI Media Watch. Best-effort: не валим старт, если Neo4j не поднят.
    app.state.neo4j = make_neo4j_driver() if s.enable_graph else None
    if app.state.neo4j is not None:
        try:
            await ensure_constraints(app.state.neo4j)
        except Exception:  # noqa: BLE001
            pass
    yield
    if app.state.neo4j is not None:
        await app.state.neo4j.close()
    if s.enable_db:
        from backend.app.clients.db import get_engine

        try:
            await get_engine().dispose()
        except Exception:  # noqa: BLE001
            pass


app = FastAPI(title="Digital Shadow", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.get("/")
async def root() -> dict:
    return {"service": "Digital Shadow", "docs": "/docs", "health": "/shadow/health"}


@app.get("/shadow/health")
async def health() -> dict:
    s = get_settings()
    driver = getattr(app.state, "neo4j", None)
    graph_ok = False
    if driver is not None:
        try:
            await graph_service.overview(driver, entities=1, limit=1)
            graph_ok = True
        except Exception:  # noqa: BLE001
            graph_ok = False
    return {"status": "ok", "graph_connected": graph_ok, "db_enabled": s.enable_db}


@app.post("/shadow/analyze", response_model=ShadowFinding)
async def analyze(item: ShadowItem) -> ShadowFinding:
    wl = await persistence.watchlist_values()
    bad = await persistence.bad_entity_values()
    finding = await analyze_item(
        item, driver=getattr(app.state, "neo4j", None), watchlist=wl, bad_entities=bad)
    await persistence.save_finding(
        finding, platform=item.platform, language=item.language, text=item.text)
    return finding


@app.post("/shadow/collect/mock")
async def collect_mock(query: str | None = None) -> dict:
    """Демо: собрать синтетические даркнет-листинги, проанализировать, сохранить, отсортировать."""
    driver = getattr(app.state, "neo4j", None)
    wl = await persistence.watchlist_values()
    bad = await persistence.bad_entity_values()
    findings: list[ShadowFinding] = []
    async for raw in DarknetMockCollector().collect(query):
        f = await analyze_item(raw, driver=driver, watchlist=wl, bad_entities=bad)
        await persistence.save_finding(
            f, platform=raw.platform, language=raw.language, text=raw.text)
        findings.append(f)
    findings.sort(key=lambda f: f.threat_score, reverse=True)  # приоритет сверху
    return {"count": len(findings), "findings": [f.model_dump() for f in findings]}


# ── Триаж / ревью ────────────────────────────────────────────────────────────
@app.get("/shadow/queue")
async def queue(status: str | None = None, limit: int = 50) -> dict:
    """Очередь триажа по убыванию threat_score (опц. фильтр статуса)."""
    return {"queue": await persistence.list_queue(limit=limit, status=status)}


class ReviewRequest(BaseModel):
    decision: str                 # confirm / dismiss / in_review
    reviewer: str | None = None
    notes: str | None = None


@app.post("/shadow/findings/{finding_id}/review")
async def review(finding_id: str, req: ReviewRequest) -> dict:
    res = await persistence.add_review(
        finding_id, req.decision, reviewer=req.reviewer, notes=req.notes)
    if res is None:
        raise HTTPException(status_code=400, detail="неизвестное решение или БД недоступна")
    return res


# ── Watchlist ────────────────────────────────────────────────────────────────
class WatchRequest(BaseModel):
    value: str
    kind: str | None = None
    note: str | None = None


@app.get("/shadow/watchlist")
async def watchlist_get() -> dict:
    return {"watchlist": await persistence.watchlist_list()}


@app.post("/shadow/watchlist")
async def watchlist_post(req: WatchRequest) -> dict:
    ok = await persistence.watchlist_add(req.value, kind=req.kind, note=req.note)
    return {"added": ok, "value": req.value}


@app.delete("/shadow/watchlist")
async def watchlist_delete(value: str) -> dict:
    return {"removed": await persistence.watchlist_remove(value), "value": value}


# ── Профили акторов / кросс-продукт ──────────────────────────────────────────
@app.get("/shadow/actors")
async def actors(limit: int = 20, min_uses: int = 2) -> dict:
    """Топ повторяющихся сущностей в графе (cross_product=мост Media↔Shadow)."""
    return {"actors": await actors_svc.top_actors(
        getattr(app.state, "neo4j", None), limit=limit, min_uses=min_uses)}


@app.get("/shadow/cross")
async def cross(limit: int = 50) -> dict:
    """Только кросс-продуктовые сущности: связывают контент (Media) и теневые источники (Shadow)."""
    return {"cross": await actors_svc.cross_product(getattr(app.state, "neo4j", None), limit=limit)}


@app.get("/shadow/clusters")
async def clusters(
    min_uses: int = Query(2, ge=1, le=100),
    limit: int = Query(500, ge=1, le=5000),
    max_clusters: int = Query(50, ge=1, le=500),
) -> dict:
    """Кластеры связанных акторов (связные компоненты по со-упоминанию).
    cross_product=True — кластер связывает контент (Media) и теневые источники (Shadow)."""
    cl = await actors_svc.actor_clusters(
        getattr(app.state, "neo4j", None),
        min_uses=min_uses, limit=limit, max_clusters=max_clusters)
    return {"clusters": cl, "count": len(cl)}


@app.get("/shadow/graph")
async def graph(value: str | None = None, limit: int = 150) -> dict:
    """Теневой граф (общий Neo4j): окрестность сущности или обзор кластеров."""
    driver = getattr(app.state, "neo4j", None)
    if driver is None:
        return {"nodes": [], "edges": [], "note": "граф выключен (ENABLE_GRAPH=false)"}
    try:
        if value:
            return await graph_service.neighborhood(driver, value, limit=limit)
        return await graph_service.overview(driver, limit=limit)
    except Exception as e:  # noqa: BLE001 — Neo4j может быть недоступен
        return {"nodes": [], "edges": [], "note": f"граф недоступен: {type(e).__name__}"}


@app.get("/shadow/sessions")
async def sessions(limit: int = 20, category: str | None = None,
                   priority: str | None = None) -> dict:
    """Последние сохранённые находки из Postgres (опц. фильтры category/priority)."""
    return {"sessions": await persistence.list_findings(
        limit=limit, category=category, priority=priority)}
