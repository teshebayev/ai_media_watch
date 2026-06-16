"""Студент 5: синтетические KZ-звонки eGov/КНБ/банк → kz_call_transcripts.jsonl.

Сценарии строятся ТОЛЬКО на основе официальных предупреждений eGov/Нацбанка (ТЗ §2.3).
Реальные записи звонков жертв не используются (ТЗ §0).

Вход: kz_call_scripts.csv с колонками минимум `id,language,text`
(опционально `case_type`). На выходе — предразмеченные записи единого формата §5:
regex-сущности + базовые risk_signals + детекция этапов звонка (ТЗ §2.2).

Запуск:
    python -m src.parsers.parse_kz_calls data/raw/kz_calls/kz_call_scripts.csv
"""

from __future__ import annotations

import csv
import json
import os
import sys

from src.extraction.regex_extractors import extract_entities
from src.extraction.signal_extractor import detect_call_stages, extract_signals

# Ключевые слова сценария (ТЗ §2.4) — ru + kz
RU_KEYWORDS = [
    "доставка от eGov", "код из SMS", "код 1414", "сотрудник КНБ", "служба безопасности",
    "на вас оформляют кредит", "безопасный счёт", "не кладите трубку", "никому не говорите",
    "удалённый доступ", "AnyDesk", "TeamViewer", "RustDesk",
]
KZ_KEYWORDS = [
    "қауіпсіз шот", "несие рәсімделді", "банк қызметкері", "полиция қызметкері",
    "ұлттық банк", "SMS кодын айтыңыз", "қосымшаны орнатыңыз", "ешкімге айтпаңыз", "шұғыл",
]


def load_scripts(csv_path: str) -> list[dict]:
    """Прочитать kz_call_scripts.csv → предразмеченные записи (единый формат §5)."""
    records = []
    with open(csv_path, encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            text = (row.get("text") or "").strip()
            if not text:
                continue
            entities = extract_entities(text)
            signals = extract_signals(text, entities)
            stages = detect_call_stages(text)
            records.append({
                "id": row.get("id") or f"kz_call_{i:04d}",
                "source": "synthetic_based_on_official_warning",
                "platform": "phone",
                "modality": "text",  # станет audio после озвучки + Whisper
                "case_type": row.get("case_type") or "fake_egov_delivery_call",
                "language": row.get("language") or "ru",
                "url": None,
                "title": None,
                "description": None,
                "transcript": text,
                "ocr_text": None,
                "combined_text": text,
                "entities": entities,
                "media_anomalies": {},
                "risk_signals": signals,
                "evidence_spans": [],
                "label": "scam" if signals else "unclear",
                "fraud_type": row.get("case_type") or "fake_egov_delivery_call",
                "risk_level": None,
                "risk_score": None,
                "annotator": "student_05",
                "review_status": "pending",
                "call_stages": stages,  # доп. поле: этапы звонка (ТЗ §2.2)
            })
    return records


def write_jsonl(records: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(1)
    records = load_scripts(sys.argv[1])
    write_jsonl(records, "data/processed/kz_call_transcripts.jsonl")
    print(f"Сценариев: {len(records)} → data/processed/kz_call_transcripts.jsonl")


if __name__ == "__main__":
    main()
