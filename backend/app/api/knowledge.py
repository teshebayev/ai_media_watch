"""Роутер /agent/* — AFM Knowledge Agent (Q&A по базе знаний с гибридным поиском)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.api.deps import get_llm, get_qdrant
from backend.app.config import get_settings
from backend.app.services import knowledge as kb

router = APIRouter(prefix="/agent", tags=["agent"])


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Вопрос пользователя на естественном языке")


@router.post("/ask")
async def ask(req: AskRequest, qdrant=Depends(get_qdrant), llm=Depends(get_llm)) -> dict:
    if not get_settings().enable_kb:
        raise HTTPException(status_code=503, detail="KB-агент выключен (ENABLE_KB=false)")
    return await kb.ask(qdrant, llm, req.question)


@router.get("/search")
async def search(q: str, limit: int = 4, qdrant=Depends(get_qdrant)) -> dict:
    """Только гибридный поиск по карточкам (без генерации ответа) — для отладки."""
    hits = await kb.hybrid_search(qdrant, q, limit=limit)
    return {"hits": hits}


@router.post("/reindex")
async def reindex(recreate: bool = True, qdrant=Depends(get_qdrant)) -> dict:
    n = await kb.index_cards(qdrant, recreate=recreate)
    return {"indexed": n, "collection": get_settings().kb_collection}


@router.get("/status")
async def status(qdrant=Depends(get_qdrant)) -> dict:
    s = get_settings()
    return {
        "enabled": s.enable_kb,
        "collection": s.kb_collection,
        "indexed": await kb.kb_count(qdrant),
        "embedding_model": s.embedding_model,
        "search": "hybrid (dense e5 + sparse BM25, RRF fusion)",
    }
