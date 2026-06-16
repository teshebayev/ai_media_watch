"""Scenario Service: LLM-классификация combined_text → fraud_type (ТЗ §7).

vLLM (OpenAI-compatible). Ответ строго JSON. Если LLM выключен флагом
ENABLE_LLM=false — возвращаем None (пайплайн работает на regex-сигналах).

Реализация промпта — этап 2 плана. Здесь каркас с системным промптом и
безопасным парсингом JSON.
"""

from __future__ import annotations

import json

from openai import AsyncOpenAI

from backend.app.config import get_settings
from backend.app.schemas.enums import RISK_SIGNALS, FraudType

SYSTEM_PROMPT = (
    "Ты — аналитик антифрод-системы. Верни СТРОГО один JSON-объект, без markdown и "
    "пояснений, все строки — на русском языке.\n"
    'Формат: {"fraud_type": "...", "confidence": 0..1, "risk_signals": [...], '
    '"evidence_spans": [...]}.\n'
    "fraud_type — РОВНО одно значение из списка: "
    + ", ".join(ft.value for ft in FraudType) + ".\n"
    "Если явных признаков мошенничества нет (обычная реклама банка/вклада/кредита, "
    "официальное предупреждение, образовательный пост) — ставь legit_finance, "
    "anti_fraud_education или ordinary_spam и risk_signals: []. Не преувеличивай: "
    "высокий доход или упоминание банка сами по себе не мошенничество.\n"
    "risk_signals — ТОЛЬКО значения из этого списка (если ничего не подходит — []): "
    + ", ".join(sorted(RISK_SIGNALS)) + ".\n"
    "evidence_spans — дословные фразы из текста. Не выноси обвинений, только риск-сигналы."
)


async def detect_scenario(llm: AsyncOpenAI, combined_text: str) -> dict | None:
    s = get_settings()
    if not s.enable_llm:
        return None
    resp = await llm.chat.completions.create(
        model=s.llm_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": combined_text},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(resp.choices[0].message.content or "{}")
    except (json.JSONDecodeError, IndexError):
        return None
