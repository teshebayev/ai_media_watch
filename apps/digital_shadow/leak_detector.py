"""Детектор утечек/продажи баз данных РК.

Ставит сигналы по признакам: упоминание дампа/слива/пробива + KZ-привязка (.kz, «база РК/Казахстан»)
+ наличие в тексте паттерна ИИН (12 цифр) или связки ПДн.

⚠️ §0: реальные ПДн из дампов НЕ сохраняем. Фиксируем только ФАКТ и маскированные индикаторы;
сам текст дампа не персистим. `mask_iins` приводит найденные 12-значные последовательности к маске.
"""

from __future__ import annotations

import re

_BREACH_RE = re.compile(
    r"\b(слив\s+баз|слил\s+баз|продам\s+баз|дамп|пробив|leaked\s+database|database\s+dump|утечк)\b",
    re.IGNORECASE,
)
_KZ_RE = re.compile(
    r"\b(база\s+рк|база\s+казахстан|казахстан|\.kz\b|республик[аи]\s+казахстан)\b", re.IGNORECASE
)
# ИИН РК — 12 цифр (детект паттерна, не валидация и не хранение)
_IIN_RE = re.compile(r"(?<!\d)\d{12}(?!\d)")
_PII_RE = re.compile(r"\b(фио|иин|паспорт|телефон[аы]?|адрес[а]?)\b", re.IGNORECASE)


def mask_iins(text: str) -> str:
    """Замаскировать 12-значные последовательности (потенциальные ИИН) перед логированием."""
    return _IIN_RE.sub("************", text)


# Телефоны (в т.ч. с разделителями) и длинные числовые цепочки (ИИН/карты).
# Класс [\d\s\-()] не включает буквы → крипто-адреса (hex/base58) не задеваются.
_PHONE_LIKE_RE = re.compile(r"(?<![\w])[+(]?\d[\d\s\-()]{6,}\d")
_LONGNUM_RE = re.compile(r"(?<!\d)\d{7,}(?!\d)")


def mask_pii(text: str) -> str:
    """Замаскировать потенциальные ПДн в тексте перед персистом/показом (§0):
    телефоны, ИИН (12 цифр), длинные числовые цепочки (карты). Крипто-адреса не трогаем."""
    t = _PHONE_LIKE_RE.sub("«номер скрыт»", text)
    return _LONGNUM_RE.sub("************", t)


def detect_leak_signals(text: str) -> list[str]:
    """Вернуть сигналы утечки БД РК."""
    signals: list[str] = []
    has_breach = bool(_BREACH_RE.search(text))
    has_kz = bool(_KZ_RE.search(text))

    if has_breach and has_kz:
        signals.append("kz_data_leak")
    # упоминание дампа с ИИН/ПДн
    if has_breach and (_IIN_RE.search(text) or _PII_RE.search(text)):
        signals.append("iin_dump_mention")
    return list(dict.fromkeys(signals))
