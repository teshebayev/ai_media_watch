"""Каноникализация значений сущностей для графа (Фаза 1: граф-мост).

Чистые функции, без зависимостей и I/O. Цель: одна и та же сущность из Media и
Shadow должна писаться в ОДИН узел Neo4j (иначе кросс-продуктовая связка не работает).
Применяется в `graph.upsert_entities` (MERGE-ключи) и `graph.entity_reuse` (поиск).

Правила нормализации (см. docs/shadow_graph_schema.md):
  - telegram: lower + срезать ведущий '@';
  - domain:   lower + срезать схему (http/https), 'www.' и хвостовые '/';
  - wallet:   только trim — адреса BTC/ETH регистрозависимы, регистр НЕ менять;
  - promo:    upper + trim.
Неизвестный kind → только trim (безопасный дефолт).
"""

from __future__ import annotations

# Синонимы имён полей сущностей → канонический kind.
_KIND_ALIASES = {
    "domain": "domain", "domains": "domain",
    "telegram": "telegram", "telegram_username": "telegram",
    "telegram_usernames": "telegram",
    "wallet": "wallet", "wallets": "wallet",
    "crypto_wallet": "wallet", "crypto_wallets": "wallet",
    "promo": "promo", "promo_code": "promo", "promo_codes": "promo",
}

_ALL_KINDS = ("domain", "telegram", "wallet", "promo")


def _canonical_kind(kind: str | None) -> str | None:
    if kind is None:
        return None
    return _KIND_ALIASES.get(kind.strip().lower())


def normalize_entity_value(kind: str | None, value: str) -> str:
    """Привести значение сущности к каноническому виду по типу `kind`."""
    v = (value or "").strip()
    if not v:
        return v
    k = _canonical_kind(kind)
    if k == "telegram":
        return (v[1:] if v.startswith("@") else v).lower()
    if k == "domain":
        v = v.lower()
        for scheme in ("https://", "http://"):
            if v.startswith(scheme):
                v = v[len(scheme):]
        # только хост: отрезаем путь/запрос/порт, чтобы site.kz, site.kz/promo,
        # site.kz:443, https://www.site.kz/p?x сходились в один узел
        v = v.split("/", 1)[0].split("?", 1)[0].split(":", 1)[0]
        if v.startswith("www."):
            v = v[4:]
        return v.strip(".")
    if k == "promo":
        return v.upper()
    # wallet и неизвестный kind — без смены регистра, только trim
    return v


def normalized_variants(value: str) -> list[str]:
    """Различные канонические формы значения по всем типам — для kind-агностичного
    поиска повторяемости (когда тип сущности на момент запроса неизвестен)."""
    seen: dict[str, None] = {}
    for k in (None, *_ALL_KINDS):
        nv = normalize_entity_value(k, value)
        if nv:
            seen.setdefault(nv, None)
    return list(seen)
