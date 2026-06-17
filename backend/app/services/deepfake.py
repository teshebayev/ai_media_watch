"""Deepfake-детектор: вызывает внешний детектор (репо fakeface-deepfake-detector)
в ЕГО venv через subprocess — изоляция от конфликта зависимостей
(их transformers 4.49 / torch 2.6 vs наши 5.12 / 2.12).

Контракт `media_anomalies` совпадает с нашей схемой §5:
  has_face, possible_deepfake, synthetic_voice_suspected, lip_sync_anomaly
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess

from backend.app.config import get_settings


def _run_sync(video_path: str) -> dict:
    s = get_settings()
    py = os.path.abspath(s.deepfake_python)   # абсолютные пути — subprocess резолвит exe от cwd родителя
    cwd = os.path.abspath(s.deepfake_dir)
    proc = subprocess.run(
        [py, "-m", "src.media.fakeface_detector_real", "--video", os.path.abspath(video_path)],
        cwd=cwd, capture_output=True, text=True, timeout=s.deepfake_timeout,
    )
    out = proc.stdout.strip()
    if not out:
        return {}
    # детектор печатает JSON {"media_anomalies": {...}, "details": {...}}
    start = out.find("{")
    if start < 0:
        return {}
    try:
        data = json.loads(out[start:])
    except json.JSONDecodeError:
        return {}
    return data.get("media_anomalies", {}) or {}


async def analyze_video_file(path: str) -> dict:
    """media_anomalies для видео-файла. Best-effort: {} при выключенном/недоступном детекторе."""
    if not get_settings().enable_deepfake:
        return {}
    try:
        return await asyncio.to_thread(_run_sync, path)
    except Exception:  # noqa: BLE001
        return {}


def anomalies_to_signals(anomalies: dict) -> list[str]:
    """media_anomalies → risk_signals (веса уже есть в risk_engine §11)."""
    out = []
    if anomalies.get("possible_deepfake"):
        out.append("possible_deepfake")
    if anomalies.get("synthetic_voice_suspected"):
        out.append("synthetic_voice_suspected")
    if anomalies.get("lip_sync_anomaly"):
        out.append("lip_sync_anomaly")
    return out
