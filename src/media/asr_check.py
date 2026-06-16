"""Этап 8.2/8.4 — петля проверки: синтетические wav → Whisper (CPU) → сверка с ground-truth.

Берёт kz_call_transcripts.jsonl (поле transcript = что озвучивали, url = путь к wav),
транскрибирует каждый wav на CPU и считает WER по языкам. Заодно проверяет, тянет ли
Whisper казахский (Этап 8.4: если WER высокий — переключать kk на Soyle).

Выход: data/processed/asr_check.jsonl (ground_truth, asr, wer) + сводка в stdout.

Запуск (CPU):
    CUDA_VISIBLE_DEVICES="" python -m src.media.asr_check [--model small] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import re

IN_JSONL = "data/processed/kz_call_transcripts.jsonl"
OUT_JSONL = "data/processed/asr_check.jsonl"

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def _norm(text: str) -> list[str]:
    return _PUNCT.sub(" ", text.lower()).split()


def wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate через расстояние Левенштейна по словам."""
    r, h = _norm(reference), _norm(hypothesis)
    if not r:
        return 0.0 if not h else 1.0
    d = [[0] * (len(h) + 1) for _ in range(len(r) + 1)]
    for i in range(len(r) + 1):
        d[i][0] = i
    for j in range(len(h) + 1):
        d[0][j] = j
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            cost = 0 if r[i - 1] == h[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
    return d[len(r)][len(h)] / len(r)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="small")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    from src.media.asr_whisper import transcribe

    rows = [json.loads(line) for line in open(IN_JSONL, encoding="utf-8")]
    if args.limit:
        rows = rows[: args.limit]

    by_lang: dict[str, list[float]] = {}
    out = []
    for i, row in enumerate(rows, 1):
        wav = row.get("url")
        gt = row.get("transcript", "")
        lang = row.get("language", "ru")
        try:
            asr = transcribe(wav, model_size=args.model, language=lang)
        except Exception as e:  # noqa: BLE001
            asr = ""
            print(f"[warn] {row['id']}: {type(e).__name__}: {e}")
        score = wer(gt, asr)
        by_lang.setdefault(lang, []).append(score)
        out.append({"id": row["id"], "language": lang, "ground_truth": gt,
                    "asr": asr, "wer": round(score, 3)})
        if i % 20 == 0:
            print(f"  ...{i}/{len(rows)}")

    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for rec in out:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print("\n=== WER по языкам (ниже — лучше) ===")
    for lang, scores in sorted(by_lang.items()):
        avg = sum(scores) / len(scores)
        print(f"  {lang}: mean WER = {avg:.3f}  (n={len(scores)})")
    print(f"\nДетали → {OUT_JSONL}")


if __name__ == "__main__":
    main()
