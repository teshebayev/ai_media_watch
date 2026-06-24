"""Тесты пайплайна Digital Shadow (чисто, без графа/сети). Защищают детекцию категорий,
границы лексикона (регрессии «оклад»→drug, легальный вейп→контрабанда) и приоритизацию.
"""

from __future__ import annotations

import asyncio

from apps.digital_shadow import prioritization, taxonomy
from apps.digital_shadow.pipeline import analyze_item
from apps.digital_shadow.schemas import ShadowItem


def _run(text: str, src: str = "clearweb"):
    item = ShadowItem(id="t", source_type=src, text=text)
    return asyncio.run(analyze_item(item, driver=None))


def test_categories_detected():
    assert _run("Ищем дропов, карта в аренду за %, приём переводов, @x, оплата USDT").category \
        == "drop_recruitment"
    assert _run("Продам базу РК, свежий дамп, пробив, ИИН ************", "paste").category \
        == "kz_data_leak"
    assert _run("Elf bar оптом, жидкости без акциз, @vape_kz").category == "contraband_vape"
    f = _run("Закладки по городу, товар в наличии, оплата только USDT, session", "darknet")
    assert f.category == "drug_trafficking"
    assert "darknet_listing" in f.signals


def test_legit_not_flagged():
    f = _run("Продам вейп, чек и гарантия, оригинал, продажа только 21+.")
    assert f.category == "unknown"
    assert f.risk_level in ("low", "medium")


def test_lexicon_word_boundaries():
    # «оклад» НЕ должен ловиться как наркотический «клад»
    sigs, cats = taxonomy.detect_lexicon_signals("Ищем менеджера, оклад плюс бонус, офис")
    assert "drug_slang" not in sigs
    assert "drug_trafficking" not in cats
    # легальная розничная продажа вейпа НЕ контрабанда
    _, cats2 = taxonomy.detect_lexicon_signals("Продам вейп, чек и гарантия, оригинал")
    assert "contraband_vape" not in cats2


def test_watchlist_signal():
    txt = "Перевод на кошелёк bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"
    item = ShadowItem(id="w", source_type="paste", text=txt)
    f = asyncio.run(analyze_item(
        item, driver=None, watchlist={"bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"}))
    assert "watchlisted" in f.signals
    # без watchlist — сигнала нет
    f2 = asyncio.run(analyze_item(item, driver=None))
    assert "watchlisted" not in f2.signals


def test_priority_weighs_source():
    """Даркнет-источник тяжелее clearweb при тех же сигналах."""
    dn = prioritization.prioritize(risk_score=80, signals=["drug_slang"], source_type="darknet")
    cw = prioritization.prioritize(risk_score=80, signals=["drug_slang"], source_type="clearweb")
    assert dn["threat_score"] >= cw["threat_score"]
