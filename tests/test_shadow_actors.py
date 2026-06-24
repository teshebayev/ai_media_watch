"""Тесты кластеров акторов (Фаза 1): чистая агрегация union-find + async-путь с фейк-драйвером.
Без сети/Neo4j — фейковый driver отдаёт заранее заданные рёбра.
"""

from __future__ import annotations

import asyncio

from apps.digital_shadow import actors


def test_build_clusters_groups_by_shared_source():
    """Две сущности, упомянутые одним источником, попадают в один кластер."""
    edges = [
        {"entity": "casino-x.com", "etype": "Domain", "sid": "s1", "skind": "ShadowItem"},
        {"entity": "bc1qabc", "etype": "Wallet", "sid": "s1", "skind": "ShadowItem"},
        # отдельный источник с отдельной сущностью → второй кластер
        {"entity": "@solo_kz", "etype": "TelegramUsername", "sid": "s2", "skind": "ShadowItem"},
    ]
    clusters = actors._build_clusters(edges)
    assert len(clusters) == 2
    big = clusters[0]
    assert big["size"] == 2
    assert {e["value"] for e in big["entities"]} == {"casino-x.com", "bc1qabc"}
    assert big["sources"] == 1


def test_build_clusters_transitive_merge_via_shared_entity():
    """Источники, делящие сущность (кошелёк), сливаются в один кластер транзитивно."""
    edges = [
        {"entity": "w1", "etype": "Wallet", "sid": "video1", "skind": "Video"},
        {"entity": "w1", "etype": "Wallet", "sid": "dn1", "skind": "ShadowItem"},
        {"entity": "dom1", "etype": "Domain", "sid": "dn1", "skind": "ShadowItem"},
    ]
    clusters = actors._build_clusters(edges)
    assert len(clusters) == 1
    c = clusters[0]
    assert c["cross_product"] is True          # Video + ShadowItem
    assert c["sources"] == 2
    assert sorted(c["kinds"]) == ["ShadowItem", "Video"]


def test_cross_product_cluster_sorted_first():
    edges = [
        {"entity": "solo", "etype": "Domain", "sid": "s1", "skind": "ShadowItem"},
        {"entity": "bridge", "etype": "Wallet", "sid": "v1", "skind": "Video"},
        {"entity": "bridge", "etype": "Wallet", "sid": "s2", "skind": "ShadowItem"},
    ]
    clusters = actors._build_clusters(edges)
    assert clusters[0]["cross_product"] is True   # мост — выше


def test_build_clusters_no_cross_type_collision():
    """H2: одинаковая строка у разных типов (PromoCode 'SOLO' vs Domain 'SOLO') —
    это РАЗНЫЕ узлы, не должны схлопываться в одного актора."""
    edges = [
        {"entity": "SOLO", "etype": "PromoCode", "sid": "s1", "skind": "ShadowItem"},
        {"entity": "SOLO", "etype": "Domain", "sid": "s2", "skind": "ShadowItem"},
    ]
    clusters = actors._build_clusters(edges)
    # два разных источника, две разные сущности — не один кластер из-за совпадения строки
    assert len(clusters) == 2
    assert all(c["size"] == 1 for c in clusters)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def __aiter__(self):
        async def gen():
            for r in self._rows:
                yield r
        return gen()


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def run(self, *a, **k):
        return _FakeResult(self._rows)


class _FakeDriver:
    def __init__(self, rows):
        self._rows = rows

    def session(self):
        return _FakeSession(self._rows)


def test_actor_clusters_async_with_fake_driver():
    # новый row-shape: сущность + collect её источников (srcs)
    rows = [
        {"entity": "casino-x.com", "etype": "Domain", "srcs": [
            {"sid": "s1", "skind": "ShadowItem"}, {"sid": "v1", "skind": "Video"}]},
    ]
    out = asyncio.run(actors.actor_clusters(_FakeDriver(rows), min_uses=2))
    assert len(out) == 1
    assert out[0]["cross_product"] is True
    assert out[0]["sources"] == 2


def test_actor_clusters_none_driver():
    assert asyncio.run(actors.actor_clusters(None)) == []
