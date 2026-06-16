"""Pydantic-модели = единый JSONL-формат из ТЗ §5 + Analyst Report (§6 плана)."""

from pydantic import BaseModel, Field

from backend.app.schemas.enums import FraudType, Label, Modality, RiskLevel


class Entities(BaseModel):
    urls: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    telegram_usernames: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)  # только маска/хэш (ТЗ §0)
    promo_codes: list[str] = Field(default_factory=list)
    crypto_wallets: list[str] = Field(default_factory=list)
    money_amounts: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)


class MediaAnomalies(BaseModel):
    has_face: bool = False
    possible_deepfake: bool = False
    synthetic_voice_suspected: bool = False
    lip_sync_anomaly: bool = False


class AnalysisRecord(BaseModel):
    """Одна строка ai_media_watch_dataset.jsonl (ТЗ §5)."""

    id: str
    source: str
    platform: str
    modality: Modality
    case_type: str | None = None
    language: str = "ru"
    url: str | None = None
    media_path: str | None = None  # локальный путь к mp4/wav (для офлайн-транскрибации)
    title: str | None = None
    description: str | None = None
    transcript: str | None = None
    ocr_text: str | None = None
    combined_text: str = ""

    entities: Entities = Field(default_factory=Entities)
    media_anomalies: MediaAnomalies = Field(default_factory=MediaAnomalies)

    risk_signals: list[str] = Field(default_factory=list)
    evidence_spans: list[str] = Field(default_factory=list)

    label: Label | None = None
    fraud_type: FraudType | None = None
    risk_level: RiskLevel | None = None
    risk_score: int | None = None

    annotator: str | None = None
    review_status: str | None = None


class TriggeredSignal(BaseModel):
    signal: str
    weight: int


class AnalystReport(BaseModel):
    """Выход Risk Engine. Формулировка ТЗ §0: система выявляет риск-сигналы и
    передаёт на ручную проверку, не выносит обвинение."""

    id: str
    risk_score: int
    risk_level: RiskLevel
    fraud_type: FraudType | None = None
    triggered_signals: list[TriggeredSignal] = Field(default_factory=list)
    entities: Entities = Field(default_factory=Entities)
    evidence_spans: list[str] = Field(default_factory=list)
    recommendation: str = (
        "Система не выносит юридическое обвинение. Выявлены риск-сигналы; "
        "материал передаётся на ручную проверку аналитика."
    )
