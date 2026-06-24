"""Контракт общего движка `core`. Если падает — кто-то сломал общий слой,
от которого зависят ОБА продукта (AI Media Watch и Digital Shadow). Менять core —
только осознанно и с обновлением этого теста. Чистый тест: без сети/GPU/БД.
"""

from __future__ import annotations

import core


def test_public_api_present():
    """Все имена из core.__all__ реально экспортируются (защита от случайного удаления)."""
    missing = [name for name in core.__all__ if not hasattr(core, name)]
    assert not missing, f"в core пропали экспорты: {missing}"


def test_risk_engine_contract():
    res = core.evaluate(["sms_code_request", "safe_account"])  # 45 + 45
    assert res["risk_score"] == 90
    assert res["risk_level"] == "critical"
    assert core.signal_weight("phishing_url") == 40
    assert core.risk_level(0) == "low"


def test_risk_signals_vocab():
    assert isinstance(core.RISK_SIGNALS, frozenset)
    assert "sms_code_request" in core.RISK_SIGNALS
    # enum-значения на месте
    assert core.RiskLevel("critical").value == "critical"
    assert core.Label("scam").value == "scam"


def test_entity_and_signal_extraction():
    text = "Регистрация на casino-x.com промокод WIN5000, пишите @scam_kz, кошелёк " \
           "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"
    ent = core.extract_regex_entities(text)
    assert any("casino-x.com" in d for d in ent.domains)
    assert "@scam_kz" in ent.telegram_usernames
    assert ent.crypto_wallets, "крипто-кошелёк должен извлекаться"
    signals = core.extract_signals(text, ent.model_dump())
    assert isinstance(signals, list)


def test_service_layers_exposed():
    """Слои инфраструктуры доступны через core с ожидаемыми функциями."""
    for fn in ("upsert_entities", "entity_reuse", "neighborhood", "overview"):
        assert callable(getattr(core.graph_service, fn))
    for fn in ("search_similar", "embed", "similarity_signal"):
        assert callable(getattr(core.similarity_service, fn))
    for fn in ("osint_signals", "domain_signals"):
        assert callable(getattr(core.osint_service, fn))


def test_graph_supports_wallet_reuse():
    """REUSE/NEIGHBORHOOD должны искать и по address (кросс-продуктовая связка по кошелькам)."""
    assert "e.address" in core.graph_service.REUSE_QUERY
    assert "e.address" in core.graph_service.NEIGHBORHOOD_QUERY
    assert "ShadowItem" in core.graph_service._SOURCE_LABELS


def test_entity_normalization_merges_nodes():
    """Каноникализация: одна сущность из Media и Shadow → ОДИН узел графа.
    @Work_Fast == @work_fast, www.site.kz/ == site.kz, промокод регистронезависим.
    """
    n = core.normalize_entity_value
    # telegram: регистр и ведущий @ не должны плодить дубли
    assert n("telegram", "@Work_Fast") == n("telegram", "@work_fast") == "work_fast"
    assert n("telegram_usernames", "@Work_Fast") == "work_fast"  # алиас имени поля
    # domain: схема/www/порт/путь/запрос срезаются → только хост (один узел)
    assert n("domain", "www.Site.kz/") == n("domain", "https://site.kz") == "site.kz"
    assert n("domain", "https://www.site.kz/promo?ref=1") == "site.kz"
    assert n("domain", "site.kz:443") == "site.kz"
    # promo — в верхний регистр; wallet — регистр СОХРАНЯЕТСЯ (адреса регистрозависимы)
    assert n("promo", "win5000") == "WIN5000"
    addr = "bc1QXY2KGdygjrsqtzq2n0"
    assert n("wallet", addr) == addr
    # variants содержат каноническую форму → REUSE найдёт узел без знания kind
    assert "work_fast" in core.normalized_variants("@Work_Fast")


def test_reuse_query_uses_normalized_values():
    """entity_reuse ищет по списку канонических форм ($values), а не по сырому значению."""
    assert "$values" in core.graph_service.REUSE_QUERY
    assert "$values" in core.graph_service.NEIGHBORHOOD_QUERY
