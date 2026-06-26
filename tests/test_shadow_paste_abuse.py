"""Тесты paste-коллектора (фильтр по утечкам БД РК, офлайн-fetch) и ингеста crypto-abuse фида."""

from __future__ import annotations

import asyncio

from apps.digital_shadow import crypto_risk
from apps.digital_shadow.collectors.paste_sites import (
    PasteSiteCollector,
    is_kz_leak_relevant,
)


def _collect(collector, query=None):
    async def run():
        return [item async for item in collector.collect(query)]
    return asyncio.run(run())


def test_relevance_filter():
    assert is_kz_leak_relevant("Продам базу Казахстан, свежий дамп, ИИН, ФИО") is True
    assert is_kz_leak_relevant("Просто заметка про погоду") is False


def test_paste_collector_keeps_only_kz_leaks():
    pages = {
        "u1": "Продам базу РК: свежий слив, дамп ИИН и ФИО, контакт jabber",
        "u2": "Рецепт борща и список покупок",        # нерелевантно → отфильтровать
    }

    async def fake_fetch(url):
        return pages.get(url)

    c = PasteSiteCollector(["u1", "u2"], fetch=fake_fetch)
    items = _collect(c)
    assert len(items) == 1
    assert items[0].source_type == "paste"
    assert items[0].source_url == "u1"


def test_paste_collector_skips_missing_pages():
    async def fake_fetch(url):
        return None

    c = PasteSiteCollector(["x"], fetch=fake_fetch)
    assert _collect(c) == []


def test_paste_kz_only_false_passes_through():
    async def fake_fetch(url):
        return "любой текст без утечки"

    c = PasteSiteCollector(["x"], fetch=fake_fetch, kz_only=False)
    assert len(_collect(c)) == 1


def test_ingest_abuse_feed_extracts_addresses():
    feed = (
        "# chainabuse export\n"
        "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh,scam,2024\n"
        "0x0000000000000000000000000000000000001234;mixer\n"
        "не-адрес строка без кошелька\n"
    )
    before = crypto_risk.detect_wallet_type  # touch to ensure import side-effects ok
    assert before is not None
    n = crypto_risk.ingest_abuse_feed(feed)
    assert n >= 2
    # теперь адрес из фида помечается как bad
    a = crypto_risk.assess_wallet("bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh")
    assert "bad_crypto_wallet" in a["signals"]
