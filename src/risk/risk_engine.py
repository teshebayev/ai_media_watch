"""Детерминированный Risk Engine (ТЗ §11). Без LLM — только таблица весов.

Единый источник истины для скоринга: используется и backend-сервисом, и
оффлайн-скриптами. LLM сигналы НЕ ставит баллы (план, этап 2) — он лишь
поставляет risk_signals, а итоговый score считается здесь, детерминированно.
"""

from __future__ import annotations

# Веса сигналов из ТЗ §11. Сигналы, не указанные явно, получают вес по умолчанию.
SIGNAL_WEIGHTS: dict[str, int] = {
    "casino_domain_found": 25,
    "promo_code_found": 20,
    "registration_instruction": 20,
    "fake_winner_claim": 20,
    "sms_code_request": 45,
    "fake_government_employee": 30,
    "safe_account": 45,
    "do_not_tell_anyone": 30,
    "remote_access_request": 45,
    "guaranteed_income": 25,
    "referral_scheme": 25,
    "phishing_url": 40,
    "crypto_wallet_found": 20,
    "possible_deepfake": 25,
    "synthetic_voice_suspected": 25,
    "lip_sync_anomaly": 20,
    "graph_entity_reuse": 25,
    # доп. сигнал из плана (Qdrant similarity), согласован с командой = +20
    "similar_to_known_scam": 20,
}

DEFAULT_WEIGHT = 10

# Пороги (ТЗ §11)
THRESHOLDS = [(0, "low"), (25, "medium"), (50, "high"), (80, "critical")]


def signal_weight(signal: str) -> int:
    return SIGNAL_WEIGHTS.get(signal, DEFAULT_WEIGHT)


def score_signals(signals: list[str]) -> int:
    """Сумма весов уникальных сигналов, обрезанная до 100."""
    unique = dict.fromkeys(signals)  # дедуп с сохранением порядка
    return min(100, sum(signal_weight(s) for s in unique))


def risk_level(score: int) -> str:
    level = "low"
    for threshold, name in THRESHOLDS:
        if score >= threshold:
            level = name
    return level


def evaluate(signals: list[str]) -> dict:
    """Вернуть {score, level, breakdown}. breakdown — вклад каждого сигнала."""
    unique = list(dict.fromkeys(signals))
    breakdown = [{"signal": s, "weight": signal_weight(s)} for s in unique]
    score = min(100, sum(item["weight"] for item in breakdown))
    return {"risk_score": score, "risk_level": risk_level(score), "breakdown": breakdown}


if __name__ == "__main__":
    # Быстрая проверка: пример kz_call_001 из ТЗ должен давать critical.
    demo = ["fake_egov_call", "sms_code_request", "fake_government_employee",
            "safe_account", "do_not_tell_anyone"]
    print(evaluate(demo))
