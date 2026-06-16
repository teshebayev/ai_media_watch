"""Интеграция датасета Stop-Piramida.kz (официальный источник ТЗ §3.1).

Читает release/videos.csv из соседнего репозитория stop-piramida-dataset
(593 видео, 17 категорий мошенничества, ~415 скачанных mp4) и нормализует в единый
формат §5 → data/processed/stop_piramida.jsonl.

ВАЖНО по разметке: это официальные ПРЕДУПРЕЖДЕНИЯ о схемах. Пока видео не
транскрибированы, ставим label=unclear + review_status=needs_transcription
(educational-категорию — legit), чтобы не выучить «предупреждение = scam».
fraud_type — тематическая категория (надёжна: видео точно ПРО эту схему).
media_path — путь к локальному mp4 для последующей транскрибации (Whisper).

Запуск:
    python -m src.parsers.parse_stop_piramida [--dataset-dir ~/stop-piramida-dataset]
"""

from __future__ import annotations

import argparse
import csv
import json
import os

from src.extraction.regex_extractors import extract_entities
from src.extraction.signal_extractor import extract_signals

# Категория Stop-Piramida → fraud_type (§7). None — нет уверенного соответствия.
CATEGORY_MAP: dict[str, str | None] = {
    "dropperstvo": "money_mule_or_drop",
    "fejkovyie-vyiplatyi": "phishing",
    "finansovyie-piramidyi": "investment_scam",
    "fishing": "phishing",
    "kriptoriski": "crypto_scam",
    "lzhe-kredityi": "fake_credit",
    "lzheprodavczyi": "fake_seller",
    "lzheturizm": "fake_seller",
    "lzhexalyal": "investment_scam",
    "lzheyuristyi": "fake_seller",
    "lzhezarabotok": "investment_scam",
    "rabota-za-graniczej": "fake_seller",
    "riski-v-setevom-marketinge": "investment_scam",
    "roditelyam-na-zametku": "anti_fraud_education",
    "romanticheskoe-moshennichestvo": "investment_scam",
    "stop-mfo": "fake_credit",
    "telefonnoe-moshennichestvo": "fake_government_call",
}
EDU_CATEGORIES = {"roditelyam-na-zametku"}

DEFAULT_DIR = os.path.expanduser("~/stop-piramida-dataset")


def to_record(row: dict, dataset_dir: str) -> dict:
    category = row.get("category", "")
    title = (row.get("title") or "").strip()
    desc = (row.get("description") or "").strip()
    combined = ". ".join(p for p in (title, desc) if p)
    entities = extract_entities(combined)
    is_edu = category in EDU_CATEGORIES

    # media_path — по ФАКТУ наличия файла на диске (флаг downloaded в csv устаревает,
    # т.к. загрузка идёт после генерации release/videos.csv).
    rel = row.get("file") or f"outputs/videos/{category}/{row.get('vimeo_id')}.mp4"
    candidate = os.path.join(dataset_dir, rel)
    media_path = candidate if os.path.exists(candidate) else None

    return {
        "id": f"sp_{row.get('vimeo_id')}",
        "source": "stop_piramida",
        "platform": "vimeo",
        "modality": "video",
        "case_type": category,  # сохраняем оригинальный slug-таксономии
        "language": "ru",
        "url": row.get("page_url") or row.get("vimeo_url"),
        "media_path": media_path,
        "title": title or None,
        "description": desc or None,
        "transcript": None,  # появится после транскрибации
        "ocr_text": None,
        "combined_text": combined,
        "entities": entities,
        "media_anomalies": {},
        "risk_signals": extract_signals(combined, entities),
        "evidence_spans": [],
        "label": "legit" if is_edu else "unclear",
        "fraud_type": CATEGORY_MAP.get(category),
        "risk_level": None,
        "risk_score": None,
        "annotator": "stop_piramida",
        "review_status": "needs_transcription",
    }


def parse(dataset_dir: str) -> list[dict]:
    csv_path = os.path.join(dataset_dir, "release", "videos.csv")
    with open(csv_path, encoding="utf-8") as f:
        return [to_record(row, dataset_dir) for row in csv.DictReader(f)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", default=DEFAULT_DIR)
    parser.add_argument("--out", default="data/processed/stop_piramida.jsonl")
    args = parser.parse_args()

    records = parse(args.dataset_dir)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    import collections
    have_media = sum(1 for r in records if r["media_path"])
    print(f"Stop-Piramida: {len(records)} видео → {args.out}")
    print(f"  с локальным mp4 (готовы к транскрибации): {have_media}")
    print(f"  по fraud_type: {dict(collections.Counter(r['fraud_type'] for r in records))}")


if __name__ == "__main__":
    main()
