"""Студент 3: нормализация готовых датасетов → ready_dataset_examples.jsonl.

Источники (ТЗ §3.3): ScamSpot, ealvaradob/phishing-dataset, CryptoScamDB,
Telegram Spam or Ham. Каждый приводится к единому формату ТЗ §5.

Запуск:
    python -m src.parsers.parse_ready_datasets <source> <path.csv|path.jsonl> [out.jsonl]
    source ∈ {scamspot, phishing, cryptoscamdb, telegram_spam}
"""

from __future__ import annotations

import csv
import json
import os
import sys

# Сопоставление сырых меток источника → label/fraud_type единого формата (ТЗ §6/§7).
SOURCE_DEFAULTS = {
    "scamspot": ("spam", "ordinary_spam"),
    "phishing": ("scam", "phishing"),
    "cryptoscamdb": ("scam", "crypto_scam"),
    "telegram_spam": ("spam", "ordinary_spam"),
}


def _base_record(idx: int, source: str, text: str, modality: str = "text") -> dict:
    label, fraud_type = SOURCE_DEFAULTS.get(source, (None, None))
    return {
        "id": f"{source}_{idx:04d}",
        "source": "ready_dataset",
        "platform": "dataset",
        "modality": modality,
        "case_type": fraud_type,
        "language": "en",
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
        "label": label,
        "fraud_type": fraud_type,
        "risk_level": None,
        "risk_score": None,
        "annotator": f"ready:{source}",
        "review_status": "pending",
    }


def normalize(records: list[dict], source: str) -> list[dict]:
    """Привести произвольные записи готового датасета к единому JSONL-формату.

    Эвристика по полям: текст ищем в text/comment/message/body, URL — в url/link.
    Если в исходной записи есть метка (label/is_scam/phishing) — мапим в label/fraud_type.
    """
    out = []
    for i, rec in enumerate(records):
        text = (
            rec.get("text")
            or rec.get("comment")
            or rec.get("message")
            or rec.get("body")
            or rec.get("url")
            or rec.get("link")
            or ""
        )
        if not str(text).strip():
            continue
        norm = _base_record(i, source, str(text).strip(),
                            modality="url" if source in {"phishing", "cryptoscamdb"} else "text")

        url = rec.get("url") or rec.get("link")
        if url:
            norm["url"] = url
            norm["entities"] = {"urls": [url]}

        # Перенос исходной метки, если есть
        raw_label = rec.get("label") or rec.get("class")
        if isinstance(raw_label, str):
            low = raw_label.lower()
            if low in {"scam", "spam", "legit", "unclear"}:
                norm["label"] = low
            elif low in {"phishing", "bad", "malicious", "1"}:
                norm["label"] = "scam"
            elif low in {"legitimate", "ham", "good", "0"}:
                norm["label"] = "legit"
        out.append(norm)
    return out


def _read_any(path: str) -> list[dict]:
    if path.endswith(".jsonl"):
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    if path.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else data.get("data", [])
    # CSV по умолчанию
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(1)
    source, path = sys.argv[1], sys.argv[2]
    out_path = sys.argv[3] if len(sys.argv) > 3 else "data/processed/ready_dataset_examples.jsonl"
    records = normalize(_read_any(path), source)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Нормализовано {len(records)} записей ({source}) → {out_path}")


if __name__ == "__main__":
    main()
