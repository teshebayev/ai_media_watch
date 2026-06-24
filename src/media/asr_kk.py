"""Казахский ASR-бэкенд: Whisper, дообученный под kk (по умолчанию
shyngys879/kazakh-whisper-large-v3-turbo), через transformers-pipeline.

Зачем отдельно от faster-whisper: на kk дообученная модель заметно точнее
(числа прописью, термины), а turbo в faster-whisper теряет сегменты на длинном
аудио — transformers с chunk_length_s транскрибирует целиком. Роутинг — в
asr_whisper.transcribe(): faster-whisper определяет язык, для kk зовётся этот модуль.

Модель/устройство — из настроек (ASR_KK_MODEL), GPU при наличии.
"""

from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def _get_pipeline(model_id: str, device: str):
    import torch
    from transformers import pipeline

    dev = 0 if device == "cuda" else -1
    dtype = torch.float16 if device == "cuda" else torch.float32
    return pipeline(
        "automatic-speech-recognition", model=model_id, device=dev, torch_dtype=dtype)


def transcribe(audio_path: str, *, model_id: str, device: str = "cuda") -> str:
    """Транскрипт казахского аудио. chunk_length_s=30 — чтобы не терять сегменты."""
    pipe = _get_pipeline(model_id, device)
    out = pipe(
        audio_path, chunk_length_s=30,
        generate_kwargs={"language": "kazakh", "task": "transcribe"})
    return (out.get("text") or "").strip()
