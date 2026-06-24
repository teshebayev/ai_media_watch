"""Таксономия Digital Shadow: категории незаконной активности + лексикон (ru/kk) +
шадоу-специфичные риск-сигналы и их веса.

Расширяет общий движок ДОБАВЛЯЯ свои сигналы поверх `core` (не трогает общий enums/risk_engine):
итоговый скоринг считает `prioritization.py`, объединяя веса core и шадоу.

⚠️ Лексикон — иллюстративный, для детекции (defensive OSINT-мониторинг). Перед боевым
использованием курировать со специалистами/правоохранителями; это НЕ инструкция, а ключевые
слова для пометки подозрительного контента.
"""

from __future__ import annotations

import re

# ── Категории (аналог fraud_type, но для теневой активности) ─────────────────
# Держим как строки (свой словарь продукта), чтобы не раздувать общий FraudType.
SHADOW_CATEGORIES = [
    "contraband_vape",        # контрабанда вейпов/жидкостей
    "contraband_alcohol",     # нелегальный алкоголь
    "drug_trafficking",       # сбыт наркотиков / закладки
    "drop_recruitment",       # вербовка дропов (обнал, приём переводов, посылки)
    "suspicious_crypto",      # подозрительные криптокошельки / отмыв
    "kz_data_leak",           # утечка/продажа баз данных РК
    "counterfeit_goods",      # подделки/контрафакт
    "document_forgery",       # поддельные документы
    "unknown",
]

# ── Лексикон ru/kk по категориям → сигнал ────────────────────────────────────
# Каждый ключ — категория; значения — слова/обороты, по которым ставим сигнал.
LEXICON: dict[str, list[str]] = {
    # ВАЖНО: контекстные фразы (требуют «оптом/без акциз»), иначе легальная продажа вейпа
    # («продам вейп, чек и гарантия») ложно попадёт в контрабанду.
    "contraband_vape": [
        "вейп оптом", "вейпы оптом", "elf bar оптом", "айкос оптом", "iqos оптом",
        "жидкости без акциз", "жидкост без акциз", "сигареты без акциз", "стики без",
        "электронные сигареты без акциз",
        # kk:
        "вейп көтерме", "көтерме вейп", "акцизсіз вейп", "вейп акцизсіз", "акцизсіз сұйықтық",
        "сұйықтық көтерме", "электронды сигарет көтерме", "iqos көтерме", "elf bar көтерме",
    ],
    "contraband_alcohol": [
        "алкоголь без акциз", "паленый алкоголь", "спирт оптом", "контрафактный алкоголь",
        "акцизсіз алкоголь", "паленая водка",
        # kk:
        "арақ көтерме", "спирт көтерме", "акцизсіз арақ", "акцизсіз спирт",
    ],
    "drug_trafficking": [
        # ключевые слова для пометки (детекция), не инструкция:
        "закладк", "клад", "оптом и розниц", "товар в наличии", "проверенный магазин",
        "соль", "меф", "шишк", "гашиш", "скорость", "реагент", "тайник",
    ],
    "drop_recruitment": [
        "ищем дропов", "дроп", "обнал", "обналич", "прием переводов", "карта в аренду",
        "переоформ карт", "выгодная подработка", "получить и снять", "reshipping",
        "ваша карта за процент",
    ],
    "kz_data_leak": [
        "слив базы", "пробив", "база данных", "дамп", "leaked database", "база рк",
        "база казахстан", "слил базу", "продам базу", "утечка",
    ],
    "counterfeit_goods": [
        "реплика", "копия aaa", "контрафакт", "подделк", "1:1 luxury",
    ],
    "document_forgery": [
        "поддельн", "купить диплом", "купить справк", "удостоверение под заказ", "права под заказ",
    ],
}

# ── Шадоу-сигналы и их веса (поверх core.SIGNAL_WEIGHTS) ──────────────────────
SHADOW_SIGNAL_WEIGHTS: dict[str, int] = {
    "darknet_listing": 25,          # источник — даркнет/закрытая площадка
    "contraband_keyword": 25,       # совпадение лексикона контрабанды
    "drug_slang": 35,               # наркотическая лексика
    "drop_recruitment": 35,         # вербовка дропов
    "kz_data_leak": 40,             # признаки утечки БД РК
    "iin_dump_mention": 45,         # упоминание дампа с ИИН/ПДн
    "bad_crypto_wallet": 40,        # кошелёк в списке «плохих»
    "mixer_or_tumbler": 30,         # признаки миксера/тумблера
    "crypto_only_payment": 15,      # оплата только в крипте
    "encrypted_contact": 15,        # увод в закрытый канал (telegram/session/threema)
    "bulk_sale": 15,                # оптовые объёмы
    "no_kyc": 15,                   # «без документов / без верификации»
    "counterfeit": 20,
    "document_forgery": 25,
    "watchlisted": 30,              # сущность из watchlist аналитика
    "known_bad_entity": 40,         # сущность с подтверждённым abuse (репутация, flywheel)
}

# Категория → характерные сигналы (для определения SHADOW_CATEGORY находки)
CATEGORY_SIGNALS: dict[str, list[str]] = {
    "contraband_vape": ["contraband_keyword", "bulk_sale", "no_kyc"],
    "contraband_alcohol": ["contraband_keyword", "bulk_sale", "no_kyc"],
    "drug_trafficking": ["drug_slang", "darknet_listing", "crypto_only_payment"],
    "drop_recruitment": ["drop_recruitment", "encrypted_contact"],
    "suspicious_crypto": ["bad_crypto_wallet", "mixer_or_tumbler", "crypto_wallet_found",
                          "crypto_only_payment"],
    "kz_data_leak": ["kz_data_leak", "iin_dump_mention"],
    "counterfeit_goods": ["counterfeit"],
    "document_forgery": ["document_forgery"],
}

# Закрытые мессенджеры → encrypted_contact
_ENCRYPTED_CONTACT_RE = re.compile(
    r"\b(session|threema|jabber|tox|signal)\b|@[A-Za-z0-9_]{4,}", re.IGNORECASE
)
_BULK_RE = re.compile(
    r"\b(оптом|опт\b|wholesale|оптовы|большие\s+объ[её]м|көтерме)\b", re.IGNORECASE
)
_NO_KYC_RE = re.compile(r"без\s+документ|без\s+верификац|no\s*kyc|анонимн", re.IGNORECASE)
_CRYPTO_ONLY_RE = re.compile(
    r"\b(usdt|btc|bitcoin|эфир|крипт|tron|trc20|оплата\s+в\s+крипт)\b", re.IGNORECASE
)


# Компилируем лексикон с ЛЕВОЙ границей слова `(?<!\w)`, чтобы «клад» не ловился в «оклад»,
# «соль» в «консоль» и т.п. (правой границы нет — нужно ловить словоформы: «закладки»).
_LEX_RE: dict[str, re.Pattern[str]] = {
    cat: re.compile(r"(?<!\w)(" + "|".join(re.escape(w) for w in words) + ")", re.IGNORECASE)
    for cat, words in LEXICON.items()
}


def detect_lexicon_signals(text: str) -> tuple[list[str], list[str]]:
    """Вернуть (signals, matched_categories) по совпадениям лексикона/паттернов в тексте."""
    signals: list[str] = []
    categories: list[str] = []

    for category in LEXICON:
        if _LEX_RE[category].search(text):
            categories.append(category)
            if category == "drug_trafficking":
                signals.append("drug_slang")
            elif category == "drop_recruitment":
                signals.append("drop_recruitment")
            elif category == "kz_data_leak":
                signals.append("kz_data_leak")
            elif category == "counterfeit_goods":
                signals.append("counterfeit")
            elif category == "document_forgery":
                signals.append("document_forgery")
            else:  # вейпы/алкоголь
                signals.append("contraband_keyword")

    if _ENCRYPTED_CONTACT_RE.search(text):
        signals.append("encrypted_contact")
    if _BULK_RE.search(text):
        signals.append("bulk_sale")
    if _NO_KYC_RE.search(text):
        signals.append("no_kyc")
    if _CRYPTO_ONLY_RE.search(text):
        signals.append("crypto_only_payment")

    return list(dict.fromkeys(signals)), list(dict.fromkeys(categories))


def classify_category(signals: list[str], lexicon_categories: list[str]) -> str:
    """Выбрать SHADOW_CATEGORY: приоритет — лексикон; иначе по характерным сигналам."""
    if lexicon_categories:
        return lexicon_categories[0]
    for category, sigs in CATEGORY_SIGNALS.items():
        if any(s in signals for s in sigs):
            return category
    return "unknown"
