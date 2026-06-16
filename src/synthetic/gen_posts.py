"""Этап 8.1 — генератор синтетических постов по категориям (ru/kk), self-labeled.

Покрывает категории, которых нет в звонках: казино-промо, пирамида/инвест-скам,
фишинг, крипто-скам, плюс legit-финансы и антифрод-обучение (чтобы классификатор
не выучил «текст про деньги = scam» и «kk = scam»). Каждый пост — единый формат §5
с предразметкой: regex-сущности + базовые risk_signals.

Запуск:
    python -m src.synthetic.gen_posts [--out data/processed/synthetic_posts.jsonl]
"""

from __future__ import annotations

import argparse
import itertools
import json
import os

from src.extraction.regex_extractors import extract_entities
from src.extraction.signal_extractor import extract_signals

# Банки подстановок
AMOUNTS = ["10 000 ₸", "50 000 ₸", "500 000 ₸", "1 000 000 ₸"]
PERCENTS = ["20% в неделю", "300% в месяц", "10% в день"]
DOMAINS = ["casino-x.com", "invest-pro.top", "fast-money.site", "kaspi-bonus.click"]
PROMOS = ["PROMO777", "BONUS500", "WIN1000", "LUCKY24"]
TG = ["@easy_money_mgr", "@invest_guru_kz", "@crypto_support1", "@bonus_manager"]
WALLETS = ["TRC20: TJ8s9kLa2mNpQ 1234567890abcdef", "0x1234567890abcdef1234567890abcdef12345678"]
# Банки для legit-примеров (реалистичные, не скам)
BANKS = ["Halyk Bank", "Kaspi Bank", "ForteBank", "Jusan Bank"]
RATES = ["14% годовых", "16,5% годовых", "12,5% годовых"]
DEPOSITS = ["100 000 ₸", "500 000 ₸", "1 000 000 ₸"]

# category → (label, fraud_type, language, [шаблоны])
TEMPLATES = {
    "gambling": ("scam", "illegal_gambling_promo", "ru", [
        "Регистрируйся на {domain}, вводи промокод {promo} и получи бонус на депозит. Я поднял {amount}, вывод работает!",
        "Слоты и ставки — заходи по ссылке {domain}, промокод {promo}, бонус за регистрацию. Пиши {tg}.",
    ]),
    "pyramid": ("scam", "investment_scam", "ru", [
        "Инвестируй {amount} и получай {percent}. Пригласи друзей, повышай уровень — чем больше команда, тем выше доход. Пиши {tg}.",
        "Гарантированный пассивный доход {percent} без риска. Реферальная программа, пакеты, статусы. Старт от {amount}.",
    ]),
    "phishing": ("scam", "phishing", "ru", [
        "Ваш аккаунт заблокирован. Перейдите по ссылке {domain} и подтвердите данные карты и код из SMS, иначе списание.",
        "Вам положена компенсация {amount}. Для получения подтвердите карту на {domain} и введите код из SMS.",
    ]),
    "crypto": ("scam", "crypto_scam", "ru", [
        "Арбитраж криптовалют без риска! Минимальный депозит {amount}, менеджер поможет вывести прибыль. Кошелёк {wallet}. {tg}",
        "Инвестируй в майнинг USDT, доход {percent}. Переводи на {wallet}, поддержка {tg}.",
    ]),
    # --- НЕ скам: важно для баланса ---
    "legit_finance": ("legit", "legit_finance", "ru", [
        "Депозит в {bank} под {rate}, страхование вкладов до 20 млн ₸. Оформление в отделении или приложении.",
        "{bank} запустил вклад от {deposit} со ставкой {rate}. Условия на официальном сайте.",
        "Ипотека в {bank}: первоначальный взнос от {deposit}, ставка {rate}. Подробности у менеджера в отделении.",
    ]),
    "education": ("legit", "anti_fraud_education", "ru", [
        "Помните: сотрудники {bank} и госорганов никогда не просят код из SMS и не предлагают «безопасный счёт». Это мошенники.",
        "Антифрод-памятка: не переходите по ссылкам из SMS, не устанавливайте AnyDesk по просьбе «службы безопасности».",
        "Официальное предупреждение: если звонят из «{bank}» и торопят перевести деньги — положите трубку и позвоните в банк сами.",
    ]),
    # --- казахские примеры (часть scam, часть legit — баланс языка) ---
    "education_kk": ("legit", "anti_fraud_education", "kk", [
        "Есіңізде болсын: банк қызметкерлері SMS кодын сұрамайды және «қауіпсіз шот» ұсынбайды. Бұл алаяқтар.",
        "Алаяқтыққа қарсы кеңес: SMS-тегі сілтемелерге өтпеңіз, бөгде адамға қашықтан кіруге рұқсат бермеңіз.",
    ]),
    "pyramid_kk": ("scam", "investment_scam", "kk", [
        "{amount} салыңыз да, аптасына {percent} табыс алыңыз. Достарыңызды шақырыңыз, команда үлкейген сайын табыс өседі. {tg}",
    ]),
}


def _fill(template: str) -> list[str]:
    """Подставить все нужные плейсхолдеры комбинаторно, вернуть уникальные тексты."""
    keys = [k for k in ("domain", "promo", "amount", "percent", "tg", "wallet",
                        "bank", "rate", "deposit") if "{" + k + "}" in template]
    banks = {"domain": DOMAINS, "promo": PROMOS, "amount": AMOUNTS,
             "percent": PERCENTS, "tg": TG, "wallet": WALLETS,
             "bank": BANKS, "rate": RATES, "deposit": DEPOSITS}
    if not keys:
        return [template]
    combos = itertools.product(*[banks[k] for k in keys])
    seen, out = set(), []
    for combo in combos:
        text = template.format(**dict(zip(keys, combo)))
        if text not in seen:
            seen.add(text)
            out.append(text)
    return out


def generate(per_template_cap: int = 6) -> list[dict]:
    rows, idx = [], 0
    for cat, (label, fraud_type, lang, templates) in TEMPLATES.items():
        for template in templates:
            for text in _fill(template)[:per_template_cap]:
                idx += 1
                entities = extract_entities(text)
                signals = extract_signals(text, entities) if label == "scam" else []
                rows.append({
                    "id": f"post_{cat}_{idx:04d}",
                    "source": "synthetic_post",
                    "platform": "telegram",
                    "modality": "text",
                    "case_type": fraud_type,
                    "language": lang,
                    "url": None,
                    "title": None,
                    "description": None,
                    "transcript": None,
                    "ocr_text": None,
                    "combined_text": text,
                    "entities": entities,
                    "media_anomalies": {},
                    "risk_signals": signals,
                    "evidence_spans": [],
                    "label": label,
                    "fraud_type": fraud_type,
                    "risk_level": None,
                    "risk_score": None,
                    "annotator": "synthetic",
                    "review_status": "pending",
                })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/processed/synthetic_posts.jsonl")
    parser.add_argument("--cap", type=int, default=6, help="макс. постов на шаблон")
    args = parser.parse_args()
    rows = generate(args.cap)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for rec in rows:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    import collections
    by_label = collections.Counter(r["label"] for r in rows)
    by_lang = collections.Counter(r["language"] for r in rows)
    print(f"Постов: {len(rows)} → {args.out}")
    print(f"по label: {dict(by_label)} | по языкам: {dict(by_lang)}")


if __name__ == "__main__":
    main()
