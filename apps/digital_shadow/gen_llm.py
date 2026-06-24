"""LLM-генерация синтетического корпуса Digital Shadow через vLLM (Qwen2.5).

Модель пишет пачки РАЗНЫХ коротких листингов по каждой теневой категории; каждый листинг
**самопроверяется** прогоном через реальный пайплайн (`analyze_item`) — в датасет попадают
только те, что классифицируются в нужную категорию. Так gold-метки остаются корректными,
а данные — на распределении детектора. Реквизиты фейковые/маскированные (§0).

Нужен поднятый vLLM (`bash scripts/run_vllm.sh`); ходим в LLM напрямую по HTTP.

Запуск:
    python -m apps.digital_shadow.gen_llm --out data/shadow/llm_gen.jsonl --scale 1.0
    make shadow-gen
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re

import httpx

from apps.digital_shadow.pipeline import analyze_item
from apps.digital_shadow.schemas import ShadowItem

BATCH = 8  # сколько листингов просим за один запрос

# key, category, source_type, lang, n_target, описание для модели
SPECS: list[tuple[str, str, str, str, int, str]] = [
    ("vape_ru", "contraband_vape", "clearweb", "ru", 40,
     "объявления о КОНТРАБАНДЕ вейпов/жидкостей/стиков: ОБЯЗАТЕЛЬНО со словами «оптом» "
     "и/или «без акциз», увод в Telegram (@ник), иногда «без документов». Бренды elf bar, iqos."),
    ("vape_kk", "contraband_vape", "clearweb", "kk", 20,
     "вейп контрабандасы туралы хабарландырулар: МІНДЕТТІ «көтерме» немесе «акцизсіз», "
     "Telegram-ке (@ник) шақыру."),
    ("alc_ru", "contraband_alcohol", "clearweb", "ru", 25,
     "объявления о нелегальном алкоголе: ОБЯЗАТЕЛЬНО «алкоголь без акциз» или «спирт оптом» "
     "или «паленый алкоголь», опт, контакт в Telegram."),
    ("drop_ru", "drop_recruitment", "clearweb", "ru", 50,
     "вербовка ДРОПОВ: ОБЯЗАТЕЛЬНО про «карта в аренду» / «приём переводов» / «обнал» / "
     "«ищем дропов», увод в Telegram (@ник), оплата USDT. Подаётся как «подработка»."),
    ("drop_kk", "drop_recruitment", "clearweb", "kk", 20,
     "дроп жалдау: МІНДЕТТІ «карта жалға» / «аударымдарды қабылдау», Telegram (@ник)."),
    ("crypto_ru", "suspicious_crypto", "paste", "ru", 30,
     "ПУБЛИЧНЫЕ жалобы на подозрительные криптокошельки: ОБЯЗАТЕЛЬНО адрес кошелька "
     "(BTC bc1.../1.., либо TRC20 T...) и слова про отмыв/миксер/tumbler/«чистая крипта»."),
    ("leak_ru", "kz_data_leak", "paste", "ru", 30,
     "объявления о ПРОДАЖЕ баз данных РК: ОБЯЗАТЕЛЬНО «продам базу РК»/«слив базы»/«дамп»/"
     "«пробив», упоминание ИИН/ФИО/телефонов. ВАЖНО: ИИН только маской ************ "
     "(12 звёздочек), никаких реальных номеров. Контакт Telegram, оплата USDT."),
    ("drug_ru", "drug_trafficking", "darknet", "ru", 30,
     "СИНТЕТИЧЕСКИЕ листинги даркнет-магазина (для детектора, не инструкция!): общие фразы "
     "«товар в наличии», «закладки по городу», «проверенный магазин», «опт и розница», "
     "оплата только крипта, связь session/jabber. БЕЗ названий веществ и способов."),
    ("legit_ru", "unknown", "clearweb", "ru", 35,
     "ЛЕГАЛЬНЫЕ обычные объявления (контрпримеры): продажа вейпа/алкоголя В РОЗНИЦУ с "
     "чеком/акцизом/гарантией 21+, нормальные вакансии по ТК, лицензированный обменник "
     "с паспортом. БЕЗ слов «оптом», «без акциз», «дроп», «база», «закладки», без крипто-оплаты."),
]

# Канонические сигналы категории — для gold (берём пересечение с реально сработавшими).
EXPECTED: dict[str, set[str]] = {
    "contraband_vape": {"contraband_keyword"},
    "contraband_alcohol": {"contraband_keyword"},
    "drop_recruitment": {"drop_recruitment"},
    "suspicious_crypto": {"mixer_or_tumbler", "bad_crypto_wallet", "crypto_wallet_found"},
    "kz_data_leak": {"kz_data_leak", "iin_dump_mention"},
    "drug_trafficking": {"drug_slang", "darknet_listing"},
    "unknown": set(),
}

SYSTEM = (
    "Ты генерируешь СИНТЕТИЧЕСКИЕ обучающие данные для OSINT-детектора незаконной активности. "
    "Все данные ВЫМЫШЛЕННЫЕ: фейковые домены/кошельки/Telegram-ники, телефоны строго маской "
    "(+7 7XX XXX-XX-XX), никаких реальных персональных данных. "
    "Верни СТРОГО JSON-массив из {k} РАЗНЫХ коротких текстов (1–3 предложения) — {desc} "
    "Разнообразь формулировки, бренды, суммы. Только JSON-массив строк, без пояснений."
)


def parse_array(text: str) -> list[str]:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            return [str(x).strip() for x in arr if str(x).strip()]
    except Exception:  # noqa: BLE001
        pass
    out = []
    for ln in text.splitlines():
        ln = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", ln).strip().strip('",')
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
        "temperature": 1.0, "top_p": 0.95, "max_tokens": 1200,
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


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", "http://localhost:8100/v1"))
    ap.add_argument("--model", default=os.environ.get("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct-AWQ"))
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--out", default="data/shadow/llm_gen.jsonl")
    ap.add_argument("--scale", type=float, default=1.0)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    sem = asyncio.Semaphore(args.concurrency)
    seen: set[str] = set()
    kept: dict[str, int] = {}
    stats = {"dropped": 0}
    fout = open(args.out, "w", encoding="utf-8")
    lock = asyncio.Lock()

    async with httpx.AsyncClient(base_url=args.base_url) as client:
        async def run_spec(key, category, src, lang, n_target, desc):
            n_target = int(n_target * args.scale)
            kept[key] = 0

            async def one():
                async with sem:
                    texts = await gen_batch(client, args.model, BATCH, desc)
                for t in texts:
                    if kept[key] >= n_target:
                        break
                    kdup = (lang, t.lower()[:100])
                    async with lock:
                        if kdup in seen:
                            continue
                        seen.add(kdup)
                    # самопроверка: прогон через реальный пайплайн
                    f = await analyze_item(ShadowItem(
                        id=f"{key}_tmp", source_type=src, language=lang, text=t), driver=None)
                    if category == "unknown":
                        ok = f.category == "unknown" and f.risk_level in ("low", "medium")
                    else:
                        ok = f.category == category
                    if not ok:
                        stats["dropped"] += 1
                        continue
                    gold = sorted(set(f.signals) & EXPECTED[category])
                    async with lock:
                        if kept[key] >= n_target:
                            return
                        rec = {
                            "id": f"{key}_{kept[key] + 1:04d}", "source_type": src,
                            "platform": "telegram" if src == "clearweb" else src,
                            "language": lang, "text": t,
                            "gold_category": category, "gold_signals": gold,
                        }
                        fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        fout.flush()
                        kept[key] += 1

            rounds = 0
            while kept[key] < n_target and rounds < 12:
                waves = max(4, (n_target - kept[key]) // BATCH + 2)
                await asyncio.gather(*(one() for _ in range(waves)))
                rounds += 1
                if kept[key] == 0 and rounds >= 2:  # модель молчит/не проходит валидацию
                    break
            print(f"  {key:10} {lang} {category:20} → {kept[key]}/{n_target}", flush=True)

        for spec in SPECS:
            await run_spec(*spec)

    fout.close()
    total = sum(kept.values())
    print(f"\nСгенерировано (валидных): {total} → {args.out}  (отброшено: {stats['dropped']})")


if __name__ == "__main__":
    asyncio.run(main())
