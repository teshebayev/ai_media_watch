"""Regex-извлечение сущностей из ТЗ §10. Детерминированный первый проход
(LLM добирает названия проектов/организации/pressure-фразы вторым проходом).

Телефоны и карты по правилам безопасности (ТЗ §0) наружу отдаём только в
виде маски/хэша — см. mask_phone / hash_value.
"""

from __future__ import annotations

import hashlib
import re

RE_TELEGRAM = re.compile(r"@[A-Za-z0-9_]{5,32}")
RE_URL = re.compile(r"https?://[^\s]+|www\.[^\s]+")
RE_PHONE_KZ = re.compile(r"(\+7|8)\s?\(?7\d{2}\)?\s?\d{3}[-\s]?\d{2}[-\s]?\d{2}")
RE_MONEY = re.compile(r"\d[\d\s]{2,}\s?(₸|тг|тенге|KZT|USDT|\$)")
RE_PROMO = re.compile(r"(?i)(промокод|promo|код)\s*[:\-]?\s*([A-Z0-9]{4,20})")
RE_CRYPTO_KW = re.compile(
    r"USDT|BTC|ETH|TRC20|ERC20|BEP20|крипта|биткоин|эфир|майнинг", re.IGNORECASE
)
RE_BTC = re.compile(r"\b(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}\b")
RE_ETH = re.compile(r"0x[a-fA-F0-9]{40}")

_DOMAIN_RE = re.compile(r"https?://([^/\s]+)|www\.([^/\s]+)")

# «Голые» домены без схемы (casino-x.com, invest-pro.top). TLD-allowlist, чтобы не
# ловить сокращения («т.е.») и имена файлов. Латиница — домены не пишут кириллицей.
_BARE_DOMAIN_RE = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:com|net|org|info|biz|top|site|click|online|app|xyz|io|co|kz|ru|me)\b",
    re.IGNORECASE,
)


def _unique(seq: list[str]) -> list[str]:
    return list(dict.fromkeys(s for s in seq if s))


def mask_phone(phone: str) -> str:
    """Маскируем телефон: оставляем код страны и последние 2 цифры."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 4:
        return "***"
    return digits[:2] + "*" * (len(digits) - 4) + digits[-2:]


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def extract_urls(text: str) -> list[str]:
    return _unique(RE_URL.findall(text))


def extract_domains(text: str) -> list[str]:
    domains = []
    for m in _DOMAIN_RE.finditer(text):
        domains.append((m.group(1) or m.group(2) or "").lower())
    # голые домены без схемы
    for m in _BARE_DOMAIN_RE.finditer(text):
        domains.append(m.group(0).lower())
    # нормализуем www-префикс, чтобы www.x.com и x.com были одним узлом
    domains = [d[4:] if d.startswith("www.") else d for d in domains]
    return _unique(domains)


def extract_telegram(text: str) -> list[str]:
    return _unique(RE_TELEGRAM.findall(text))


def extract_promo_codes(text: str) -> list[str]:
    return _unique([m.group(2).upper() for m in RE_PROMO.finditer(text)])


def extract_money(text: str) -> list[str]:
    # findall с группой вернёт только группу — берём целые совпадения через finditer
    return _unique([m.group(0).strip() for m in RE_MONEY.finditer(text)])


def extract_crypto_wallets(text: str) -> list[str]:
    btc = [m.group(0) for m in RE_BTC.finditer(text)]
    eth = [m.group(0) for m in RE_ETH.finditer(text)]
    return _unique(btc + eth)


def extract_phones_masked(text: str) -> list[str]:
    return _unique([mask_phone(m.group(0)) for m in RE_PHONE_KZ.finditer(text)])


def has_crypto_keywords(text: str) -> bool:
    return RE_CRYPTO_KW.search(text) is not None


def extract_entities(text: str) -> dict[str, list[str]]:
    """Единый словарь сущностей под формат ТЗ §5 (entities)."""
    return {
        "urls": extract_urls(text),
        "domains": extract_domains(text),
        "telegram_usernames": extract_telegram(text),
        "phones": extract_phones_masked(text),  # только маска
        "promo_codes": extract_promo_codes(text),
        "crypto_wallets": extract_crypto_wallets(text),
        "money_amounts": extract_money(text),
        "organizations": [],  # добирает LLM (второй проход)
    }
