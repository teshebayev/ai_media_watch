"""FinGuard Core — общий движок для обоих продуктов (AI Media Watch + Digital Shadow).

Это **фасад** над уже существующим кодом: ничего не перемещаем, чтобы не ломать рабочий
стек (`backend/`, `src/`). Оба приложения (`apps/media_watch`, `apps/digital_shadow`) импортируют
общие примитивы отсюда — единая точка входа в движок:

    from core import AnalysisRecord, Entities, evaluate, extract_signals, graph_service

Слой, который реально общий для двух продуктов:
  - единый формат данных (§5) + контролируемые словари (enums);
  - детерминированный risk_engine (§11);
  - извлечение сущностей (regex) и риск-сигналов;
  - Shadow Graph (Neo4j) и similarity (Qdrant) — переиспользуются обоими, что даёт
    кросс-продуктовую связку: один и тот же кошелёк/домен/Telegram из соцвидео и из
    даркнет-листинга сходится в ОДИН узел графа.

Физическая консолидация (перенос модулей внутрь core/) — отдельный рефакторинг на потом;
сейчас core импортирует их по месту.
"""

from __future__ import annotations

# ── Схемы и словари (§5, §6–§9) ──────────────────────────────────────────────
from backend.app.schemas.enums import (
    RISK_SIGNALS,
    FraudType,
    Label,
    Modality,
    RiskLevel,
)
from backend.app.schemas.models import (
    AnalysisRecord,
    AnalystReport,
    Entities,
    MediaAnomalies,
)

# ── Слои инфраструктуры (переиспользуются обоими приложениями) ───────────────
from backend.app.services import graph as graph_service
from backend.app.services import osint as osint_service
from backend.app.services import similarity as similarity_service

# ── Извлечение сущностей и сигналов ──────────────────────────────────────────
from backend.app.services.entities import extract_regex_entities
from src.extraction.regex_extractors import (
    extract_crypto_wallets,
    extract_domains,
    extract_urls,
    hash_value,
    mask_phone,
)
from src.extraction.signal_extractor import (
    extract_signals,
    signals_from_entities,
    signals_from_text,
)

# ── Risk Engine (§11) ────────────────────────────────────────────────────────
from src.risk.risk_engine import (
    SIGNAL_WEIGHTS,
    evaluate,
    risk_level,
    score_signals,
    signal_weight,
)

__all__ = [
    "RISK_SIGNALS", "FraudType", "Label", "Modality", "RiskLevel",
    "AnalysisRecord", "AnalystReport", "Entities", "MediaAnomalies",
    "SIGNAL_WEIGHTS", "evaluate", "risk_level", "score_signals", "signal_weight",
    "extract_regex_entities", "extract_crypto_wallets", "extract_domains",
    "extract_urls", "hash_value", "mask_phone",
    "extract_signals", "signals_from_entities", "signals_from_text",
    "graph_service", "osint_service", "similarity_service",
]
