"""Тесты Фазы 2: извлечение индикаторов (репутация/watchlist) и active learning.
Чисто, без БД — проверяем чистые функции."""

from __future__ import annotations

from apps.digital_shadow import persistence
from apps.digital_shadow.leak_detector import mask_pii
from apps.digital_shadow.train_classifier import reviews_to_examples


def test_mask_pii_hides_iin_phone_keeps_wallet():
    """§0: телефоны/ИИН/карты маскируются, крипто-адрес не задевается."""
    text = ("Дамп РК, ИИН 901231300123, тел +7 707 123 45 67, "
            "карта 4400430012345678, кошелёк bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh")
    masked = mask_pii(text)
    assert "901231300123" not in masked            # ИИН скрыт
    assert "4400430012345678" not in masked         # карта скрыта
    assert "7071234567" not in masked.replace(" ", "")  # телефон скрыт
    assert "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh" in masked  # адрес цел


def test_safe_preview_masks_text():
    out = persistence._safe_preview("позвоните 87011234567, ИИН 901231300123", [])
    assert "87011234567" not in out and "901231300123" not in out


def test_indicators_only_public_indicators():
    """Берём только публичные индикаторы (домены/кошельки/@ник/промо), НЕ ПДн (§0)."""
    ents = {
        "domains": ["casino-x.com"], "crypto_wallets": ["bc1qabc"],
        "telegram_usernames": ["@scam_kz"], "promo_codes": ["WIN5000"],
        "phones": ["+7700..."], "organizations": ["Нацбанк"], "urls": ["http://x"],
    }
    inds = persistence._indicators(ents)
    assert {v for v, _ in inds} == {"casino-x.com", "bc1qabc", "@scam_kz", "WIN5000"}
    assert dict(inds)["bc1qabc"] == "wallet"
    assert dict(inds)["@scam_kz"] == "telegram"


def test_indicators_empty_and_dirty():
    assert persistence._indicators({}) == []
    assert persistence._indicators({"domains": ["", "  ", None]}) == []


def test_reviews_to_examples_empty():
    """Active learning не падает на пустых ревью (DoD)."""
    assert reviews_to_examples([]) == ([], [])


def test_reviews_to_examples_maps_decisions():
    rows = [
        {"text": "продам базу рк дамп", "category": "kz_data_leak", "decision": "confirm"},
        {"text": "легальный магазин вейпов", "category": "contraband_vape", "decision": "dismiss"},
        {"text": "пропустить", "category": "drug_trafficking", "decision": "in_review"},
        {"text": None, "category": "kz_data_leak", "decision": "confirm"},  # без текста → skip
    ]
    X, y = reviews_to_examples(rows)
    assert X == ["продам базу рк дамп", "легальный магазин вейпов"]
    assert y == ["kz_data_leak", "unknown"]   # confirm→категория, dismiss→hard-negative
