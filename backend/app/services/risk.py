"""Risk Service: тонкая обёртка над детерминированным src/risk/risk_engine.

Собирает Analyst Report по ТЗ §0 (выявляет сигналы, не обвиняет)."""

from __future__ import annotations

from src.risk.risk_engine import evaluate
from backend.app.schemas.enums import RiskLevel
from backend.app.schemas.models import (
    AnalystReport,
    Entities,
    FraudType,
    TriggeredSignal,
)


def build_report(
    record_id: str,
    signals: list[str],
    entities: Entities,
    evidence_spans: list[str],
    fraud_type: FraudType | None = None,
) -> AnalystReport:
    result = evaluate(signals)
    return AnalystReport(
        id=record_id,
        risk_score=result["risk_score"],
        risk_level=RiskLevel(result["risk_level"]),
        fraud_type=fraud_type,
        triggered_signals=[
            TriggeredSignal(signal=b["signal"], weight=b["weight"]) for b in result["breakdown"]
        ],
        entities=entities,
        evidence_spans=evidence_spans,
    )
