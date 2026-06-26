"""Юнит-тесты regex-экстракторов (ТЗ §10)."""

from src.extraction.regex_extractors import (
    extract_crypto_wallets,
    extract_entities,
    extract_promo_codes,
    extract_telegram,
    mask_phone,
)


def test_promo_code():
    assert "PROMO777" in extract_promo_codes("вводи промокод PROMO777")


def test_telegram():
    assert "@casino_manager" in extract_telegram("пиши @casino_manager в тг")


def test_phone_masked_not_raw():
    masked = mask_phone("+7 701 123 45 67")
    assert masked.startswith("77") and masked.endswith("67") and "*" in masked


def test_crypto_wallets_btc_eth_tron():
    """Кошельки BTC/ETH/TRON извлекаются (TRC20 — типичная оплата в KZ крипто-преступности)."""
    text = ("оплата BTC bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh "
            "или ETH 0x0000000000000000000000000000000000001234 "
            "или USDT TQn9Y2khEsLJW1ChVWFMSMeRDow5Kcbk2v")
    wallets = extract_crypto_wallets(text)
    assert "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh" in wallets
    assert "0x0000000000000000000000000000000000001234" in wallets
    assert "TQn9Y2khEsLJW1ChVWFMSMeRDow5Kcbk2v" in wallets    # ранее не ловился


def test_extract_entities_shape():
    ents = extract_entities("casino-example.com промокод PROMO777 @mgr 500 000 ₸")
    assert set(ents) == {
        "urls", "domains", "telegram_usernames", "phones",
        "promo_codes", "crypto_wallets", "money_amounts", "organizations",
    }
    assert "PROMO777" in ents["promo_codes"]
