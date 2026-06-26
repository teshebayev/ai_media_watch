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
  GET  /shadow/actors/scored    — риск-скоринг акторов (охват × степень в сети × кросс-продукт)
  GET  /shadow/clusters         — кластеры связанных акторов + риск сети и «вожак» (hub)
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
from apps.digital_shadow.collectors import (  # noqa: E402
    DarknetMockCollector,
    DemoClusterCollector,
)
from apps.digital_shadow.pipeline import analyze_item  # noqa: E402
from apps.digital_shadow.schemas import ShadowFinding, ShadowItem  # noqa: E402
from backend.app.clients.neo4j import ensure_constraints, make_neo4j_driver  # noqa: E402
from backend.app.clients.qdrant import make_qdrant_client  # noqa: E402
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
    # Qdrant — семантическое сходство с известными листингами (best-effort).
    app.state.qdrant = make_qdrant_client() if s.enable_similarity else None
    yield
    if app.state.neo4j is not None:
        await app.state.neo4j.close()
    if getattr(app.state, "qdrant", None) is not None:
        try:
            await app.state.qdrant.close()
        except Exception:  # noqa: BLE001
            pass
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
        item, driver=getattr(app.state, "neo4j", None), watchlist=wl, bad_entities=bad,
        qdrant=getattr(app.state, "qdrant", None))
    await persistence.save_finding(
        finding, platform=item.platform, language=item.language, text=item.text)
    return finding


@app.post("/shadow/collect/mock")
async def collect_mock(query: str | None = None) -> dict:
    """Демо: собрать синтетические даркнет-листинги, проанализировать, сохранить, отсортировать."""
    driver = getattr(app.state, "neo4j", None)
    qdrant = getattr(app.state, "qdrant", None)
    wl = await persistence.watchlist_values()
    bad = await persistence.bad_entity_values()
    findings: list[ShadowFinding] = []
    async for raw in DarknetMockCollector().collect(query):
        f = await analyze_item(raw, driver=driver, watchlist=wl, bad_entities=bad, qdrant=qdrant)
        await persistence.save_finding(
            f, platform=raw.platform, language=raw.language, text=raw.text)
        findings.append(f)
    findings.sort(key=lambda f: f.threat_score, reverse=True)  # приоритет сверху
    return {"count": len(findings), "findings": [f.model_dump() for f in findings]}


@app.post("/shadow/collect/demo")
async def collect_demo(query: str | None = None) -> dict:
    """Демо для графа: листинги с общими индикаторами → кластеры по торговлям
    (вейпы/алкоголь/наркотики/дропы/утечки) + кросс-категорийный мост (наркотики↔дропы)."""
    driver = getattr(app.state, "neo4j", None)
    qdrant = getattr(app.state, "qdrant", None)
    wl = await persistence.watchlist_values()
    bad = await persistence.bad_entity_values()
    findings: list[ShadowFinding] = []
    async for raw in DemoClusterCollector().collect(query):
        f = await analyze_item(raw, driver=driver, watchlist=wl, bad_entities=bad, qdrant=qdrant)
        await persistence.save_finding(
            f, platform=raw.platform, language=raw.language, text=raw.text)
        findings.append(f)
    findings.sort(key=lambda f: f.threat_score, reverse=True)
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


@app.get("/shadow/actors/scored")
async def actors_scored(
    limit: int = Query(20, ge=1, le=200),
    min_uses: int = Query(2, ge=1, le=100),
    scan: int = Query(500, ge=1, le=5000),
) -> dict:
    """Скоринг акторов: риск отдельной сущности по охвату (uses) + степени в сети
    (co_actors) + разнообразию источников + кросс-продуктовости. Сортировка по actor_risk."""
    return {"actors": await actors_svc.actor_scores(
        getattr(app.state, "neo4j", None), limit=limit, min_uses=min_uses, scan=scan)}


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


@app.get("/shadow/path")
async def path(
    a: str = Query(..., min_length=1, description="сущность A (домен/кошелёк/@telegram)"),
    b: str = Query(..., min_length=1, description="сущность B"),
    max_hops: int = Query(5, ge=1, le=6),
) -> dict:
    """Объяснимость связи: кратчайший путь между двумя сущностями + «почему связаны»."""
    driver = getattr(app.state, "neo4j", None)
    if driver is None:
        return {"found": False, "explanation": ["граф выключен (ENABLE_GRAPH=false)"],
                "nodes": [], "edges": []}
    try:
        return await graph_service.explain_link(driver, a, b, max_hops=max_hops)
    except Exception as e:  # noqa: BLE001 — Neo4j может быть недоступен
        return {"found": False, "explanation": [f"граф недоступен: {type(e).__name__}"],
                "nodes": [], "edges": []}


def _merge_graphs(*graphs: dict) -> dict:
    """Слить несколько nodes/edges-подграфов в один (дедуп узлов по id, рёбер по from/to/label)."""
    nodes: dict[str, dict] = {}
    edges: dict[tuple, dict] = {}
    for g in graphs:
        for n in g.get("nodes", []):
            nodes[n["id"]] = n
        for e in g.get("edges", []):
            edges[(e["from"], e["to"], e.get("label"))] = e
    return {"nodes": list(nodes.values()), "edges": list(edges.values())}


@app.get("/shadow/graph")
async def graph(value: str | None = None, limit: int = 200) -> dict:
    """Теневой граф (общий Neo4j). Без value — теневые листинги (ShadowItem + их сущности,
    включая кошельки) ОБЪЕДИНЁННЫЕ с общим обзором кластеров (casino-x.com и пр.): видны и
    новые теневые данные, и старые кластеры. С value — окрестность конкретной сущности."""
    driver = getattr(app.state, "neo4j", None)
    if driver is None:
        return {"nodes": [], "edges": [], "note": "граф выключен (ENABLE_GRAPH=false)"}
    try:
        if value:
            return await graph_service.neighborhood(driver, value, limit=limit)
        shadow = await graph_service.source_subgraph(driver, "ShadowItem", limit=limit)
        media = await graph_service.overview(driver, limit=limit)
        return _merge_graphs(shadow, media)
    except Exception as e:  # noqa: BLE001 — Neo4j может быть недоступен
        return {"nodes": [], "edges": [], "note": f"граф недоступен: {type(e).__name__}"}


@app.get("/shadow/signals")
async def signals_legend() -> dict:
    """Справочник риск-сигналов: код · вес · человекочитаемое объяснение (легенда для UI)."""
    from apps.digital_shadow import taxonomy
    from apps.digital_shadow.prioritization import _weight

    items = [
        {"signal": s, "weight": _weight(s), "description": d}
        for s, d in taxonomy.SIGNAL_DESCRIPTIONS.items()
    ]
    items.sort(key=lambda x: x["weight"], reverse=True)
    return {"signals": items}


@app.get("/shadow/sessions")
async def sessions(limit: int = 20, category: str | None = None,
                   priority: str | None = None) -> dict:
    """Последние сохранённые находки из Postgres (опц. фильтры category/priority)."""
    return {"sessions": await persistence.list_findings(
        limit=limit, category=category, priority=priority)}
