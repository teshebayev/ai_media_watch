"""Роутер /search/* — похожие кейсы из Qdrant."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.deps import get_qdrant
from backend.app.services import similarity as sim_svc

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/similar")
async def search_similar(text: str, limit: int = 5, qdrant=Depends(get_qdrant)) -> dict:
    neighbors = await sim_svc.search_similar(qdrant, text, limit=limit)
    return {"neighbors": neighbors, "similar_to_known_scam": sim_svc.similarity_signal(neighbors)}
