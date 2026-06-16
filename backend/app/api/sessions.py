"""Роутеры истории анализа, ручной проверки и аналитики (Postgres)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.api.deps import get_db
from backend.app.services import sessions as svc

router = APIRouter(tags=["sessions"])


class ReviewRequest(BaseModel):
    reviewer: str | None = None
    decision: str  # confirm / override
    final_label: str | None = None
    final_fraud_type: str | None = None
    notes: str | None = None


def _require_db(db):
    if db is None:
        raise HTTPException(status_code=503, detail="БД выключена (ENABLE_DB=false)")


@router.get("/sessions")
async def list_sessions(limit: int = 50, risk_level: str | None = None,
                        fraud_type: str | None = None, db=Depends(get_db)) -> dict:
    _require_db(db)
    items = await svc.list_sessions(db, limit=limit, risk_level=risk_level, fraud_type=fraud_type)
    return {"count": len(items), "sessions": items}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db=Depends(get_db)) -> dict:
    _require_db(db)
    row = await svc.get_session(db, session_id)
    if not row:
        raise HTTPException(status_code=404, detail="сеанс не найден")
    return row


@router.post("/sessions/{session_id}/review")
async def review_session(session_id: str, req: ReviewRequest, db=Depends(get_db)) -> dict:
    _require_db(db)
    return await svc.add_review(
        db, session_id, reviewer=req.reviewer, decision=req.decision,
        final_label=req.final_label, final_fraud_type=req.final_fraud_type, notes=req.notes)


@router.get("/stats")
async def stats(db=Depends(get_db)) -> dict:
    _require_db(db)
    return await svc.stats(db)
