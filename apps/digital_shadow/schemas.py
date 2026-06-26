"""Pydantic-модели Digital Shadow. Переиспользуют общий формат сущностей из core."""

from __future__ import annotations

from pydantic import BaseModel, Field

from core import Entities


class ShadowItem(BaseModel):
    """Сырой элемент от коллектора (clearweb / darknet / paste)."""

    id: str
    source_type: str = "clearweb"          # clearweb | darknet | paste
    source_url: str | None = None          # .onion / http(s) / paste-id (для графа-источника)
    platform: str | None = None            # форум/маркет/барахолка/paste-сайт
    title: str | None = None
    text: str = ""
    language: str = "ru"
    collected_at: str | None = None        # ISO-время (проставляет коллектор)


class ShadowFinding(BaseModel):
    """Результат анализа ShadowItem — находка для аналитика."""

    id: str
    source_type: str
    source_url: str | None = None
    category: str = "unknown"              # SHADOW_CATEGORIES
    risk_score: int = 0
    risk_level: str = "low"
    priority: str = "low"                  # low | medium | high | urgent (из prioritization)
    threat_score: float = 0.0
    signals: list[str] = Field(default_factory=list)
    breakdown: list[dict] = Field(default_factory=list)      # [{signal, weight}] — вклад в скоринг
    entities: Entities = Field(default_factory=Entities)
    wallet_risks: list[dict] = Field(default_factory=list)   # из crypto_risk
    evidence: list[str] = Field(default_factory=list)
    recommendation: str = (
        "Система выявляет риск-сигналы и передаёт материал на ручную проверку аналитика; "
        "не выносит обвинение (правило §0)."
    )
