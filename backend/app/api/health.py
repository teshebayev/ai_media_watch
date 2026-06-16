"""Роутер /health — пинг vLLM / Qdrant / Neo4j."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict:
    status = {"api": "ok", "vllm": "unknown", "qdrant": "unknown", "neo4j": "unknown"}

    # vLLM
    try:
        await request.app.state.llm.models.list()
        status["vllm"] = "ok"
    except Exception as e:  # noqa: BLE001
        status["vllm"] = f"down: {type(e).__name__}"

    # Qdrant
    try:
        await request.app.state.qdrant.get_collections()
        status["qdrant"] = "ok"
    except Exception as e:  # noqa: BLE001
        status["qdrant"] = f"down: {type(e).__name__}"

    # Neo4j
    try:
        await request.app.state.neo4j.verify_connectivity()
        status["neo4j"] = "ok"
    except Exception as e:  # noqa: BLE001
        status["neo4j"] = f"down: {type(e).__name__}"

    return status
