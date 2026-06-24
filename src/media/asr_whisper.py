"""ASR: аудио → текст через faster-whisper (Студент 4, ТЗ §13).

По умолчанию large-v3 на GPU (float16) — заметно точнее на kk/ru, чем small/int8.
Модель/устройство берутся из настроек (backend.app.config) и переопределяются
переменными окружения ASR_MODEL_SIZE / ASR_DEVICE / ASR_COMPUTE_TYPE.

Запуск:
    python -m src.media.asr_whisper path/to/audio.wav [model_size]
"""

from __future__ import annotations

import sys
from functools import lru_cache


def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:  # noqa: BLE001 — torch может отсутствовать
        return "cpu"


def _resolve_compute(compute_type: str, device: str) -> str:
    if compute_type != "auto":
        return compute_type
    return "float16" if device == "cuda" else "int8"


def _defaults() -> tuple[str, str, str]:
    """(model_size, device, compute_type) из настроек; fallback на large-v3/auto."""
    try:
        from backend.app.config import get_settings

        s = get_settings()
        return s.asr_model_size, s.asr_device, s.asr_compute_type
    except Exception:  # noqa: BLE001 — конфиг может быть недоступен вне backend
        return "large-v3", "auto", "auto"


def _kk_config() -> tuple[bool, str]:
    """(enabled, model_id) казахского бэкенда из настроек."""
    try:
        from backend.app.config import get_settings

        s = get_settings()
        return s.asr_kk_enabled, s.asr_kk_model
    except Exception:  # noqa: BLE001
        return True, "shyngys879/kazakh-whisper-large-v3-turbo"


def _maybe_kk(audio_path: str, lang: str | None, device: str) -> str | None:
    """Если язык казахский и kk-бэкенд включён — вернуть транскрипт спец-моделью, иначе None."""
    if lang != "kk":
        return None
    enabled, model_id = _kk_config()
    if not enabled:
        return None
    try:
        from src.media import asr_kk

        return asr_kk.transcribe(audio_path, model_id=model_id, device=device)
    except Exception:  # noqa: BLE001 — нет transformers/модели → откат на faster-whisper
        return None


@lru_cache(maxsize=2)
def _get_model(model_size: str, device: str, compute_type: str):
    from faster_whisper import WhisperModel

    return WhisperModel(model_size, device=device, compute_type=compute_type)


def _model_for(model_size: str | None, device: str | None, compute_type: str | None):
    d_size, d_device, d_compute = _defaults()
    size = model_size or d_size
    device = _resolve_device(device or d_device)
    compute = _resolve_compute(compute_type or d_compute, device)
    return _get_model(size, device, compute), device


def transcribe(
    audio_path: str,
    model_size: str | None = None,
    language: str | None = None,
    compute_type: str | None = None,
    device: str | None = None,
) -> str:
    """Вернуть текст транскрипта .wav/.mp3. Для казахского — спец-модель (см. _maybe_kk)."""
    model, dev = _model_for(model_size, device, compute_type)
    # info.language доступен сразу после вызова (детекция языка — на первом окне).
    segments, info = model.transcribe(audio_path, language=language)
    kk = _maybe_kk(audio_path, language or info.language, dev)
    if kk is not None:
        return kk
    return " ".join(seg.text.strip() for seg in segments).strip()


def transcribe_with_segments(
    audio_path: str,
    model_size: str | None = None,
    language: str | None = None,
    compute_type: str | None = None,
    device: str | None = None,
) -> list[dict]:
    """Сегменты с таймкодами — полезно для разбиения звонка на этапы (ТЗ §2.2).

    Для казахского сегменты тоже отдаёт faster-whisper (нужны таймкоды);
    спец-модель используется только в transcribe() для итогового текста.
    """
    model, _dev = _model_for(model_size, device, compute_type)
    segments, _info = model.transcribe(audio_path, language=language)
    return [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    size = sys.argv[2] if len(sys.argv) > 2 else None
    print(transcribe(sys.argv[1], model_size=size))
