"""Тесты демо-датасета кластеров: листинги делят индикаторы → классифицируются по торговлям,
и один кошелёк мостит наркотики↔дропы (кросс-категория). Без графа/сети."""

from __future__ import annotations

import asyncio

from apps.digital_shadow.collectors.demo_clusters import _W_BRIDGE, DemoClusterCollector
from apps.digital_shadow.pipeline import analyze_item


def _run(collector, query=None):
    async def go():
        return [it async for it in collector.collect(query)]
    return asyncio.run(go())


def test_demo_yields_all_trades():
    items = _run(DemoClusterCollector())
    assert len(items) >= 10
    # каждый вид торговли представлен ≥2 листингами (для кластера)
    prefixes = [i.id.rsplit("_", 1)[0] for i in items]
    for trade in ("cl_vape", "cl_alco", "cl_drug", "cl_drop", "cl_leak"):
        assert prefixes.count(trade) >= 2, trade


def test_demo_categories_classify_correctly():
    want = {
        "cl_vape_1": "contraband_vape", "cl_alco_1": "contraband_alcohol",
        "cl_drug_1": "drug_trafficking", "cl_drop_1": "drop_recruitment",
        "cl_leak_1": "kz_data_leak",
    }
    items = {i.id: i for i in _run(DemoClusterCollector())}

    async def cat(item):
        return (await analyze_item(item, driver=None)).category

    for cid, expected in want.items():
        assert asyncio.run(cat(items[cid])) == expected, cid


def test_bridge_wallet_links_drugs_and_drops():
    """Мост-кошелёк присутствует и в наркотиках, и в дропах → основа кросс-категории."""
    items = {i.id: i.text for i in _run(DemoClusterCollector())}
    assert _W_BRIDGE in items["cl_drug_2"]
    assert _W_BRIDGE in items["cl_drop_2"]
