"""SQLAlchemy-модели персистентного слоя (Postgres).

analysis_sessions — журнал каждого вызова /analyze/* (история/аудит).
analyst_reviews   — ручная проверка аналитика (human-in-the-loop, ТЗ §0).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
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
    media_anomalies: Mapped[dict] = mapped_column(JSONB, default=dict)
    evidence_spans: Mapped[list] = mapped_column(JSONB, default=list)
    recommendation: Mapped[str | None] = mapped_column(Text)
    llm_used: Mapped[bool] = mapped_column(default=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    reviews: Mapped[list[AnalystReview]] = relationship(
        back_populates="session", cascade="all, delete-orphan")


class ShadowFinding(Base):
    """Находка Digital Shadow (OSINT/DarkNet). Своя таблица — у неё своя таксономия
    (category вместо fraud_type, priority/threat_score, source_type)."""

    __tablename__ = "shadow_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True)
    item_id: Mapped[str | None] = mapped_column(String(128))
    source_type: Mapped[str | None] = mapped_column(String(16), index=True)  # clearweb/darknet/paste
    source_url: Mapped[str | None] = mapped_column(Text)
    platform: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(8))

    category: Mapped[str | None] = mapped_column(String(32), index=True)     # SHADOW_CATEGORIES
    risk_score: Mapped[int | None] = mapped_column(Integer)
    risk_level: Mapped[str | None] = mapped_column(String(16), index=True)
    priority: Mapped[str | None] = mapped_column(String(16), index=True)     # low/medium/high/urgent
    threat_score: Mapped[float | None] = mapped_column(Float)
    signals: Mapped[list] = mapped_column(JSONB, default=list)
    entities: Mapped[dict] = mapped_column(JSONB, default=dict)
    wallet_risks: Mapped[list] = mapped_column(JSONB, default=list)
    text_preview: Mapped[str | None] = mapped_column(Text)
    # триаж аналитика: new → in_review → confirmed / dismissed
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)


class ShadowReview(Base):
    """Решение аналитика по находке Digital Shadow (human-in-the-loop, §0)."""

    __tablename__ = "shadow_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shadow_findings.id", ondelete="CASCADE"), index=True)
    reviewer: Mapped[str | None] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(16))     # confirm / dismiss / in_review
    notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())


class ShadowWatchlist(Base):
    """Список отслеживаемых сущностей (кошельки/домены/@ник): при появлении в находке —
    сигнал `watchlisted` и приоритет."""

    __tablename__ = "shadow_watchlist"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    value: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    kind: Mapped[str | None] = mapped_column(String(24))  # wallet/domain/telegram/promo
    note: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())


class ShadowEntityReputation(Base):
    """Репутация публичного индикатора (кошелёк/домен/@ник/промокод) — flywheel:
    решения аналитика возвращаются в скоринг. ТОЛЬКО публичные индикаторы, НЕ ПДн (§0)."""

    __tablename__ = "shadow_entity_reputation"

    value: Mapped[str] = mapped_column(String(256), primary_key=True)
    kind: Mapped[str | None] = mapped_column(String(24))   # wallet/domain/telegram/promo
    abuse_count: Mapped[int] = mapped_column(Integer, default=0)
    confirmed_count: Mapped[int] = mapped_column(Integer, default=0)
    dismissed_count: Mapped[int] = mapped_column(Integer, default=0)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())


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
