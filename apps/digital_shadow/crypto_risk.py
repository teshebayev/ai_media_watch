"""Оценка риска криптокошельков: формат, список «плохих» адресов, признаки миксеров.

Скелет с рабочими эвристиками. Реальную цепочную аналитику (кластеризация, метки бирж/миксеров)
подключать через внешний сервис/датасет адресов — точка расширения помечена TODO.
"""

from __future__ import annotations

import re

# Минимальный детект типа по формату адреса
_PATTERNS = {
    "btc": re.compile(r"\b(bc1[a-z0-9]{20,}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b"),
    "eth": re.compile(r"\b0x[a-fA-F0-9]{40}\b"),
    "tron": re.compile(r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b"),  # TRC20 (USDT часто здесь)
}

# Демонстрационный список «плохих» адресов (в проде — подгружать фид/датасет).
# TODO: заменить на загрузку из data/ или внешний сервис (chainalysis-подобный).
_BAD_WALLETS: set[str] = set()

# Признаки миксеров/тумблеров в сопроводительном тексте
_MIXER_RE = re.compile(
    r"\b(mixer|tumbler|миксер|тумблер|отмыв|launder|чистая\s+крипт)\b", re.IGNORECASE
)


def detect_wallet_type(address: str) -> str | None:
    for kind, rx in _PATTERNS.items():
        if rx.fullmatch(address) or rx.search(address):
            return kind
    return None


def assess_wallet(address: str, *, context_text: str = "") -> dict:
    """Вернуть оценку одного кошелька: тип, причины, сигналы."""
    kind = detect_wallet_type(address)
    reasons: list[str] = []
    signals: list[str] = []

    if address in _BAD_WALLETS:
        reasons.append("адрес в списке известных «плохих» кошельков")
        signals.append("bad_crypto_wallet")
    if _MIXER_RE.search(context_text):
        reasons.append("рядом признаки миксера/тумблера")
        signals.append("mixer_or_tumbler")

    return {
        "address": address,
        "type": kind or "unknown",
        "reasons": reasons,
        "signals": list(dict.fromkeys(signals)),
    }


def assess_wallets(addresses: list[str], *, context_text: str = "") -> tuple[list[dict], list[str]]:
    """Оценить список кошельков → (детали, объединённые сигналы)."""
    details, signals = [], []
    for addr in dict.fromkeys(addresses):
        a = assess_wallet(addr, context_text=context_text)
        details.append(a)
        signals.extend(a["signals"])
    return details, list(dict.fromkeys(signals))
