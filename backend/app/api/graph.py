"""Роутер /graph/* — связи и повторяемость сущностей из Neo4j."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.deps import get_neo4j
from backend.app.services import graph as graph_svc

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/entity/{value}")
async def entity_reuse(value: str, neo4j=Depends(get_neo4j)) -> dict:
    uses = await graph_svc.entity_reuse(neo4j, value)
    return {"value": value, "uses": uses, "graph_entity_reuse": uses > 1}


@router.get("/network")
async def network(value: str | None = None, limit: int = 150, neo4j=Depends(get_neo4j)) -> dict:
    """Подграф для визуализации (nodes/edges). С value — окрестность сущности,
    без value — overview топ-повторяемых кластеров."""
    if value:
        return await graph_svc.neighborhood(neo4j, value, limit=limit)
    return await graph_svc.overview(neo4j, limit=limit)
