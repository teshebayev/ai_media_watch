"""Скоринг и приоритизация угроз Digital Shadow.

shadow_score — объединяет веса общего движка (core.SIGNAL_WEIGHTS) и шадоу-сигналов
(taxonomy.SHADOW_SIGNAL_WEIGHTS); risk_level берём из core (единые пороги §11).

prioritize — приоритет для аналитика: severity (risk) × confidence (сколько независимых
сигналов) × источник (даркнет тяжелее) × охват/повторяемость в графе.
"""

from __future__ import annotations

from apps.digital_shadow.taxonomy import SHADOW_SIGNAL_WEIGHTS
from core import risk_level, signal_weight


def _weight(signal: str) -> int:
    # шадоу-вес приоритетнее; иначе вес общего движка (с дефолтом)
    return SHADOW_SIGNAL_WEIGHTS.get(signal) or signal_weight(signal)


def shadow_score(signals: list[str]) -> dict:
    """{risk_score, risk_level, breakdown} с учётом шадоу-весов."""
    unique = list(dict.fromkeys(signals))
    breakdown = [{"signal": s, "weight": _weight(s)} for s in unique]
    score = min(100, sum(item["weight"] for item in breakdown))
    return {"risk_score": score, "risk_level": risk_level(score), "breakdown": breakdown}


# Источник: даркнет/leak-форум весомее обычного clearweb
_SOURCE_FACTOR = {"darknet": 1.0, "paste": 0.9, "leak_forum": 1.0, "clearweb": 0.75}

_PRIORITY_TIERS = [(0, "low"), (35, "medium"), (60, "high"), (85, "urgent")]


def prioritize(
    *,
    risk_score: int,
    signals: list[str],
    source_type: str = "clearweb",
    graph_reuse: int = 0,
) -> dict:
    """Вернуть {threat_score (0..100), priority}.

    threat = risk × confidence × source, с бонусом за повторяемость сущностей в графе.
    confidence растёт с числом независимых сигналов (до +20%).
    """
    confidence = min(1.2, 1.0 + 0.05 * max(0, len(set(signals)) - 1))
    source = _SOURCE_FACTOR.get(source_type, 0.75)
    reuse_bonus = min(15, 5 * graph_reuse)  # сущность всплывает в N источниках → +

    threat = min(100.0, risk_score * confidence * source + reuse_bonus)

    priority = "low"
    for threshold, name in _PRIORITY_TIERS:
        if threat >= threshold:
            priority = name
    return {"threat_score": round(threat, 1), "priority": priority}
