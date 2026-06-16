"""Юнит-тест Risk Engine (план, этап 6): kz_call_001 из ТЗ → critical."""

from src.risk.risk_engine import evaluate, risk_level, score_signals


def test_kz_call_001_is_critical():
    signals = [
        "fake_egov_call",
        "sms_code_request",
        "fake_government_employee",
        "safe_account",
        "do_not_tell_anyone",
    ]
    result = evaluate(signals)
    assert result["risk_level"] == "critical"
    assert result["risk_score"] >= 80


def test_gambling_video_is_high_or_above():
    signals = [
        "illegal_gambling_promo",
        "promo_code_found",
        "casino_domain_found",
        "financial_call_to_action",
    ]
    assert evaluate(signals)["risk_level"] in {"high", "critical"}


def test_score_capped_at_100():
    assert score_signals(["sms_code_request"] * 10) <= 100


def test_thresholds():
    assert risk_level(0) == "low"
    assert risk_level(24) == "low"
    assert risk_level(25) == "medium"
    assert risk_level(50) == "high"
    assert risk_level(80) == "critical"


def test_dedup_signals():
    # дубли не накручивают score
    assert score_signals(["safe_account", "safe_account"]) == 45
