"""Шаг 8.6 — машинный перевод ru-scam → kk через vLLM (OpenAI-совместимый API).

Берём из единого датасета строки language=ru & label=scam, переводим combined_text
на казахский и пишем новые kk-записи (id = kktr_<orig>, source += '+mt_kk').
Скрипт РЕЗЮМИРУЕМЫЙ: при повторном запуске пропускает уже переведённые id.

Запуск (на хосте, vLLM на :8100):
    python -m src.translate_kk --concurrency 48
    python -m src.translate_kk --limit 200          # пробный прогон
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import httpx

SRC = "data/processed/ai_media_watch_dataset.jsonl"
OUT = "data/processed/kk_translated_from_ru.jsonl"

SYSTEM = (
    "Сен — кәсіби аудармашысың. Қолданушы мәтінін орыс тілінен қазақ тіліне аудар. "
    "Мағынаны, сандарды, сілтемелерді (URL), @пайдаланушы аттарын, промокодтар мен "
    "ақша сомаларын дәл сақта. Тек қазақша аударманы қайтар — ешқандай түсініктеме жазба."
)


def load_targets() -> list[dict]:
    rows = []
    with open(SRC, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("language") == "ru" and r.get("label") == "scam":
                txt = (r.get("combined_text") or "").strip()
                if txt:
                    rows.append(r)
    return rows


def load_done(out_path: str) -> set[str]:
    done: set[str] = set()
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    done.add(json.loads(line)["mt_source_id"])
                except Exception:  # noqa: BLE001
                    continue
    return done


def make_record(orig: dict, kk_text: str) -> dict:
    rec = dict(orig)
    rec["id"] = f"kktr_{orig['id']}"
    rec["language"] = "kk"
    rec["combined_text"] = kk_text
    # язык-специфичные подполя обнуляем, чтобы не было ru-утечки в kk-запись
    rec["title"] = None
    rec["description"] = None
    rec["transcript"] = None
    rec["ocr_text"] = None
    rec["source"] = f"{orig.get('source', '')}+mt_kk"
    rec["annotator"] = "mt:qwen2.5-7b-awq"
    rec["review_status"] = "draft_mt"
    rec["mt_source_id"] = orig["id"]
    return rec


async def translate_one(client: httpx.AsyncClient, model: str, text: str) -> str | None:
    # бюджет токенов с запасом относительно длины входа (kk чуть длиннее ru)
    max_tokens = min(2048, max(64, int(len(text) / 2) + 128))
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": text},
        ],
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }
    for attempt in range(4):
        try:
            resp = await client.post("/chat/completions", json=payload, timeout=180)
            resp.raise_for_status()
            out = resp.json()["choices"][0]["message"]["content"].strip()
            return out or None
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                print(f"[fail] {type(e).__name__}: {str(e)[:80]}", file=sys.stderr)
                return None
            await asyncio.sleep(2 * (attempt + 1))
    return None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("LLM_HOST_URL", "http://localhost:8100/v1"))
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct-AWQ")
    ap.add_argument("--concurrency", type=int, default=48)
    ap.add_argument("--limit", type=int, default=0, help="0 = все")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    targets = load_targets()
    done = load_done(args.out)
    todo = [r for r in targets if r["id"] not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"ru-scam всего: {len(targets)} | уже готово: {len(done)} | к переводу: {len(todo)}")
    if not todo:
        print("Нечего переводить.")
        return

    sem = asyncio.Semaphore(args.concurrency)
    lock = asyncio.Lock()
    counter = {"ok": 0, "fail": 0}
    fout = open(args.out, "a", encoding="utf-8")

    async with httpx.AsyncClient(base_url=args.base_url) as client:

        async def worker(orig: dict) -> None:
            async with sem:
                kk = await translate_one(client, args.model, orig["combined_text"])
            async with lock:
                if kk:
                    fout.write(json.dumps(make_record(orig, kk), ensure_ascii=False) + "\n")
                    fout.flush()
                    counter["ok"] += 1
                else:
                    counter["fail"] += 1
                n = counter["ok"] + counter["fail"]
                if n % 200 == 0 or n == len(todo):
                    print(f"  {n}/{len(todo)}  ok={counter['ok']} fail={counter['fail']}", flush=True)

        await asyncio.gather(*(worker(r) for r in todo))

    fout.close()
    print(f"Готово: ok={counter['ok']} fail={counter['fail']} → {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
