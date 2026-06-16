"""Роутеры /analyze/*.

- /analyze/text  — синхронно end-to-end (regex + LLM + similarity + graph + risk).
- /analyze/url   — ссылка (YouTube/HTML/Telegram) → извлечение текста → пайплайн.
- /analyze/audio — звонок → Whisper → детекция этапов → пайплайн.
- /analyze/video — видео → ffmpeg (аудио+кадры) → Whisper + OCR → пайплайн.

Медиа-эндпоинты тяжёлые: для хакатона работают синхронно на одном файле. При росте
нагрузки выносить в фоновую задачу с job-таблицей (план, этап 3).
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import time

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from backend.app.api.deps import get_db, get_llm, get_neo4j, get_qdrant
from backend.app.config import get_settings
from backend.app.schemas.models import AnalystReport
from backend.app.services import ingest as ingest_svc
from backend.app.services import media as media_svc
from backend.app.services import pipeline
from backend.app.services import sessions as sessions_svc
from src.extraction.signal_extractor import detect_call_stages

router = APIRouter(prefix="/analyze", tags=["analyze"])


async def _persist(db, report, *, modality, source, input_url, text_preview, language, t0):
    """Best-effort запись сеанса в Postgres (не валит анализ при сбое БД)."""
    try:
        return await sessions_svc.save_session(
            db, report, modality=modality, source=source, input_url=input_url,
            text_preview=text_preview, language=language,
            llm_used=get_settings().enable_llm,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
    except Exception:  # noqa: BLE001
        return None


class TextRequest(BaseModel):
    id: str
    text: str


class UrlRequest(BaseModel):
    url: str
    deep: bool = False  # для видео: скачать низкокач. копию и OCR-ить кадры


async def _save_upload(file: UploadFile, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(await file.read())
    return path


@router.post("/text", response_model=AnalystReport)
async def analyze_text(
    req: TextRequest,
    llm=Depends(get_llm),
    qdrant=Depends(get_qdrant),
    neo4j=Depends(get_neo4j),
    db=Depends(get_db),
) -> AnalystReport:
    t0 = time.perf_counter()
    report = await pipeline.analyze_text(req.id, req.text, llm=llm, qdrant=qdrant, neo4j=neo4j)
    await _persist(db, report, modality="text", source="text", input_url=None,
                   text_preview=req.text, language=None, t0=t0)
    return report


@router.post("/url")
async def analyze_url(
    req: UrlRequest,
    llm=Depends(get_llm),
    qdrant=Depends(get_qdrant),
    neo4j=Depends(get_neo4j),
    db=Depends(get_db),
) -> dict:
    """Ссылка (YouTube/HTML/Telegram) → извлечение текста → пайплайн."""
    t0 = time.perf_counter()
    try:
        data = await ingest_svc.ingest_url(req.url, deep=req.deep)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"не удалось извлечь контент: {e}") from e

    record_id = "url_" + hashlib.sha1(data["url"].encode()).hexdigest()[:12]
    report = await pipeline.analyze_text(
        record_id, data["combined_text"], language=data.get("language", "ru"),
        llm=llm, qdrant=qdrant, neo4j=neo4j,
    )
    session_id = await _persist(
        db, report, modality=data.get("modality", "url"), source=data.get("platform"),
        input_url=data.get("url"), text_preview=data["combined_text"][:500],
        language=data.get("language"), t0=t0)
    return {
        "session_id": session_id,
        "extracted": {
            "platform": data.get("platform"),
            "modality": data.get("modality"),
            "language": data.get("language"),
            "title": data.get("title"),
            "description": data.get("description"),
            "channel": data.get("channel"),
            "has_transcript": bool(data.get("transcript")),
            "ocr_text": data.get("ocr_text"),
            "ocr_note": data.get("ocr_note"),
            "duration": data.get("duration"),
            "url": data.get("url"),
        },
        "combined_text_preview": data["combined_text"][:500],
        "report": report.model_dump(),
    }


@router.post("/audio")
async def analyze_audio(
    file: UploadFile,
    llm=Depends(get_llm),
    qdrant=Depends(get_qdrant),
    neo4j=Depends(get_neo4j),
    db=Depends(get_db),
) -> dict:
    t0 = time.perf_counter()
    path = await _save_upload(file, os.path.splitext(file.filename or "a.wav")[1] or ".wav")
    try:
        transcript = await media_svc.transcribe_audio(path)
    finally:
        os.unlink(path)
    record_id = f"audio_{os.path.basename(file.filename or 'call')}"
    report = await pipeline.analyze_text(
        record_id, transcript, llm=llm, qdrant=qdrant, neo4j=neo4j
    )
    session_id = await _persist(db, report, modality="audio", source="phone", input_url=None,
                                text_preview=transcript, language="ru", t0=t0)
    return {
        "session_id": session_id,
        "transcript": transcript,
        "call_stages": detect_call_stages(transcript),  # этапы звонка (ТЗ §2.2)
        "report": report.model_dump(),
    }


@router.post("/video")
async def analyze_video(
    file: UploadFile,
    llm=Depends(get_llm),
    qdrant=Depends(get_qdrant),
    neo4j=Depends(get_neo4j),
    db=Depends(get_db),
) -> dict:
    t0 = time.perf_counter()
    path = await _save_upload(file, os.path.splitext(file.filename or "v.mp4")[1] or ".mp4")
    try:
        media = await media_svc.process_video(path)
    finally:
        os.unlink(path)
    record_id = f"video_{os.path.basename(file.filename or 'clip')}"
    report = await pipeline.analyze_text(
        record_id, media.combined_text, llm=llm, qdrant=qdrant, neo4j=neo4j
    )
    session_id = await _persist(db, report, modality="video", source="upload", input_url=None,
                                text_preview=media.combined_text, language="ru", t0=t0)
    return {
        "session_id": session_id,
        "transcript": media.transcript,
        "ocr_text": media.ocr_text,
        "report": report.model_dump(),
    }
