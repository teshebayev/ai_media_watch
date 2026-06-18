"""OSINT / репутация доменов и URL (агент из ТЗ §2).

Два уровня:
  1. Эвристика репутации (офлайн, всегда): подозрительные TLD, тайпсквоттинг KZ-брендов
     (kaspi/halyk/egov…), «мусорная» структура (много дефисов/цифр, IP-хост) → suspicious_domain,
     для бренд-лукалайков → phishing_url.
  2. PhishTank (опционально, сеть, флаг ENABLE_PHISHTANK): проверка URL в базе фишинга.

Сигналы — из контролируемого словаря §9 (phishing_url, suspicious_domain).
"""

from __future__ import annotations

import re

import httpx

from backend.app.config import get_settings

SUSPICIOUS_TLDS = {
    "top", "click", "xyz", "site", "online", "icu", "cc", "tk", "ml", "ga", "gq",
    "work", "link", "rest", "fit", "live", "shop", "buzz", "monster", "lol", "win",
}

# Бренд → официальные домены (всё остальное с этим словом в имени — лукалайк).
KZ_BRANDS = {
    "kaspi": {"kaspi.kz", "kaspi.com"},
    "halyk": {"halykbank.kz", "halyk.kz"},
    "egov": {"egov.kz"},
    "jusan": {"jusan.kz"},
    "forte": {"fortebank.com", "forte.kz"},
    "homebank": {"homebank.kz"},
    "kazpost": {"post.kz", "kazpost.kz"},
    "olx": {"olx.kz"},
    "kolesa": {"kolesa.kz"},
    "krisha": {"krisha.kz"},
    "sberbank": {"sberbank.kz"},
    "1414": set(),  # eGov SMS-код — упоминание в домене подозрительно
}

_IP_HOST = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def _normalize(d: str) -> str:
    d = d.lower().strip().rstrip(".")
    if d.startswith("www."):
        d = d[4:]
    return d.split("/")[0]


def domain_signals(domains: list[str], urls: list[str] | None = None) -> list[str]:
    """Офлайн-эвристика репутации → список risk-сигналов (§9)."""
    sig: set[str] = set()
    cands = list(domains or [])
    for u in urls or []:
        m = re.search(r"https?://([^/\s]+)", u)
        if m:
            cands.append(m.group(1))

    for raw in cands:
        d = _normalize(raw)
        if not d or "." not in d:
            continue
        host = d.split(".")[0]
        tld = d.rsplit(".", 1)[-1]

        # тайпсквоттинг известного бренда на НЕ официальном домене
        for brand, official in KZ_BRANDS.items():
            if brand in d and d not in official:
                sig.add("phishing_url")
                sig.add("suspicious_domain")

        if tld in SUSPICIOUS_TLDS:
            sig.add("suspicious_domain")
        if _IP_HOST.match(d.rsplit(":", 1)[0]):
            sig.add("suspicious_domain")
        if host.count("-") >= 2 or sum(c.isdigit() for c in host) >= 4:
            sig.add("suspicious_domain")
    return list(sig)


def _phishtank_check(urls: list[str]) -> bool:
    """PhishTank checkurl (best-effort, сеть). True — найден верифицированный фишинг."""
    s = get_settings()
    api = "https://checkurl.phishtank.com/checkurl/"
    headers = {"User-Agent": "phishtank/finguard"}
    for u in (urls or [])[:5]:
        try:
            data = {"url": u, "format": "json"}
            if s.phishtank_api_key:
                data["app_key"] = s.phishtank_api_key
            r = httpx.post(api, data=data, headers=headers, timeout=8)
            r.raise_for_status()
            res = r.json().get("results", {})
            if res.get("in_database") and res.get("valid"):
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def osint_signals(domains: list[str], urls: list[str] | None = None) -> list[str]:
    """Все OSINT-сигналы: эвристика всегда + PhishTank по флагу."""
    s = get_settings()
    sig = set(domain_signals(domains, urls))
    if s.enable_phishtank and urls:
        if _phishtank_check(urls):
            sig.add("phishing_url")
    return list(sig)
