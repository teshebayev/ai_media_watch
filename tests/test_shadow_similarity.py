"""Тесты Фазы 3: семантическое сходство (чистая логика) + объяснимость evidence."""

from __future__ import annotations

import asyncio

from apps.digital_shadow import similarity
from apps.digital_shadow.pipeline import analyze_item
from apps.digital_shadow.schemas import ShadowItem


def test_is_similar_threshold_and_label():
    near_bad = [{"score": 0.91, "payload": {"label": "bad"}}]
    near_legit = [{"score": 0.95, "payload": {"label": "legit"}}]
    far_bad = [{"score": 0.5, "payload": {"label": "bad"}}]
    assert similarity._is_similar(near_bad) is True
    assert similarity._is_similar(near_legit) is False   # похоже, но на legit → не сигнал
    assert similarity._is_similar(far_bad) is False       # bad, но далеко
    assert similarity._is_similar([]) is False


def test_similar_listing_no_client():
    matched, top = asyncio.run(similarity.similar_listing(None, "любой текст"))
    assert matched is False and top == 0.0


def test_evidence_has_lexicon_and_breakdown():
    """ShadowFinding.evidence содержит совпавшие слова лексикона и топ-вклады."""
    item = ShadowItem(id="ev", source_type="darknet",
                      title="Закладки", text="Закладки по городу, оплата USDT, session")
    f = asyncio.run(analyze_item(item, driver=None))
    joined = " | ".join(f.evidence)
    assert "лексикон:" in joined
    # топ-вклады в риск — человекочитаемым описанием (объяснимость для аналитика)
    assert "почему:" in joined
    assert "(+" in joined            # с весами вклада
