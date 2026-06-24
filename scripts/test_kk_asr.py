"""Прогон казахского ASR (Soyle-эквивалент: Whisper-turbo, дообученный на ISSAI KSC2)
на наших синтетических kk-звонках. Замер: WER против ground-truth, VRAM, время.

Запуск: CUDA_VISIBLE_DEVICES=0 PYTHONPATH=. .venv/bin/python scripts/test_kk_asr.py
"""

import json
import os
import time
import wave

import numpy as np
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

from src.media.asr_check import wer  # word-level WER

MODEL = os.getenv("KK_ASR_MODEL", "Uali/whisper-turbo-ksc2-kazakh-finetuned")
N = int(os.getenv("KK_N", "12"))


def read_wav(path: str):
    with wave.open(path) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype("float32") / 32768.0
        return a, w.getframerate()


def main():
    rows = [json.loads(l) for l in open("data/processed/kz_call_transcripts.jsonl", encoding="utf-8")]
    kk = [r for r in rows if r.get("language") == "kk" and r.get("url") and os.path.exists(r["url"])][:N]
    print(f"kk-сэмплов: {len(kk)} | модель: {MODEL}")

    t0 = time.time()
    proc = AutoProcessor.from_pretrained(MODEL)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(MODEL, torch_dtype=torch.float16).to("cuda").eval()
    pipe = pipeline("automatic-speech-recognition", model=model, tokenizer=proc.tokenizer,
                    feature_extractor=proc.feature_extractor, torch_dtype=torch.float16, device="cuda")
    print(f"модель загружена за {time.time()-t0:.0f} c")
    # форсируем kk через старый механизм (generation_config фичтюна без lang-маппинга)
    try:
        forced = proc.get_decoder_prompt_ids(language="kazakh", task="transcribe")
    except Exception:  # noqa: BLE001
        forced = None
    gkw = {"forced_decoder_ids": forced} if forced else {}

    wers, infer_t, audio_s = [], 0.0, 0.0
    for r in kk:
        a, sr = read_wav(r["url"])
        audio_s += len(a) / sr
        t = time.time()
        try:
            out = pipe({"raw": a, "sampling_rate": sr}, generate_kwargs=gkw)
            hyp = out["text"].strip()
        except Exception as e:  # noqa: BLE001
            hyp = ""
            print("  [warn]", r["id"], type(e).__name__, str(e)[:80])
        infer_t += time.time() - t
        w = wer(r["transcript"], hyp)
        wers.append(w)
    print("\nпример:")
    print("  GT :", kk[0]["transcript"][:90])
    print("  ASR:", pipe({"raw": read_wav(kk[0]["url"])[0], "sampling_rate": 16000}, generate_kwargs=gkw)["text"][:90])
    vram = torch.cuda.max_memory_allocated() / 1e9
    print(f"\n=== ИТОГ (kk Whisper-KSC2) ===")
    print(f"  mean WER : {sum(wers)/len(wers):.3f}  (Whisper small ранее было ~0.91)")
    print(f"  VRAM peak: {vram:.2f} ГБ")
    print(f"  время    : {infer_t:.1f} c на {audio_s:.0f} c аудио  →  {infer_t/audio_s:.2f}× RT")
    print("KK_ASR_OK")


if __name__ == "__main__":
    main()
