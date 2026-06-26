"""Оркестратор Digital Shadow: сырой элемент → находка (ShadowFinding).

Reuse общего движка (`core`): извлечение сущностей, базовые сигналы, OSINT, Neo4j-граф.
Поверх — шадоу-специфика: лексикон контрабанды/дропов, крипто-риск, детект утечек, приоритизация.

Граф — ТОТ ЖЕ Neo4j, что у AI Media Watch → сущности из даркнета и из соцвидео сходятся
в общие узлы (кросс-продуктовая теневая сеть).
"""

from __future__ import annotations

import logging
import os

from apps.digital_shadow import crypto_risk, leak_detector, similarity, taxonomy
from apps.digital_shadow.prioritization import prioritize, shadow_score
from apps.digital_shadow.schemas import ShadowFinding, ShadowItem
from core import (
    extract_regex_entities,
    extract_signals,
    graph_service,
    osint_service,
)

logger = logging.getLogger(__name__)

# Сущности, по которым считаем повторяемость в графе (скрытые связи).
# Имя поля = kind для нормализации (entity_norm понимает эти алиасы).
_REUSE_FIELDS = ("domains", "crypto_wallets", "telegram_usernames", "promo_codes")


async def analyze_item(item: ShadowItem, *, driver=None, watchlist: set[str] | None = None,
                       bad_entities: set[str] | None = None, qdrant=None) -> ShadowFinding:
    """Проанализировать один элемент. driver (Neo4j AsyncDriver) — опц.: upsert + reuse.
    watchlist — отслеживаемые значения (совпадение → watchlisted).
    bad_entities — индикаторы с подтверждённым abuse (репутация → known_bad_entity).
    qdrant — клиент Qdrant: семантическое сходство с известными листингами."""
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
    flat = (entities.domains + entities.crypto_wallets
            + entities.telegram_usernames + entities.promo_codes)
    if watchlist and any(v in watchlist for v in flat):             # отслеживаемые сущности
        signals.append("watchlisted")
    if bad_entities and any(v in bad_entities for v in flat):       # репутация (flywheel)
        signals.append("known_bad_entity")
    if item.source_type == "darknet":
        signals.append("darknet_listing")
    if qdrant is not None:                                          # семантическое сходство
        matched, _top = await similarity.similar_listing(qdrant, text)
        if matched:
            signals.append("similar_to_known_listing")
    signals = list(dict.fromkeys(signals))

    # категорию определяем ДО графа — чтобы записать её в узел ShadowItem
    # (нужно для кросс-категорийного анализа). Сигналы, влияющие на категорию
    # (darknet_listing и лексикон), уже посчитаны; graph_entity_reuse на категорию не влияет.
    category = taxonomy.classify_category(signals, lex_categories)

    # 3) граф: upsert сущностей (+ category/source_type в узел) + повторяемость
    graph_reuse = 0
    if driver is not None:
        try:
            await graph_service.upsert_entities(
                driver, item.id, entities, source_label="ShadowItem",
                node_props={"category": category, "source_type": item.source_type})
            for field in _REUSE_FIELDS:
                for value in ent_dict.get(field, []):
                    graph_reuse += await graph_service.entity_reuse(driver, value, kind=field)
        except Exception as e:  # noqa: BLE001 — граф недоступен → продолжаем без reuse
            logger.warning("граф недоступен для %s, продолжаю без reuse: %s", item.id, e)
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
        breakdown=scored["breakdown"],
        entities=entities,
        wallet_risks=wallet_risks,
        evidence=_build_evidence(item, text, scored["breakdown"]),
    )


def _build_evidence(item: ShadowItem, text: str, breakdown: list[dict]) -> list[str]:
    """Объяснимость (Фаза 3): почему находка. Заголовок + совпавшие слова лексикона +
    топ-3 вклада в риск-скоринг — чтобы аналитик видел основание."""
    ev: list[str] = []
    if item.title:
        ev.append(item.title)
    terms = taxonomy.matched_lexicon_terms(text)
    if terms:
        ev.append("лексикон: " + ", ".join(terms[:8]))
    top = sorted(breakdown, key=lambda b: b["weight"], reverse=True)[:3]
    if top:
        # человекочитаемое объяснение топ-вклада: «<описание> (+вес)»
        ev.append("почему: " + "; ".join(
            f"{taxonomy.describe_signal(b['signal'])} (+{b['weight']})" for b in top))
    return ev
