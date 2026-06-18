"""Сервис персистентных сеансов анализа и ручной проверки (Postgres)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.models import AnalysisSession, AnalystReview
from backend.app.schemas.models import AnalystReport


async def save_session(
    db: AsyncSession | None,
    report: AnalystReport,
    *,
    modality: str,
    source: str | None = None,
    input_url: str | None = None,
    text_preview: str | None = None,
    language: str | None = None,
    llm_used: bool = False,
    latency_ms: int | None = None,
    media_anomalies: dict | None = None,
) -> str | None:
    """Сохранить сеанс анализа. Best-effort: при выключенной/недоступной БД — None."""
    if db is None:
        return None
    row = AnalysisSession(
        record_id=report.id,
        modality=modality,
        source=source,
        input_url=input_url,
        text_preview=(text_preview or "")[:2000] or None,
        language=language,
        fraud_type=report.fraud_type.value if report.fraud_type else None,
        risk_score=report.risk_score,
        risk_level=report.risk_level.value if report.risk_level else None,
        risk_signals=[s.signal for s in report.triggered_signals],
        entities=report.entities.model_dump(),
        media_anomalies=media_anomalies or {},
        evidence_spans=report.evidence_spans,
        recommendation=report.recommendation,
        llm_used=llm_used,
        latency_ms=latency_ms,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return str(row.id)


async def list_sessions(db: AsyncSession, *, limit: int = 50,
                        risk_level: str | None = None, fraud_type: str | None = None) -> list[dict]:
    q = select(AnalysisSession).order_by(AnalysisSession.created_at.desc()).limit(limit)
    if risk_level:
        q = q.where(AnalysisSession.risk_level == risk_level)
    if fraud_type:
        q = q.where(AnalysisSession.fraud_type == fraud_type)
    rows = (await db.execute(q)).scalars().all()
    return [_session_brief(r) for r in rows]


async def get_session(db: AsyncSession, session_id: str) -> dict | None:
    q = (select(AnalysisSession)
         .options(selectinload(AnalysisSession.reviews))
         .where(AnalysisSession.id == uuid.UUID(session_id)))
    row = (await db.execute(q)).scalar_one_or_none()
    return _session_full(row) if row else None


async def add_review(db: AsyncSession, session_id: str, *, reviewer: str | None,
                     decision: str, final_label: str | None,
                     final_fraud_type: str | None, notes: str | None) -> dict:
    review = AnalystReview(
        session_id=uuid.UUID(session_id), reviewer=reviewer, decision=decision,
        final_label=final_label, final_fraud_type=final_fraud_type, notes=notes,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return {"id": str(review.id), "session_id": session_id, "decision": decision,
            "final_label": final_label, "final_fraud_type": final_fraud_type}


async def stats(db: AsyncSession) -> dict:
    total = (await db.execute(select(func.count(AnalysisSession.id)))).scalar()
    by_level = dict((await db.execute(
        select(AnalysisSession.risk_level, func.count()).group_by(AnalysisSession.risk_level))).all())
    by_fraud = dict((await db.execute(
        select(AnalysisSession.fraud_type, func.count())
        .group_by(AnalysisSession.fraud_type)
        .order_by(func.count().desc()).limit(10))).all())
    reviewed = (await db.execute(select(func.count(func.distinct(AnalystReview.session_id))))).scalar()
    return {"total_sessions": total, "by_risk_level": by_level,
            "top_fraud_types": by_fraud, "reviewed_sessions": reviewed}


def _session_brief(r: AnalysisSession) -> dict:
    return {"id": str(r.id), "created_at": r.created_at.isoformat() if r.created_at else None,
            "modality": r.modality, "fraud_type": r.fraud_type, "risk_level": r.risk_level,
            "risk_score": r.risk_score, "text_preview": (r.text_preview or "")[:120]}


def _session_full(r: AnalysisSession) -> dict:
    d = _session_brief(r)
    d.update({"source": r.source, "input_url": r.input_url, "language": r.language,
              "text_preview": r.text_preview, "risk_signals": r.risk_signals,
              "entities": r.entities, "media_anomalies": r.media_anomalies,
              "evidence_spans": r.evidence_spans,
              "recommendation": r.recommendation, "llm_used": r.llm_used,
              "latency_ms": r.latency_ms,
              "reviews": [{"id": str(rv.id), "reviewer": rv.reviewer, "decision": rv.decision,
                           "final_label": rv.final_label, "final_fraud_type": rv.final_fraud_type,
                           "notes": rv.notes,
                           "reviewed_at": rv.reviewed_at.isoformat() if rv.reviewed_at else None}
                          for rv in r.reviews]})
    return d
