"""Шаг 8 — собрать единый ai_media_watch_dataset.jsonl из всех processed-источников.

- валидирует каждую строку Pydantic-моделью AnalysisRecord (единый формат §5);
- доскорит risk_score/risk_level детерминированным risk_engine, где их нет;
- печатает сводку по label / fraud_type / language / modality.

Запуск:
    python -m src.build_dataset
"""

from __future__ import annotations

import collections
import glob
import json
import os

from backend.app.schemas.enums import FraudType, Label, RiskLevel
from backend.app.schemas.models import AnalysisRecord
from src.risk.risk_engine import evaluate

OUT = "data/processed/ai_media_watch_dataset.jsonl"

# Нормализация перед записью (Шаг 8.5):
MAX_COMBINED_CHARS = 4000  # обрезаем гигантские склейки (был выброс 228k символов)
# приоритет при text-дедупе: информативный лейбл важнее «unclear»/пустого
_LABEL_PRIO = {Label.scam: 0, Label.spam: 1, Label.legit: 2, Label.unclear: 3, None: 4}


def normalize(records: list[AnalysisRecord]) -> list[AnalysisRecord]:
    """Чистка датасета: (1) чиним таксономию лейблов, (2) режем выбросы по длине,
    (3) дедуп по combined_text (оставляем самую информативную копию)."""
    # (1) ordinary_spam, ошибочно помеченный unclear → spam (убирает ~110k «мусорного» unclear)
    for r in records:
        if r.fraud_type == FraudType.ordinary_spam and r.label == Label.unclear:
            r.label = Label.spam
    # (2) обрезка длинных текстов
    for r in records:
        if r.combined_text and len(r.combined_text) > MAX_COMBINED_CHARS:
            r.combined_text = r.combined_text[:MAX_COMBINED_CHARS]
    # (3) дедуп по тексту; пустые тексты не схлопываем (ключуем по id)
    best: dict[str, AnalysisRecord] = {}
    for r in records:
        key = (r.combined_text or "").strip()
        if not key:
            best[f"__empty__{r.id}"] = r
            continue
        cur = best.get(key)
        if cur is None or _LABEL_PRIO[r.label] < _LABEL_PRIO[cur.label]:
            best[key] = r
    return list(best.values())

# Источники (порядок = приоритет при дедупе по id)
SOURCES = [
    "data/processed/ai_media_watch_dataset.sample.jsonl",
    "data/processed/kz_call_transcripts.jsonl",
    "data/processed/synthetic_posts.jsonl",
    "data/processed/stop_piramida.jsonl",
    "data/processed/ready_dataset_examples.jsonl",
    "data/processed/youtube_candidates_clean.jsonl",
    "data/processed/telegram_messages.jsonl",
    # batch Jun-2026: внешние парсенные датасеты (§5-формат)
    "data/processed/kz_call_transcripts_extra.jsonl",
    "data/processed/high_risk_full_final.jsonl",
    "data/processed/mshenoda_spam_messages.jsonl",
    # аугментация под казахский + закрытие дыр (ревью §): перевод, LLM-генерация, code-switch
    "data/processed/kk_translated_from_ru.jsonl",
    "data/processed/synthetic_llm.jsonl",
    "data/processed/codeswitch_kk_ru.jsonl",
]


def main() -> None:
    seen: dict[str, AnalysisRecord] = {}
    errors = 0
    for path in SOURCES:
        for fp in glob.glob(path):
            with open(fp, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = AnalysisRecord.model_validate_json(line)
                    except Exception as e:  # noqa: BLE001
                        errors += 1
                        print(f"[skip] {fp}: {type(e).__name__}: {str(e)[:80]}")
                        continue
                    # доскор детерминированным движком
                    if rec.risk_score is None and rec.risk_signals:
                        res = evaluate(rec.risk_signals)
                        rec.risk_score = res["risk_score"]
                        rec.risk_level = RiskLevel(res["risk_level"])
                    seen.setdefault(rec.id, rec)

    records = normalize(list(seen.values()))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(rec.model_dump_json(exclude_none=False) + "\n")

    print(f"\nИтог: {len(records)} строк → {OUT}  (пропущено невалидных: {errors})")
    for field in ("label", "fraud_type", "language", "modality"):
        ctr = collections.Counter(getattr(r, field) for r in records)
        pretty = {str(getattr(k, "value", k)): v for k, v in ctr.items()}
        print(f"  {field:9}: {pretty}")


if __name__ == "__main__":
    main()
