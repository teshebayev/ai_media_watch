"""Полный пайплайн Stop-Piramida: транскрибация → NER → LLM-валидация → база+граф.

Стадии (идемпотентно, с resume):
  1. transcribe  — mp4 (media_path) → faster-whisper → transcript (чекпойнт sp_transcripts.jsonl)
  2. enrich      — combined_text = title+desc+transcript; regex-сущности + KazNERD (организации) + сигналы
  3. validate    — LLM (Qwen2.5-3B) по транскрипту: fraud_type + это предупреждение или сам скам → label
  4. rebuild     — перезапись stop_piramida.jsonl → единый датасет → reindex Qdrant → пересборка графа

Тяжёлые модели (Whisper+NER+LLM) → запускать на СВОБОДНОМ GPU (после serve_b1k).
Флаги для лёгкой проверки: --limit N --skip-ner --skip-llm --no-rebuild --whisper-size tiny

Запуск (полный, GPU свободен):
    PYTHONPATH=. QDRANT_URL=http://localhost:6333 NEO4J_URI=bolt://localhost:7687 \
    NEO4J_PASSWORD=finguard_pass .venv/bin/python scripts/process_stop_piramida.py
"""

from __future__ import annotations

import argparse
import json
import os
import re

SP = "data/processed/stop_piramida.jsonl"
TRANSCRIPTS = "data/processed/sp_transcripts.jsonl"  # чекпойнт id -> transcript
QWEN = "Qwen/Qwen2.5-3B-Instruct"

VALIDATION_PROMPT = (
    "Тебе дан транскрипт видео с антифрод-ресурса. Верни СТРОГО один JSON на русском: "
    '{"fraud_type": "...", "is_warning": true/false, "confidence": 0..1}. '
    "fraud_type — тема мошенничества (illegal_gambling_promo, fake_egov_delivery_call, "
    "fake_bank_call, fake_government_call, investment_scam, crypto_scam, phishing, "
    "money_mule_or_drop, fake_seller, fake_credit, deepfake_financial_promo, legit_finance, "
    "anti_fraud_education, ordinary_spam). "
    "is_warning=true если это предупреждение/разъяснение о схеме (а не само мошенническое сообщение)."
)


def load_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


# --- модели (ленивая загрузка) ----------------------------------------------

def get_whisper(size: str):
    import torch
    from faster_whisper import WhisperModel

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    ct = "float16" if dev == "cuda" else "int8"
    print(f"  whisper: {size} на {dev}/{ct}")
    return WhisperModel(size, device=dev, compute_type=ct)


def get_llm():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(QWEN)
    model = AutoModelForCausalLM.from_pretrained(QWEN, dtype=torch.bfloat16).to("cuda").eval()
    return tok, model


def llm_validate(tok, model, text: str) -> dict:
    import torch

    msgs = [{"role": "system", "content": VALIDATION_PROMPT},
            {"role": "user", "content": text[:3000]}]
    prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inputs = tok(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=128, do_sample=False,
                             pad_token_id=tok.eos_token_id)
    return _extract_json(tok.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True))


# --- стадии -----------------------------------------------------------------

def stage_transcribe(records: list[dict], size: str, limit: int | None) -> dict[str, str]:
    # только НЕПУСТЫЕ транскрипты считаем готовыми — пустые (ошибки прошлого прогона) перетранскрибируем
    done = {r["id"]: r["transcript"] for r in load_jsonl(TRANSCRIPTS) if (r.get("transcript") or "").strip()}
    todo = [r for r in records if r.get("media_path") and r["id"] not in done]
    if limit:
        todo = todo[:limit]
    if not todo:
        print(f"  транскрибировать нечего (готово: {len(done)})")
        return done
    model = get_whisper(size)
    os.makedirs(os.path.dirname(TRANSCRIPTS), exist_ok=True)
    with open(TRANSCRIPTS, "a", encoding="utf-8") as f:
        for i, rec in enumerate(todo, 1):
            try:
                segments, _ = model.transcribe(rec["media_path"], language="ru")
                txt = " ".join(s.text.strip() for s in segments).strip()
            except Exception as e:  # noqa: BLE001
                print(f"  [warn] {rec['id']}: {type(e).__name__}: {str(e)[:80]}")
                txt = ""
            done[rec["id"]] = txt
            f.write(json.dumps({"id": rec["id"], "transcript": txt}, ensure_ascii=False) + "\n")
            f.flush()
            if i % 20 == 0:
                print(f"  ...транскрибировано {i}/{len(todo)}")
    print(f"  готово транскриптов: {len(done)}")
    return done


def stage_enrich_validate(records, transcripts, *, skip_ner, skip_llm, limit):
    from src.extraction.regex_extractors import extract_entities
    from src.extraction.signal_extractor import extract_signals
    from src.risk.risk_engine import evaluate

    ner = None
    if not skip_ner:
        from src.extraction.kaznerd_ner import extract_kk_entities
        ner = extract_kk_entities
    llm = get_llm() if not skip_llm else None

    valid_ft = {
        "illegal_gambling_promo", "fake_egov_delivery_call", "fake_bank_call",
        "fake_government_call", "investment_scam", "crypto_scam", "phishing",
        "money_mule_or_drop", "fake_seller", "fake_credit", "deepfake_financial_promo",
        "legit_finance", "anti_fraud_education", "ordinary_spam",
    }
    processed = 0
    for rec in records:
        tr = transcripts.get(rec["id"])
        if not tr:
            continue
        # не переобрабатываем уже валидированные (resume после дозагрузки)
        if rec.get("review_status") == "llm_validated":
            continue
        if limit and processed >= limit:
            break
        processed += 1
        rec["transcript"] = tr
        combined = ". ".join(p for p in (rec.get("title"), rec.get("description"), tr) if p)
        rec["combined_text"] = combined[:20000]
        ents = extract_entities(rec["combined_text"])
        if ner:
            orgs = ner(rec["combined_text"]).get("organizations", [])
            if orgs:
                ents["organizations"] = list(dict.fromkeys([*ents.get("organizations", []), *orgs]))
        rec["entities"] = ents
        signals = extract_signals(rec["combined_text"], ents)
        rec["risk_signals"] = signals

        if llm:
            v = llm_validate(*llm, rec["combined_text"])
            ft = v.get("fraud_type")
            if ft in valid_ft:
                rec["fraud_type"] = ft
            is_warning = bool(v.get("is_warning", True))
            rec["label"] = "legit" if is_warning else "scam"
            rec["review_status"] = "llm_validated"
        else:
            rec["review_status"] = "transcribed"

        res = evaluate(signals)
        rec["risk_score"] = res["risk_score"]
        rec["risk_level"] = res["risk_level"]
    print(f"  обогащено/валидировано: {processed}")
    return records


def stage_rebuild():
    import subprocess
    env = {**os.environ, "PYTHONPATH": "."}
    for mod in ("src.build_dataset", "src.index_dataset", "src.graph.build_from_dataset"):
        extra = ["data/processed/ai_media_watch_dataset.jsonl"] if mod == "src.index_dataset" else []
        print(f"  -> {mod}")
        subprocess.run([".venv/bin/python", "-m", mod, *extra], check=False, env=env)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--whisper-size", default="small")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--skip-ner", action="store_true")
    ap.add_argument("--skip-llm", action="store_true")
    ap.add_argument("--no-rebuild", action="store_true")
    args = ap.parse_args()

    records = load_jsonl(SP)
    print(f"Stop-Piramida записей: {len(records)} (с mp4: {sum(1 for r in records if r.get('media_path'))})")

    print("[1/4] Транскрибация…")
    transcripts = stage_transcribe(records, args.whisper_size, args.limit)

    print("[2-3/4] Обогащение (NER) + LLM-валидация…")
    records = stage_enrich_validate(records, transcripts,
                                    skip_ner=args.skip_ner, skip_llm=args.skip_llm, limit=args.limit)

    with open(SP, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"  перезаписан {SP}")

    if not args.no_rebuild:
        print("[4/4] Пересборка датасета + Qdrant + граф…")
        stage_rebuild()
    print("DONE")


if __name__ == "__main__":
    main()
