"""Контролируемые словари из ТЗ: labels (§6), fraud_type (§7), risk_level (§8),
полный список risk_signals (§9). Держим как Enum/множества, чтобы валидировать вход
и не разъезжаться с разметкой студентов."""

from enum import Enum


class Label(str, Enum):
    legit = "legit"
    spam = "spam"
    scam = "scam"
    unclear = "unclear"


class FraudType(str, Enum):
    illegal_gambling_promo = "illegal_gambling_promo"
    fake_egov_delivery_call = "fake_egov_delivery_call"
    fake_bank_call = "fake_bank_call"
    fake_government_call = "fake_government_call"
    investment_scam = "investment_scam"
    crypto_scam = "crypto_scam"
    phishing = "phishing"
    money_mule_or_drop = "money_mule_or_drop"
    fake_seller = "fake_seller"
    fake_credit = "fake_credit"
    deepfake_financial_promo = "deepfake_financial_promo"
    legit_finance = "legit_finance"
    anti_fraud_education = "anti_fraud_education"
    ordinary_spam = "ordinary_spam"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Modality(str, Enum):
    video = "video"
    audio = "audio"
    text = "text"
    url = "url"
    image = "image"


# Полный список risk_signals (ТЗ §9). Источник истины для валидации сигналов.
RISK_SIGNALS: frozenset[str] = frozenset(
    {
        "guaranteed_income",
        "unrealistic_profit",
        "no_risk_claim",
        "urgency",
        "limited_slots",
        "telegram_contact",
        "whatsapp_contact",
        "direct_message_request",
        "referral_scheme",
        "crypto_payment",
        "crypto_wallet_found",
        "phishing_url",
        "suspicious_domain",
        "fake_authority",
        "fake_bank_employee",
        "fake_government_employee",
        "fake_egov_call",
        "safe_account",
        "sms_code_request",
        "remote_access_request",
        "do_not_tell_anyone",
        "loan_fear",
        "account_blocking_fear",
        "personal_data_request",
        "card_data_request",
        "egov_1414_code",
        "digital_signature_request",
        "possible_deepfake",
        "synthetic_voice_suspected",
        "lip_sync_anomaly",
        "financial_call_to_action",
        "illegal_gambling_promo",
        "casino_domain_found",
        "promo_code_found",
        "deposit_bonus",
        "registration_instruction",
        "fake_winner_claim",
        "money_mule_request",
        "third_party_payment",
        "p2p_payment",
        "frequent_requisites_change",
        "only_prepayment",
        "no_return_policy",
        "no_merchant_identity",
        "advance_fee",
        # сигналы, вычисляемые слоями инфраструктуры (не из текста):
        "similar_to_known_scam",  # Qdrant similarity
        "graph_entity_reuse",  # Neo4j повторяемость
    }
)
