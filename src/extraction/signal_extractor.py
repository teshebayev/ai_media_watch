"""Извлечение risk_signals из текста и сущностей по ключевым словам (ТЗ кейсы 1–9).

Это детерминированный baseline. LLM (scenario service) может добавлять/уточнять
сигналы поверх, но базовые ловятся правилами — чтобы пайплайн работал даже без LLM.
"""

from __future__ import annotations

import re

# Каждый сигнал → список ключевых триггеров (lowercase, ru/kz/en).
KEYWORD_SIGNALS: dict[str, list[str]] = {
    "illegal_gambling_promo": ["казино", "слот", "ставк", "casino", "bet"],
    "deposit_bonus": ["бонус", "депозит", "bonus"],
    "registration_instruction": ["регистрируйся", "регистрация", "введи промокод"],
    "fake_winner_claim": ["поднял", "выигрыш", "вывод работает", "занёс"],
    "easy_money_claim": ["легкие деньги", "лёгкие деньги", "быстрый заработок"],
    "financial_call_to_action": ["переходи по ссылке", "ссылка в описании", "пополни"],
    "guaranteed_income": ["гарантированный доход", "доход без риска", "пассивный доход"],
    "unrealistic_profit": ["20% в неделю", "процент в неделю", "иксы", "x2", "удвой"],
    "no_risk_claim": ["без риска", "trading без риска", "тейдинг без риска"],
    "referral_scheme": ["пригласи друг", "реферал", "команда", "уровень", "пакет"],
    "crypto_payment": ["usdt", "btc", "трц20", "trc20", "крипт", "майнинг", "арбитраж"],
    "fake_egov_call": ["egov", "егов", "доставка от госоргана", "1414"],
    "sms_code_request": ["код из sms", "код из смс", "назовите код", "sms кодын"],
    "egov_1414_code": ["1414", "код 1414"],
    "fake_government_employee": ["сотрудник кнб", "сотрудник полиции", "служба безопасности",
                                 "полиция қызметкері"],
    "fake_bank_employee": ["сотрудник нацбанка", "банк қызметкері", "сотрудник банка",
                           "антифрод"],
    "fake_authority": ["спецоперация", "шұғыл", "национальный банк", "ұлттық банк"],
    "loan_fear": ["оформляют кредит", "несие рәсімделді", "на вас кредит"],
    "account_blocking_fear": ["аккаунт заблокирован", "счёт заблокирован"],
    "safe_account": ["безопасный счёт", "страховой счёт", "қауіпсіз шот"],
    "do_not_tell_anyone": ["никому не говорите", "не кладите трубку", "ешкімге айтпаңыз"],
    "remote_access_request": ["anydesk", "teamviewer", "rustdesk", "удалённый доступ",
                              "қосымшаны орнатыңыз"],
    "personal_data_request": ["подтвердите данные", "введите данные"],
    "card_data_request": ["введите карту", "подтвердите карту", "данные карты"],
    "digital_signature_request": ["эцп", "электронная подпись", "цифровая подпись"],
    "phishing_url": ["подтвердите аккаунт", "перейдите по ссылке", "получить выплату",
                     "компенсация", "штраф"],
    "money_mule_request": ["карта для переводов", "принимай деньги", "дроп", "дроппер"],
    "third_party_payment": ["перевод на физлицо", "счёт третьего лица", "на карту физлица"],
    "p2p_payment": ["p2p", "пополнение через карту"],
    "frequent_requisites_change": ["новые реквизиты", "дадим другую карту"],
    "only_prepayment": ["только предоплата", "оплата вперёд", "оплатите сейчас"],
    "no_return_policy": ["возврата нет", "без возврата"],
    "advance_fee": ["предоплата за", "страховк", "комиссия вперёд"],
    "urgency": ["только сегодня", "успей", "срочно", "ограничено по времени"],
    "limited_slots": ["мест мало", "осталось мест", "лимит"],
    "telegram_contact": ["telegram", "телеграм", "@", "тг"],
    "whatsapp_contact": ["whatsapp", "ватсап", "вотсап"],
}


# Компилируем по триггеру: совпадение только на границе слова слева
# (?<!\w), иначе стем «ставк» ловится внутри «доставка», «бонус» — внутри «абонус» и т.п.
# \w в Python для str по умолчанию покрывает кириллицу.
_KW_PATTERNS: dict[str, list[re.Pattern]] = {
    sig: [re.compile(r"(?<!\w)" + re.escape(kw)) for kw in kws]
    for sig, kws in KEYWORD_SIGNALS.items()
}


def signals_from_text(text: str) -> list[str]:
    low = text.lower()
    found = [sig for sig, pats in _KW_PATTERNS.items() if any(p.search(low) for p in pats)]
    return list(dict.fromkeys(found))


def signals_from_entities(entities: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    if entities.get("domains"):
        out.append("suspicious_domain")
        # эвристика: казино-домены попадают в combined_text, но если домен явно есть —
        # помечаем как минимум suspicious_domain; casino_domain_found ставит scenario LLM.
    if entities.get("promo_codes"):
        out.append("promo_code_found")
    if entities.get("crypto_wallets"):
        out.append("crypto_wallet_found")
    if entities.get("telegram_usernames"):
        out.append("telegram_contact")
    return list(dict.fromkeys(out))


def extract_signals(combined_text: str, entities: dict[str, list[str]]) -> list[str]:
    return list(dict.fromkeys(signals_from_text(combined_text) + signals_from_entities(entities)))


# Этапы телефонного мошенничества (ТЗ §2.2). Возвращаем список сработавших этапов
# по порядку — для демо «звонок делится на этапы».
CALL_STAGES: list[tuple[str, list[str]]] = [
    ("egov_delivery", ["доставка от egov", "доставка от госоргана", "посылка", "egov", "1414"]),
    ("sms_code", ["код из sms", "код из смс", "назовите код", "sms кодын"]),
    ("authority_escalation", ["сотрудник кнб", "сотрудник полиции", "служба безопасности",
                              "сотрудник нацбанка", "национальный банк", "ұлттық банк"]),
    ("loan_threat", ["оформляют кредит", "несие рәсімделді", "ваши данные скомпрометированы"]),
    ("safe_account", ["безопасный счёт", "страховой счёт", "переведите деньги", "қауіпсіз шот"]),
]


def detect_call_stages(text: str) -> list[str]:
    low = text.lower()
    return [stage for stage, kws in CALL_STAGES if any(kw in low for kw in kws)]
