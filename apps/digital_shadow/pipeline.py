"""Оркестратор Digital Shadow: сырой элемент → находка (ShadowFinding).

Reuse общего движка (`core`): извлечение сущностей, базовые сигналы, OSINT, Neo4j-граф.
Поверх — шадоу-специфика: лексикон контрабанды/дропов, крипто-риск, детект утечек, приоритизация.

Граф — ТОТ ЖЕ Neo4j, что у AI Media Watch → сущности из даркнета и из соцвидео сходятся
в общие узлы (кросс-продуктовая теневая сеть).
"""

from __future__ import annotations

import os

from apps.digital_shadow import crypto_risk, leak_detector, taxonomy
from apps.digital_shadow.prioritization import prioritize, shadow_score
from apps.digital_shadow.schemas import ShadowFinding, ShadowItem
from core import (
    extract_regex_entities,
    extract_signals,
    graph_service,
    osint_service,
)

# Сущности, по которым считаем повторяемость в графе (скрытые связи).
_REUSE_FIELDS = ("domains", "crypto_wallets", "telegram_usernames", "promo_codes")


async def analyze_item(item: ShadowItem, *, driver=None, watchlist: set[str] | None = None
                       ) -> ShadowFinding:
    """Проанализировать один элемент. driver (Neo4j AsyncDriver) — опц.: upsert + reuse.
    watchlist — множество отслеживаемых значений (кошельки/домены/@ник): совпадение → сигнал."""
    text = item.text or ""

    # 1) сущности (общий regex-движок) + словарное представление для сигналов
    entities = extract_regex_entities(text)
    ent_dict = entities.model_dump()

    # 2) сигналы из разных слоёв
    signals: list[str] = []
    signals += extract_signals(text, ent_dict)                       # базовые (core)
    lex_signals, lex_categories = taxonomy.detect_lexicon_signals(text)
    signals += lex_signals                                           # контрабанда/дропы/утечки
    signals += osint_service.osint_signals(entities.domains, entities.urls)  # репутация доменов
    signals += leak_detector.detect_leak_signals(text)              # утечки БД РК
    wallet_risks, wallet_signals = crypto_risk.assess_wallets(
        entities.crypto_wallets, context_text=text
    )
    signals += wallet_signals                                       # крипто-риск
    if watchlist:                                                   # отслеживаемые сущности
        flat = (entities.domains + entities.crypto_wallets
                + entities.telegram_usernames + entities.promo_codes)
        if any(v in watchlist for v in flat):
            signals.append("watchlisted")
    if item.source_type == "darknet":
        signals.append("darknet_listing")
    signals = list(dict.fromkeys(signals))

    # 3) граф: upsert сущностей + повторяемость (скрытые связи между источниками)
    graph_reuse = 0
    if driver is not None:
        try:
            await graph_service.upsert_entities(
                driver, item.id, entities, source_label="ShadowItem")
            for field in _REUSE_FIELDS:
                for value in ent_dict.get(field, []):
                    graph_reuse += await graph_service.entity_reuse(driver, value)
        except Exception:  # noqa: BLE001 — граф недоступен → продолжаем без reuse
            graph_reuse = 0
    if graph_reuse > 0:
        signals.append("graph_entity_reuse")
        signals = list(dict.fromkeys(signals))

    # 4) скоринг (core+шадоу веса) + приоритизация
    scored = shadow_score(signals)
    prio = prioritize(
        risk_score=scored["risk_score"],
        signals=signals,
        source_type=item.source_type,
        graph_reuse=graph_reuse,
    )
    category = taxonomy.classify_category(signals, lex_categories)

    # 4b) ML-fallback: правила не определили категорию → спросить обученный классификатор
    #     (только при SHADOW_ML=1 и наличии модели; по умолчанию выключено).
    if category == "unknown" and os.getenv("SHADOW_ML"):
        from apps.digital_shadow import classifier
        ml = classifier.predict(text)
        if ml and ml[1] >= float(os.getenv("SHADOW_ML_THRESHOLD", "0.6")):
            category = ml[0]
            signals = list(dict.fromkeys([*signals, "ml_category"]))

    return ShadowFinding(
        id=item.id,
        source_type=item.source_type,
        source_url=item.source_url,
        category=category,
        risk_score=scored["risk_score"],
        risk_level=scored["risk_level"],
        priority=prio["priority"],
        threat_score=prio["threat_score"],
        signals=signals,
        entities=entities,
        wallet_risks=wallet_risks,
        evidence=[item.title] if item.title else [],
    )
