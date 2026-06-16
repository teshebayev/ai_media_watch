"""Оркестратор пайплайна (ТЗ §2):

combined_text → entities (regex+LLM) → scenario (LLM) → similarity (Qdrant)
→ graph upsert (Neo4j) → risk engine → Analyst Report

Каждый слой опционален (фичефлаги) — минимальный жизнеспособный срез работает
на regex + signal_extractor + risk_engine без внешних сервисов.
"""

from __future__ import annotations

import asyncio

from openai import AsyncOpenAI
from neo4j import AsyncDriver
from qdrant_client import AsyncQdrantClient

from src.extraction.signal_extractor import extract_signals
from backend.app.config import get_settings
from backend.app.schemas.enums import RISK_SIGNALS, FraudType
from backend.app.schemas.models import AnalystReport
from backend.app.services import entities as entity_svc
from backend.app.services import graph as graph_svc
from backend.app.services import risk as risk_svc
from backend.app.services import scenario as scenario_svc
from backend.app.services import similarity as sim_svc


async def analyze_text(
    record_id: str,
    combined_text: str,
    *,
    language: str = "ru",
    llm: AsyncOpenAI | None = None,
    qdrant: AsyncQdrantClient | None = None,
    neo4j: AsyncDriver | None = None,
) -> AnalystReport:
    s = get_settings()

    # 1. Сущности (regex) — детерминированный фундамент
    entities = entity_svc.extract_regex_entities(combined_text)

    # 1b. LLM-добор организаций/проектов (второй проход)
    if s.enable_llm and llm is not None:
        entities = await entity_svc.enrich_with_llm(combined_text, entities)

    # 1c. Казахский NER (KazNERD, Этап 8.4) — для kk-текста, best-effort
    if language == "kk":
        entities = await asyncio.to_thread(entity_svc.enrich_with_ner, combined_text, entities)

    # 2. Базовые сигналы из текста + сущностей
    signals = extract_signals(combined_text, entities.model_dump())
    evidence: list[str] = []
    fraud_type: FraudType | None = None

    # 3. Scenario detection (LLM) — категория + доп. сигналы/evidence
    if s.enable_llm and llm is not None:
        scenario = await scenario_svc.detect_scenario(llm, combined_text)
        if scenario:
            # фильтруем сигналы LLM к контролируемому словарю §9 (модель иногда выдумывает)
            signals += [x for x in scenario.get("risk_signals", []) if x in RISK_SIGNALS]
            evidence += scenario.get("evidence_spans", [])
            raw_ft = scenario.get("fraud_type")
            if raw_ft in FraudType._value2member_map_:
                fraud_type = FraudType(raw_ft)

    # 4. Similarity (Qdrant)
    if s.enable_similarity and qdrant is not None:
        neighbors = await sim_svc.search_similar(qdrant, combined_text)
        if sim_svc.similarity_signal(neighbors):
            signals.append("similar_to_known_scam")

    # 5. Graph upsert + повторяемость (Neo4j). Проверяем домены/telegram/промокоды.
    if s.enable_graph and neo4j is not None:
        await graph_svc.upsert_entities(neo4j, record_id, entities)
        reuse_candidates = (
            entities.domains + entities.telegram_usernames + entities.promo_codes
        )
        for value in reuse_candidates:
            if await graph_svc.entity_reuse(neo4j, value) > 1:
                signals.append("graph_entity_reuse")
                break

    # 6. Risk engine (детерминированный) → Analyst Report
    signals = list(dict.fromkeys(signals))
    return risk_svc.build_report(record_id, signals, entities, evidence, fraud_type)
