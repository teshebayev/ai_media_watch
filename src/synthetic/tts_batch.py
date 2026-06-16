"""Этап 8.2 — батч-озвучка сценариев в .wav + авторазметка (self-labeled синтетика).

csv сценариев (из gen_call_scripts.py) → data/raw/kz_calls/*.wav + строки JSONL с
modality: audio, source: synthetic_tts, media_anomalies.synthetic_voice_suspected: true.
Метка ставится по построению — аудио синтетическое, значит сигнал верен (Этап 8, ground-truth).

Бэкенд TTS — Meta MMS-TTS (VITS) через transformers, на CPU:
  - ru → facebook/mms-tts-rus
  - kk → facebook/mms-tts-kaz
Один стек с NER (transformers+torch), модели грузятся лениво и кешируются.

Запуск:
    python -m src.synthetic.tts_batch data/raw/kz_calls/kz_call_scripts.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import wave
from functools import lru_cache

from src.extraction.regex_extractors import extract_entities
from src.extraction.signal_extractor import extract_signals

WAV_DIR = "data/raw/kz_calls"
JSONL_OUT = "data/processed/kz_call_transcripts.jsonl"

MMS_MODELS = {"ru": "facebook/mms-tts-rus", "kk": "facebook/mms-tts-kaz"}


# --- TTS-бэкенд: MMS-TTS (VITS) на CPU, ленивая загрузка --------------------

@lru_cache(maxsize=2)
def _load_mms(language: str):
    import torch
    from transformers import AutoTokenizer, VitsModel

    torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
    name = MMS_MODELS.get(language, MMS_MODELS["ru"])
    model = VitsModel.from_pretrained(name).to("cpu").eval()
    tokenizer = AutoTokenizer.from_pretrained(name)
    return model, tokenizer


def _save_wav(waveform, sample_rate: int, out_wav: str) -> None:
    """Float-волну [-1..1] → 16-bit PCM wav стандартным модулем wave (без scipy)."""
    import numpy as np

    audio = np.asarray(waveform, dtype="float32").squeeze()
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767.0).astype("<i2")
    with wave.open(out_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


def synthesize(text: str, language: str, out_wav: str) -> None:
    import torch

    model, tokenizer = _load_mms(language if language in MMS_MODELS else "ru")
    inputs = tokenizer(text, return_tensors="pt")
    with torch.no_grad():
        waveform = model(**inputs).waveform  # (1, T) float
    _save_wav(waveform.cpu().numpy(), model.config.sampling_rate, out_wav)


# --- Батч + авторазметка -----------------------------------------------------

def to_record(row: dict, wav_path: str) -> dict:
    """Строка сценария + путь wav → запись единого формата §5 с авторазметкой."""
    text = row["text"]
    entities = extract_entities(text)
    return {
        "id": row["id"],
        "source": "synthetic_tts",
        "platform": "phone",
        "modality": "audio",
        "case_type": row.get("case_type"),
        "language": row.get("language", "ru"),
        "url": wav_path,
        "title": None,
        "description": None,
        "transcript": text,  # ground-truth текст (что озвучивали)
        "ocr_text": None,
        "combined_text": text,
        "entities": entities,
        "media_anomalies": {
            "has_face": False,
            "possible_deepfake": False,
            "synthetic_voice_suspected": True,  # по построению (Этап 8)
            "lip_sync_anomaly": False,
        },
        "risk_signals": extract_signals(text, entities),
        "evidence_spans": [],
        "label": "scam",
        "fraud_type": row.get("case_type"),
        "risk_level": None,
        "risk_score": None,
        "annotator": "synthetic",
        "review_status": "pending",
    }


def run(csv_path: str, *, do_tts: bool = True, limit: int | None = None) -> list[dict]:
    os.makedirs(WAV_DIR, exist_ok=True)
    records = []
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for i, row in enumerate(rows):
        wav_path = os.path.join(WAV_DIR, f"{row['id']}.wav")
        # limit ограничивает только синтез wav; авторазметка JSONL делается для всех строк
        if do_tts and (limit is None or i < limit):
            synthesize(row["text"], row.get("language", "ru"), wav_path)
        records.append(to_record(row, wav_path))
    os.makedirs(os.path.dirname(JSONL_OUT), exist_ok=True)
    with open(JSONL_OUT, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--no-tts", action="store_true",
                        help="только авторазметка JSONL, без синтеза wav")
    parser.add_argument("--limit", type=int, default=None,
                        help="озвучить только первые N строк (smoke-прогон)")
    args = parser.parse_args()
    records = run(args.csv_path, do_tts=not args.no_tts, limit=args.limit)
    print(f"Озвучено/размечено: {len(records)} → {JSONL_OUT}")


if __name__ == "__main__":
    main()
