"""ASR: аудио → текст через faster-whisper (Студент 4, ТЗ §13).

План «Риски»: для скорости — модель small, int8; для демо можно отдавать заранее
посчитанные транскрипты.

Запуск:
    python -m src.media.asr_whisper path/to/audio.wav [model_size]
"""

from __future__ import annotations

import sys
from functools import lru_cache


@lru_cache(maxsize=2)
def _get_model(model_size: str, compute_type: str):
    from faster_whisper import WhisperModel

    # device="auto" сам выберет cuda при наличии; на занятом GPU укажите device="cpu".
    return WhisperModel(model_size, compute_type=compute_type)


def transcribe(
    audio_path: str,
    model_size: str = "small",
    language: str | None = None,
    compute_type: str = "int8",
) -> str:
    """Вернуть текст транскрипта .wav/.mp3."""
    model = _get_model(model_size, compute_type)
    segments, _info = model.transcribe(audio_path, language=language)
    return " ".join(seg.text.strip() for seg in segments).strip()


def transcribe_with_segments(
    audio_path: str,
    model_size: str = "small",
    language: str | None = None,
    compute_type: str = "int8",
) -> list[dict]:
    """Сегменты с таймкодами — полезно для разбиения звонка на этапы (ТЗ §2.2)."""
    model = _get_model(model_size, compute_type)
    segments, _info = model.transcribe(audio_path, language=language)
    return [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    size = sys.argv[2] if len(sys.argv) > 2 else "small"
    print(transcribe(sys.argv[1], model_size=size))
