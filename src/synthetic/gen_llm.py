"""Шаг 8.7 — LLM-генерация разнообразного корпуса через vLLM (Qwen2.5-7B-AWQ).

Закрывает дыры датасета (замечания ревью):
  • legit-корпус (ru/kk/en): банковские/eGov-уведомления, промо, новости, антифрод —
    без негативов классификатор бесполезен;
  • тонкие классы (money_mule_or_drop, deepfake_financial_promo, fake_seller).

Каждый запрос просит МОДЕЛЬ выдать пачку РАЗНЫХ коротких сообщений (JSON-массив),
что даёт разнообразие лучше, чем шаблоны (src/synthetic/gen_posts.py). Каждое сообщение
прогоняется через regex-сущности + signal_extractor и пишется в едином §5-формате.

Запуск (vLLM на :8100):
    python -m src.synthetic.gen_llm --out data/processed/synthetic_llm.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re

import httpx

from src.extraction.regex_extractors import extract_entities
from src.extraction.signal_extractor import extract_signals

BATCH = 10  # сколько разных сообщений просим за один запрос

# key: (label, fraud_type, language, n_target, instruction)
SPECS: list[tuple[str, str, str, str, int, str]] = [
    ("legit_fin_ru", "legit", "legit_finance", "ru", 600,
     "реалистичные ЛЕГИТИМНЫЕ финансовые сообщения на русском: уведомления банков "
     "(Halyk, Kaspi, ForteBank, Jusan), подтверждения платежей и переводов, реальные "
     "промо по вкладам/картам/ипотеке, уведомления eGov/Egov mobile, новости о ставках. "
     "БЕЗ мошеннических признаков: не просят код из SMS, не торопят, не обещают сверхдоход."),
    ("legit_fin_kk", "legit", "legit_finance", "kk", 600,
     "нақты ЗАҢДЫ қаржы хабарламалары қазақ тілінде: банк хабарламалары (Halyk, Kaspi, "
     "ForteBank), төлемді растау, салым/карта/ипотека бойынша шынайы промо, eGov "
     "хабарламалары, мөлшерлеме жаңалықтары. Алаяқтық белгілерінсіз: SMS код сұрамайды, "
     "асықтырмайды, шектен тыс табыс уәде етпейді."),
    ("legit_fin_en", "legit", "legit_finance", "en", 400,
     "realistic LEGITIMATE finance messages in English: bank notifications, payment/transfer "
     "confirmations, genuine deposit/card/mortgage promos, fintech updates, rate news. "
     "NO scam markers: never ask for SMS codes, no urgency, no unrealistic returns."),
    ("edu_ru", "legit", "anti_fraud_education", "ru", 400,
     "антифрод-просвещение на русском: памятки и предупреждения, как распознать мошенников, "
     "что банк/госорган НИКОГДА не просит, как вести себя при подозрительном звонке."),
    ("edu_kk", "legit", "anti_fraud_education", "kk", 400,
     "алаяқтыққа қарсы ағарту қазақ тілінде: алаяқтарды қалай тану, банк/мемлекеттік орган "
     "ЕШҚАШАН не сұрамайды, күдікті қоңырау кезінде не істеу керек туралы кеңестер."),
    ("mule_ru", "scam", "money_mule_or_drop", "ru", 500,
     "вербовка дропов/денежных мулов на русском: предложения «заработка» за приём и перевод "
     "денег через свою карту, аренда карты, обналичка, «работа» курьером по выдаче наличных. "
     "С признаками: быстрый доход, нужна твоя карта/счёт, третьи лица, анонимность."),
    ("mule_kk", "scam", "money_mule_or_drop", "kk", 400,
     "дроп/ақша муласын жалдау қазақ тілінде: өз картаң арқылы ақша қабылдап аудару үшін "
     "«табыс» ұсыныстары, картаны жалға беру, қолма-қол ақша беру «жұмысы». Белгілерімен: "
     "тез табыс, сенің картаң/шотың керек, үшінші тұлғалар, анонимдік."),
    ("deepfake_ru", "scam", "deepfake_financial_promo", "ru", 400,
     "тексты-озвучки ДИПФЕЙК финансовых промо на русском: будто известный человек/глава банка "
     "или Нацбанка в видео зовёт инвестировать в «гос-платформу»/крипту с гарантированным "
     "доходом, срочно перейти по ссылке и внести депозит."),
    ("deepfake_kk", "scam", "deepfake_financial_promo", "kk", 300,
     "ДИПФЕЙК қаржы промо мәтіндері қазақ тілінде: бейнеде белгілі тұлға/банк басшысы "
     "«мемлекеттік платформаға»/криптоға кепілдік табыспен салым салуға шақырғандай, "
     "сілтемеге шұғыл өтіп депозит салуды сұрайды."),
    ("seller_ru", "scam", "fake_seller", "ru", 500,
     "лжепродавцы на русском (маркетплейсы/Instagram/Telegram): только предоплата, цена "
     "сильно ниже рынка, нет адреса/реквизитов магазина, торопят оплатить на карту "
     "физлица, после оплаты пропадают."),
    ("seller_kk", "scam", "fake_seller", "kk", 400,
     "жалған сатушылар қазақ тілінде (маркетплейс/Instagram/Telegram): тек алдын ала төлем, "
     "нарықтан әлдеқайда арзан баға, дүкен мекенжайы/деректемесі жоқ, жеке тұлға картасына "
     "төлеуге асықтырады, төлемнен кейін жоғалып кетеді."),
]

SYSTEM = (
    "Ты генерируешь СИНТЕТИЧЕСКИЕ обучающие данные для антифрод-классификатора. "
    "Верни СТРОГО JSON-массив из {k} РАЗНЫХ коротких сообщений (1–4 предложения каждое) — "
    "категория: {desc}. Сообщения должны быть разнообразными по формулировкам, суммам, "
    "брендам, длине. Без нумерации и пояснений — только JSON-массив строк."
)


def parse_array(text: str) -> list[str]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            return [str(x).strip() for x in arr if str(x).strip()]
    except Exception:  # noqa: BLE001
        pass
    # фолбэк: построчно, срезая маркеры списка
    out = []
    for ln in text.splitlines():
        ln = re.sub(r'^\s*(?:[-*]|\d+[.)])\s*', "", ln).strip().strip('",')
        if len(ln) > 8:
            out.append(ln)
    return out


async def gen_batch(client: httpx.AsyncClient, model: str, k: int, desc: str) -> list[str]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM.format(k=k, desc=desc)},
            {"role": "user", "content": "Сгенерируй пачку сейчас."},
        ],
        "temperature": 1.0,  # выше → разнообразнее
        "top_p": 0.95,
        "max_tokens": 1400,
    }
    for attempt in range(4):
        try:
            r = await client.post("/chat/completions", json=payload, timeout=180)
            r.raise_for_status()
            return parse_array(r.json()["choices"][0]["message"]["content"])
        except Exception:  # noqa: BLE001
            if attempt == 3:
                return []
            await asyncio.sleep(2 * (attempt + 1))
    return []


def make_record(idx: int, key: str, label: str, fraud_type: str, lang: str, text: str) -> dict:
    entities = extract_entities(text)
    signals = extract_signals(text, entities) if label == "scam" else []
    return {
        "id": f"gen_{key}_{idx:05d}",
        "source": "synthetic_llm",
        "platform": "telegram",
        "modality": "text",
        "case_type": fraud_type,
        "language": lang,
        "url": None, "title": None, "description": None, "transcript": None, "ocr_text": None,
        "combined_text": text,
        "entities": entities,
        "media_anomalies": {},
        "risk_signals": signals,
        "evidence_spans": [],
        "label": label,
        "fraud_type": fraud_type,
        "risk_level": None, "risk_score": None,
        "annotator": "synthetic_llm:qwen2.5-7b-awq",
        "review_status": "draft_synth",
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("LLM_HOST_URL", "http://localhost:8100/v1"))
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct-AWQ")
    ap.add_argument("--concurrency", type=int, default=32)
    ap.add_argument("--out", default="data/processed/synthetic_llm.jsonl")
    ap.add_argument("--scale", type=float, default=1.0, help="множитель n_target (для проб)")
    args = ap.parse_args()

    sem = asyncio.Semaphore(args.concurrency)
    seen: set[str] = set()
    fout = open(args.out, "w", encoding="utf-8")
    lock = asyncio.Lock()
    counts: dict[str, int] = {}

    async with httpx.AsyncClient(base_url=args.base_url) as client:
        async def run_spec(key, label, fraud_type, lang, n_target, desc):
            n_target = int(n_target * args.scale)
            counts[key] = 0
            n_batches = (n_target // BATCH) + 2

            async def one():
                async with sem:
                    msgs = await gen_batch(client, args.model, BATCH, desc)
                async with lock:
                    for m in msgs:
                        if counts[key] >= n_target:
                            break
                        kdup = (lang, m.lower()[:120])
                        if kdup in seen:
                            continue
                        seen.add(kdup)
                        counts[key] += 1
                        rec = make_record(counts[key], key, label, fraud_type, lang, m)
                        fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fout.flush()

            # запускаем батчи волнами, пока не наберём цель
            while counts[key] < n_target:
                todo = min(n_batches, max(4, (n_target - counts[key]) // BATCH + 2))
                await asyncio.gather(*(one() for _ in range(todo)))
                if counts[key] == 0:  # модель не отдаёт — выходим, чтобы не зациклиться
                    break
            print(f"  {key:14} {lang} {label:5} {fraud_type:24} → {counts[key]}", flush=True)

        # последовательно по спекам (внутри — параллельные батчи), чтобы лог был читаемый
        for spec in SPECS:
            await run_spec(*spec)

    fout.close()
    total = sum(counts.values())
    print(f"Сгенерировано {total} строк → {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
