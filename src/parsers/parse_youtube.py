"""Студент 1: сбор metadata видео через YouTube Data API search.list (ТЗ §1.3 / §13).

Сохраняет youtube_candidates.csv с колонками:
    source,platform,query,video_id,url,title,description,channel_title,published_at,thumbnail_url
и нормализует в youtube_candidates_clean.jsonl (единый формат ТЗ §5).

Ключ API — из переменной окружения YOUTUBE_API_KEY (не коммитить).
Запуск:
    YOUTUBE_API_KEY=... python -m src.parsers.parse_youtube
"""

from __future__ import annotations

import csv
import json
import os

import httpx

API_URL = "https://www.googleapis.com/youtube/v3/search"

CSV_HEADER = [
    "source", "platform", "query", "video_id", "url", "title",
    "description", "channel_title", "published_at", "thumbnail_url",
]

# Поисковые запросы из ТЗ §1.3
QUERIES = [
    "онлайн казино промокод",
    "казино бонус промокод",
    "слоты промокод",
    "выигрыш казино промокод",
    "депозит бонус казино",
    "вывод денег казино",
    "ставки промокод",
    "казино ссылка в описании",
    "заработок казино",
]


def search(query: str, api_key: str, max_results: int = 25) -> list[dict]:
    """Вызов YouTube Data API search.list. Возвращает строки под CSV_HEADER.

    quota: search.list стоит 100 единиц за запрос (см. quota calculator из ТЗ §3.2).
    """
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": min(max_results, 50),  # API лимит 50 на страницу
        "key": api_key,
    }
    resp = httpx.get(API_URL, params=params, timeout=30)
    resp.raise_for_status()
    rows = []
    for item in resp.json().get("items", []):
        snip = item.get("snippet", {})
        vid = item.get("id", {}).get("videoId")
        if not vid:
            continue
        rows.append({
            "source": "youtube_api",
            "platform": "youtube",
            "query": query,
            "video_id": vid,
            "url": f"https://youtube.com/watch?v={vid}",
            "title": snip.get("title", ""),
            "description": snip.get("description", ""),
            "channel_title": snip.get("channelTitle", ""),
            "published_at": snip.get("publishedAt", ""),
            "thumbnail_url": snip.get("thumbnails", {}).get("default", {}).get("url", ""),
        })
    return rows


def to_record(row: dict) -> dict:
    """CSV-строка → единый JSONL-формат ТЗ §5 (без разметки — её делает аннотатор)."""
    combined = " ".join(p for p in (row.get("title"), row.get("description")) if p).strip()
    return {
        "id": f"youtube_{row['video_id']}",
        "source": row["source"],
        "platform": "youtube",
        "modality": "video",
        "case_type": None,
        "language": "ru",
        "url": row["url"],
        "title": row.get("title"),
        "description": row.get("description"),
        "transcript": None,
        "ocr_text": None,
        "combined_text": combined,
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
    }


def write_csv(rows: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(rows: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(to_record(row), ensure_ascii=False) + "\n")


def main() -> None:
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise SystemExit("Задайте YOUTUBE_API_KEY")
    all_rows: list[dict] = []
    for query in QUERIES:
        try:
            all_rows.extend(search(query, api_key))
        except httpx.HTTPError as e:  # noqa: PERF203
            print(f"[warn] '{query}': {e}")
    # дедуп по video_id
    seen: dict[str, dict] = {r["video_id"]: r for r in all_rows}
    rows = list(seen.values())
    write_csv(rows, "data/raw/youtube/youtube_candidates.csv")
    write_jsonl(rows, "data/processed/youtube_candidates_clean.jsonl")
    print(f"Собрано уникальных видео: {len(rows)}")


if __name__ == "__main__":
    main()
