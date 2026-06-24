"""Шаг 8.8 — code-switching аугментация kk↔ru через vLLM.

Реальный казахстанский фрод двуязычный: казахская основа с русскими вставками
(термины, суммы, бренды) и наоборот. Берём scam-записи KZ-релевантных типов из
единого датасета и просим модель переписать combined_text как естественный
kk-ru микс, сохраняя label/fraud_type. Резюмируемый (дозапись + skip готовых).

Запуск (vLLM на :8100):
    python -m src.synthetic.augment_codeswitch --per-type 250
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random

import httpx

from src.extraction.regex_extractors import extract_entities
from src.extraction.signal_extractor import extract_signals

SRC = "data/processed/ai_media_watch_dataset.jsonl"
OUT = "data/processed/codeswitch_kk_ru.jsonl"

# KZ-релевантные типы, где двуязычность реалистична (без крипто/гемблинг-спама)
TARGET_TYPES = {
    "fake_bank_call", "fake_egov_delivery_call", "fake_government_call", "fake_credit",
    "investment_scam", "phishing", "fake_seller", "money_mule_or_drop",
}

SYSTEM = (
    "Сен Қазақстандағы шынайы екітілді (қазақша-орысша араласқан) хабарламаларды "
    "имитациялайсың. Берілген мәтінді ҚАЗАҚ-ОРЫС code-switching түрінде қайта жаз: "
    "қазақ тілі негіз, бірақ терминдер/сома/бренд/кейбір сөйлемдер орысша аралассын — "
    "адамдар чатта/қоңырауда нақты осылай сөйлейді. Мағынаны және алаяқтық мәнін сақта. "
    "Тек қайта жазылған мәтінді қайтар, түсініктемесіз."
)


def load_done(path: str) -> set[str]:
    done = set()
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    done.add(json.loads(line)["cs_source_id"])
                except Exception:  # noqa: BLE001
                    pass
    return done


def sample_sources(per_type: int) -> list[dict]:
    by_type: dict[str, list[dict]] = {}
    for line in open(SRC, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if (r.get("label") == "scam" and r.get("fraud_type") in TARGET_TYPES
                and r.get("language") in ("ru", "kk") and (r.get("combined_text") or "").strip()):
            by_type.setdefault(r["fraud_type"], []).append(r)
    rng = random.Random(42)
    out = []
    for ft, rows in by_type.items():
        rng.shuffle(rows)
        out.extend(rows[:per_type])
    return out


async def rewrite(client: httpx.AsyncClient, model: str, text: str) -> str | None:
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
        "temperature": 0.8, "top_p": 0.95,
        "max_tokens": min(2048, max(64, int(len(text) / 2) + 128)),
    }
    for attempt in range(4):
        try:
            r = await client.post("/chat/completions", json=payload, timeout=180)
            r.raise_for_status()
            out = r.json()["choices"][0]["message"]["content"].strip()
            return out or None
        except Exception:  # noqa: BLE001
            if attempt == 3:
                return None
            await asyncio.sleep(2 * (attempt + 1))
    return None


def make_record(orig: dict, text: str) -> dict:
    entities = extract_entities(text)
    signals = extract_signals(text, entities)
    rec = dict(orig)
    rec.update({
        "id": f"cs_{orig['id']}",
        "language": "kk",  # доминирует казахская основа → засчитываем в kk-покрытие
        "combined_text": text,
        "title": None, "description": None, "transcript": None, "ocr_text": None,
        "entities": entities,
        "risk_signals": signals or orig.get("risk_signals", []),
        "source": f"{orig.get('source', '')}+codeswitch",
        "annotator": "codeswitch:qwen2.5-7b-awq",
        "review_status": "draft_synth",
        "cs_source_id": orig["id"],
    })
    return rec


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("LLM_HOST_URL", "http://localhost:8100/v1"))
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct-AWQ")
    ap.add_argument("--concurrency", type=int, default=32)
    ap.add_argument("--per-type", type=int, default=250)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    srcs = sample_sources(args.per_type)
    done = load_done(args.out)
    todo = [r for r in srcs if r["id"] not in done]
    print(f"sources: {len(srcs)} | done: {len(done)} | todo: {len(todo)}")
    if not todo:
        return

    sem = asyncio.Semaphore(args.concurrency)
    lock = asyncio.Lock()
    fout = open(args.out, "a", encoding="utf-8")
    cnt = {"ok": 0, "fail": 0}

    async with httpx.AsyncClient(base_url=args.base_url) as client:
        async def worker(orig):
            async with sem:
                txt = await rewrite(client, args.model, orig["combined_text"])
            async with lock:
                if txt:
                    fout.write(json.dumps(make_record(orig, txt), ensure_ascii=False) + "\n")
                    fout.flush(); cnt["ok"] += 1
                else:
                    cnt["fail"] += 1
                n = cnt["ok"] + cnt["fail"]
                if n % 200 == 0 or n == len(todo):
                    print(f"  {n}/{len(todo)} ok={cnt['ok']} fail={cnt['fail']}", flush=True)

        await asyncio.gather(*(worker(r) for r in todo))
    fout.close()
    print(f"Готово: ok={cnt['ok']} fail={cnt['fail']} → {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
