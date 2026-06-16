"""Студент 2: парсинг Telegram-экспорта или готового датасета → telegram_messages.jsonl.

ВАЖНО (ТЗ §0): только открытые/свои тестовые каналы и публичные датасеты.
Приватные чаты не парсим. Реквизиты — только маска/хэш.

Поддерживает Telegram Desktop JSON-экспорт (result.json):
    {"name": ..., "messages": [{"id", "type", "date", "from", "text", ...}, ...]}

Запуск:
    python -m src.parsers.parse_telegram_export path/to/result.json
"""

from __future__ import annotations

import json
import os
import sys


def _flatten_text(text) -> str:
    """Telegram 'text' бывает строкой или списком фрагментов/энтити."""
    if isinstance(text, str):
        return text
    if isinstance(text, list):
        parts = []
        for chunk in text:
            if isinstance(chunk, str):
                parts.append(chunk)
            elif isinstance(chunk, dict):
                parts.append(chunk.get("text", ""))
        return "".join(parts)
    return ""


def parse_export(export_path: str) -> list[dict]:
    """Прочитать Telegram Desktop JSON-экспорт → список записей (единый формат §5)."""
    with open(export_path, encoding="utf-8") as f:
        data = json.load(f)

    channel = data.get("name", "unknown")
    records = []
    for msg in data.get("messages", []):
        if msg.get("type") != "message":
            continue
        text = _flatten_text(msg.get("text", "")).strip()
        if not text:
            continue
        records.append({
            "id": f"tg_{channel}_{msg.get('id')}",
            "source": "telegram_export",
            "platform": "telegram",
            "modality": "text",
            "case_type": None,
            "language": "ru",
            "url": None,
            "title": None,
            "description": None,
            "transcript": None,
            "ocr_text": None,
            "combined_text": text,
            "entities": {},
            "media_anomalies": {},
            "risk_signals": [],
            "evidence_spans": [],
            "label": None,
            "fraud_type": None,
            "risk_level": None,
            "risk_score": None,
            "annotator": None,
            "review_status": "pending",
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
    records = parse_export(sys.argv[1])
    write_jsonl(records, "data/processed/telegram_messages.jsonl")
    print(f"Сообщений: {len(records)} → data/processed/telegram_messages.jsonl")


if __name__ == "__main__":
    main()
