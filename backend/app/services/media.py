"""Media Service: видео → аудио+кадры → Whisper (ASR) + PaddleOCR (OCR).

Тяжёлые синхронные операции выносятся в asyncio.to_thread (не блокируют event loop).
Реальные ASR/OCR — в src/media (Студент 4). ffmpeg должен быть в системе
(в Docker-образе ставится, см. backend/Dockerfile).
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from dataclasses import dataclass


@dataclass
class MediaResult:
    transcript: str = ""
    ocr_text: str = ""

    @property
    def combined_text(self) -> str:
        return " ".join(p for p in (self.transcript, self.ocr_text) if p).strip()


def _extract_audio(video_path: str, out_wav: str) -> str:
    """ffmpeg: видео → 16kHz моно wav (формат, удобный для Whisper)."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-ac", "1", "-ar", "16000", "-vn", out_wav],
        check=True,
        capture_output=True,
    )
    return out_wav


def _extract_frames(video_path: str, out_dir: str, fps: float = 0.5) -> list[str]:
    """ffmpeg: кадры с заданной частотой (по умолчанию 1 кадр / 2 сек)."""
    os.makedirs(out_dir, exist_ok=True)
    pattern = os.path.join(out_dir, "frame_%04d.png")
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vf", f"fps={fps}", pattern],
        check=True,
        capture_output=True,
    )
    return sorted(
        os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.endswith(".png")
    )


def _transcribe_sync(audio_path: str, language: str | None) -> str:
    from src.media.asr_whisper import transcribe

    return transcribe(audio_path, language=language)


def _ocr_sync(frame_paths: list[str], lang: str) -> str:
    from src.media.ocr import ocr_frames

    # EasyOCR: кириллица+латиница; язык kk покрывается ru-моделью (Cyrillic).
    return ocr_frames(frame_paths, langs=("ru", "en"))


async def transcribe_audio(path: str, language: str | None = None) -> str:
    return await asyncio.to_thread(_transcribe_sync, path, language)


async def process_video(video_path: str, language: str | None = "ru") -> MediaResult:
    """Полный media-пайплайн для видео: аудио→ASR + кадры→OCR."""
    with tempfile.TemporaryDirectory() as tmp:
        wav = await asyncio.to_thread(_extract_audio, video_path, os.path.join(tmp, "a.wav"))
        frames = await asyncio.to_thread(_extract_frames, video_path, os.path.join(tmp, "frames"))
        transcript = await asyncio.to_thread(_transcribe_sync, wav, language)
        ocr_text = await asyncio.to_thread(_ocr_sync, frames, language or "ru")
    return MediaResult(transcript=transcript, ocr_text=ocr_text)
