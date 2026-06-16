"""SQLAlchemy-модели персистентного слоя (Postgres).

analysis_sessions — журнал каждого вызова /analyze/* (история/аудит).
analyst_reviews   — ручная проверка аналитика (human-in-the-loop, ТЗ §0).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True)
    record_id: Mapped[str | None] = mapped_column(String(128))
    modality: Mapped[str] = mapped_column(String(16))          # text/url/audio/video
    source: Mapped[str | None] = mapped_column(String(64))
    input_url: Mapped[str | None] = mapped_column(Text)
    text_preview: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(8))

    fraud_type: Mapped[str | None] = mapped_column(String(64), index=True)
    label: Mapped[str | None] = mapped_column(String(16))
    risk_score: Mapped[int | None] = mapped_column(Integer)
    risk_level: Mapped[str | None] = mapped_column(String(16), index=True)
    risk_signals: Mapped[list] = mapped_column(JSONB, default=list)
    entities: Mapped[dict] = mapped_column(JSONB, default=dict)
    evidence_spans: Mapped[list] = mapped_column(JSONB, default=list)
    recommendation: Mapped[str | None] = mapped_column(Text)
    llm_used: Mapped[bool] = mapped_column(default=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    reviews: Mapped[list[AnalystReview]] = relationship(
        back_populates="session", cascade="all, delete-orphan")


class AnalystReview(Base):
    __tablename__ = "analyst_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"), index=True)
    reviewer: Mapped[str | None] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(16))          # confirm / override
    final_label: Mapped[str | None] = mapped_column(String(16))
    final_fraud_type: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())

    session: Mapped[AnalysisSession] = relationship(back_populates="reviews")
