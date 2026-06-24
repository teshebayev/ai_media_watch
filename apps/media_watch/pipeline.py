"""Пайплайн AI Media Watch (контент) — высокоуровневая точка входа продукта.

Параллелен `apps/digital_shadow/pipeline.py`, но для медиа-контента. Оркестрация реализована
в backend (использует клиентов vLLM/Qdrant/Neo4j, поднятые в lifespan `apps.media_watch.app`):

    источник (текст / ссылка / аудио / видео)
      → ingest (yt-dlp/httpx)  ·  media (ffmpeg → Whisper ASR + EasyOCR)
      → combined_text
      → entities (regex + NER + LLM)  →  scenario (LLM → fraud_type)
      → similarity (Qdrant)  +  graph (Neo4j)  +  deepfake  +  OSINT
      → risk_engine (§11)  →  Analyst Report  →  Postgres

Ниже — реэкспорт ключевых шагов как единая поверхность «media pipeline».
"""

from __future__ import annotations

# Deepfake-аномалии видео → риск-сигналы
from backend.app.services.deepfake import analyze_video_file, anomalies_to_signals

# Ingest по ссылке (YouTube/Instagram/TikTok/HTML/Telegram)
from backend.app.services.ingest import cleanup_media_path, ingest_url

# Медиа: аудио/видео → текст
from backend.app.services.media import process_video, transcribe_audio

# Ядро оркестрации текста (entities → scenario → similarity → graph → risk → report)
from backend.app.services.pipeline import analyze_text

__all__ = [
    "analyze_text",
    "ingest_url", "cleanup_media_path",
    "transcribe_audio", "process_video",
    "analyze_video_file", "anomalies_to_signals",
]
