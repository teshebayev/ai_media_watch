"""Seed-датасет Digital Shadow — синтетический «стартовый набор» для обучения/демо.

Зачем синтетика, а не скрейпинг: контрабанда/наркотики/утечки нельзя собирать с реальных
площадок (юридически и по §0). Этот набор — fabricated: выдуманные домены/кошельки/Telegram,
маски телефонов, реальных ПДн нет. На его основе студенты ДОПОЛНЯЮТ датасет реальными
clearweb-кейсами (вейпы/дропы) и публичными abuse-репортами (крипто) — см.
docs/digital_shadow_data_task.md.

Каждая строка размечена эталоном: gold_category + gold_signals (ключевые шадоу-сигналы),
чтобы eval-харнес (run_batch.py) считал точность.

Запуск:  python -m apps.digital_shadow.seed_data   →  data/shadow/seed.jsonl
"""

from __future__ import annotations

import itertools
import json
import os

OUT = "data/shadow/seed.jsonl"

# Фейковые реквизиты (выдуманные/публичные примеры — НЕ реальные владельцы)
_TG = ["@opt_market_kz", "@fast_work_2024", "@baza_seller", "@shop_proveren", "@dropteam_kz"]
_BTC = ["bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
_TRC = ["TQn9Y2khEsLJW1ChVWFMSMeRDow5Kcbk2v"]


def _rows() -> list[dict]:
    rows: list[dict] = []

    def add(prefix, src, platform, lang, text, cat, signals):
        rows.append({
            "id": f"{prefix}_{len([r for r in rows if r['id'].startswith(prefix)]) + 1:03d}",
            "source_type": src, "platform": platform, "language": lang,
            "text": text, "gold_category": cat, "gold_signals": signals,
        })

    # ── contraband_vape (clearweb) ──
    vape = [
        "Elf bar оптом, жидкости без акциз, доставка по РК. Без документов. Пишите {tg}.",
        "Вейпы оптом и в розницу, электронные сигареты без акциз. Опт от 50 шт, {tg}.",
        "Айкос оптом, стики без документов, большие объёмы. Контакт {tg}.",
    ]
    vape_kk = ["Акцизсіз сұйықтық көтерме, вейп опт, құжатсыз жеткізу. {tg}."]
    for t in vape:
        for tg in _TG[:3]:
            add("vape", "clearweb", "olx", "ru", t.format(tg=tg),
                "contraband_vape", ["contraband_keyword"])
    for t in vape_kk:
        add("vape", "clearweb", "instagram", "kk", t.format(tg=_TG[0]),
            "contraband_vape", ["contraband_keyword"])

    # ── contraband_alcohol (clearweb) ──
    alc = [
        "Алкоголь без акциз оптом, спирт оптом, доставка ночью. {tg}.",
        "Паленый алкоголь дёшево, большие объёмы, без документов. {tg}.",
    ]
    for t, tg in itertools.product(alc, _TG[:3]):
        add("alc", "clearweb", "telegram", "ru", t.format(tg=tg),
            "contraband_alcohol", ["contraband_keyword"])

    # ── drop_recruitment (clearweb) — самая ценная, реальная ──
    drop = [
        "Ищем дропов: карта в аренду за процент, приём переводов и снять. {tg}, оплата USDT {trc}.",
        "Выгодная подработка: нужны карты, обнал, прием переводов. Пишите {tg}.",
        "Нужны дропы по РК, переоформление карт, получить и снять. Оплата в крипте. {tg}.",
    ]
    drop_kk = ["Дроп керек: карта жалға, аударымдарды қабылдау. {tg}, оплата USDT."]
    for t, tg in itertools.product(drop, _TG):
        add("drop", "clearweb", "telegram", "ru", t.format(tg=tg, trc=_TRC[0]),
            "drop_recruitment", ["drop_recruitment", "encrypted_contact"])
    for t in drop_kk:
        add("drop", "clearweb", "telegram", "kk", t.format(tg=_TG[4]),
            "drop_recruitment", ["drop_recruitment"])

    # ── suspicious_crypto (публичные abuse-репорты) ──
    crypto = [
        "Кошелёк {btc} замечен в схеме вымогательства, отмыв через миксер. Чистая крипта.",
        "Адрес {btc} — мошеннический сбор инвестиций, далее tumbler/миксер.",
        "Жалоба: перевёл на {btc}, деньги ушли через mixer, вернуть нельзя.",
    ]
    for t, btc in itertools.product(crypto, _BTC):
        add("crypto", "paste", "chainabuse", "ru", t.format(btc=btc),
            "suspicious_crypto", ["mixer_or_tumbler", "crypto_wallet_found"])

    # ── kz_data_leak (метаданные листинга, БЕЗ реальных ПДн) ──
    leak = [
        "Продам базу РК: ФИО, ИИН ************, телефоны. Свежий дамп, пробив по запросу. {tg}.",
        "Слив базы Казахстан, актуальный дамп, цена в USDT {trc}. Контакт {tg}.",
        "База данных РК на продажу, пробив физлиц, ИИН и адреса. {tg}.",
    ]
    for t, tg in itertools.product(leak, _TG[:3]):
        add("leak", "paste", "leak_forum", "ru", t.format(tg=tg, trc=_TRC[0]),
            "kz_data_leak", ["kz_data_leak"])

    # ── drug_trafficking (СИНТЕТИКА, source=darknet; детекция, не инструкция) ──
    drug = [
        "Проверенный магазин, товар в наличии, закладки по городу, опт и розница. Связь session.",
        "Клад по городу, товар проверенный, оплата только USDT {trc}. Анонимно.",
    ]
    for t in drug:
        add("drug", "darknet", "darkmarket", "ru", t.format(trc=_TRC[0]),
            "drug_trafficking", ["drug_slang", "darknet_listing"])

    # ── legit-контрпримеры (должны давать low / unknown) ──
    legit = [
        ("Продам вейп, чек и гарантия, оригинал, продажа только 21+.", "ru"),
        ("Ищем менеджера по продажам, офис, оклад + бонус, оформление по ТК РК.", "ru"),
        ("Лицензированный обменник валют, паспорт обязателен, официальный курс.", "ru"),
        ("Магазин электроники: доставка, гарантия, оплата картой или Kaspi.", "ru"),
        ("Продаю алкоголь — только лицензированный магазин, с акцизными марками.", "ru"),
        ("Сатылым: смартфон, кепілдік, түбіртек бар, ресми дүкен.", "kk"),
    ]
    for text, lang in legit:
        add("legit", "clearweb", "olx", lang, text, "unknown", [])

    return rows


def main() -> None:
    rows = _rows()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    ctr = Counter(r["gold_category"] for r in rows)
    print(f"seed: {len(rows)} строк → {OUT}")
    for cat, n in ctr.most_common():
        print(f"  {cat:20} {n}")


if __name__ == "__main__":
    main()
