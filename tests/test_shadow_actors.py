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


# ── Hub + риск кластера ───────────────────────────────────────────────────────
def test_cluster_hub_is_most_connected_entity():
    """Вожак сети = сущность с наибольшим числом источников (степень)."""
    edges = [
        # кошелёк делит 3 источника → центральный узел
        {"entity": "w_hub", "etype": "Wallet", "sid": "s1", "skind": "ShadowItem"},
        {"entity": "w_hub", "etype": "Wallet", "sid": "s2", "skind": "ShadowItem"},
        {"entity": "w_hub", "etype": "Wallet", "sid": "s3", "skind": "ShadowItem"},
        # домен — только в одном
        {"entity": "d_leaf.com", "etype": "Domain", "sid": "s1", "skind": "ShadowItem"},
    ]
    c = actors._build_clusters(edges)[0]
    assert c["hub"]["value"] == "w_hub"
    assert c["hub"]["sources"] == 3


def test_cluster_risk_rises_with_reach_and_cross_product():
    """Кросс-продуктовая сеть из многих источников рискованнее одиночного листинга."""
    big = [
        {"entity": "w1", "etype": "Wallet", "sid": "v1", "skind": "Video"},
        {"entity": "w1", "etype": "Wallet", "sid": "s1", "skind": "ShadowItem"},
        {"entity": "dom1", "etype": "Domain", "sid": "s1", "skind": "ShadowItem"},
        {"entity": "@drop1", "etype": "TelegramUsername", "sid": "s2", "skind": "ShadowItem"},
        {"entity": "w1", "etype": "Wallet", "sid": "s2", "skind": "ShadowItem"},
    ]
    small = [
        {"entity": "solo", "etype": "Domain", "sid": "x1", "skind": "ShadowItem"},
        {"entity": "solo2", "etype": "Domain", "sid": "x1", "skind": "ShadowItem"},
    ]
    risk_big = actors._build_clusters(big)[0]["risk"]
    risk_small = actors._build_clusters(small)[0]["risk"]
    assert risk_big > risk_small
    assert 0 < risk_big <= 100


# ── Скоринг акторов ───────────────────────────────────────────────────────────
def test_score_actors_ranks_central_node_first():
    """Кошелёк, делящий источники с многими сущностями и мостящий Media↔Shadow,
    получает максимальный actor_risk и идёт первым."""
    edges = [
        {"entity": "w_central", "etype": "Wallet", "sid": "v1", "skind": "Video"},
        {"entity": "w_central", "etype": "Wallet", "sid": "s1", "skind": "ShadowItem"},
        {"entity": "w_central", "etype": "Wallet", "sid": "s2", "skind": "ShadowItem"},
        {"entity": "dom_a.com", "etype": "Domain", "sid": "s1", "skind": "ShadowItem"},
        {"entity": "@drop_b", "etype": "TelegramUsername", "sid": "s2", "skind": "ShadowItem"},
        # одиночка в своём источнике
        {"entity": "lonely.com", "etype": "Domain", "sid": "z9", "skind": "ShadowItem"},
    ]
    scored = actors._score_actors(edges)
    top = scored[0]
    assert top["entity"] == "w_central"
    assert top["cross_product"] is True
    assert top["co_actors"] == 2          # делит источники с dom_a.com и @drop_b
    assert top["uses"] == 3
    lonely = next(a for a in scored if a["entity"] == "lonely.com")
    assert top["actor_risk"] > lonely["actor_risk"]


def test_score_actors_limit_and_self_excluded():
    edges = [
        {"entity": "solo", "etype": "Domain", "sid": "s1", "skind": "ShadowItem"},
    ]
    scored = actors._score_actors(edges, limit=5)
    assert len(scored) == 1
    assert scored[0]["co_actors"] == 0    # сам себе не co_actor


def test_actor_scores_async_with_fake_driver():
    rows = [
        {"entity": "w_central", "etype": "Wallet", "srcs": [
            {"sid": "v1", "skind": "Video"}, {"sid": "s1", "skind": "ShadowItem"}]},
        {"entity": "dom_a.com", "etype": "Domain", "srcs": [
            {"sid": "s1", "skind": "ShadowItem"}]},
    ]
    out = asyncio.run(actors.actor_scores(_FakeDriver(rows), min_uses=1))
    assert out[0]["entity"] == "w_central"
    assert out[0]["cross_product"] is True


def test_actor_scores_none_driver():
    assert asyncio.run(actors.actor_scores(None)) == []


# ── Кросс-категорийные связи (наркотики↔дропы↔утечки через общий индикатор) ────
def test_cluster_cross_category_via_shared_wallet():
    """Один кошелёк в листинге наркотиков и в листинге дропов → кросс-категорийный кластер."""
    edges = [
        {"entity": "w", "etype": "Wallet", "sid": "d1", "skind": "ShadowItem",
         "scat": "drug_trafficking"},
        {"entity": "w", "etype": "Wallet", "sid": "d2", "skind": "ShadowItem",
         "scat": "drop_recruitment"},
    ]
    c = actors._build_clusters(edges)[0]
    assert c["cross_category"] is True
    assert c["categories"] == ["drop_recruitment", "drug_trafficking"]


def test_cluster_single_category_not_cross():
    edges = [
        {"entity": "w", "etype": "Wallet", "sid": "d1", "skind": "ShadowItem",
         "scat": "drug_trafficking"},
        {"entity": "dom.com", "etype": "Domain", "sid": "d1", "skind": "ShadowItem",
         "scat": "drug_trafficking"},
    ]
    c = actors._build_clusters(edges)[0]
    assert c["cross_category"] is False
    assert c["categories"] == ["drug_trafficking"]


def test_unknown_category_ignored_for_cross():
    """'unknown'/пустая категория не создаёт ложную кросс-категорийность."""
    edges = [
        {"entity": "w", "etype": "Wallet", "sid": "d1", "skind": "ShadowItem",
         "scat": "drug_trafficking"},
        {"entity": "w", "etype": "Wallet", "sid": "d2", "skind": "ShadowItem",
         "scat": "unknown"},
        {"entity": "w", "etype": "Wallet", "sid": "d3", "skind": "ShadowItem", "scat": None},
    ]
    c = actors._build_clusters(edges)[0]
    assert c["categories"] == ["drug_trafficking"]
    assert c["cross_category"] is False


def test_cross_category_cluster_sorted_first():
    """Кросс-категорийный кластер приоритетнее одиночного, даже если меньше по размеру."""
    edges = [
        # большой одно-категорийный
        {"entity": "a", "etype": "Domain", "sid": "s1", "skind": "ShadowItem",
         "scat": "contraband_vape"},
        {"entity": "b", "etype": "Domain", "sid": "s1", "skind": "ShadowItem",
         "scat": "contraband_vape"},
        {"entity": "c", "etype": "Domain", "sid": "s1", "skind": "ShadowItem",
         "scat": "contraband_vape"},
        # маленький кросс-категорийный
        {"entity": "x", "etype": "Wallet", "sid": "s2", "skind": "ShadowItem",
         "scat": "drug_trafficking"},
        {"entity": "x", "etype": "Wallet", "sid": "s3", "skind": "ShadowItem",
         "scat": "kz_data_leak"},
    ]
    clusters = actors._build_clusters(edges)
    assert clusters[0]["cross_category"] is True
    assert "x" in {e["value"] for e in clusters[0]["entities"]}


def test_score_actors_cross_category_raises_risk():
    base = [
        {"entity": "w", "etype": "Wallet", "sid": "d1", "skind": "ShadowItem",
         "scat": "drug_trafficking"},
        {"entity": "w", "etype": "Wallet", "sid": "d2", "skind": "ShadowItem",
         "scat": "drug_trafficking"},
    ]
    cross = [
        {"entity": "w", "etype": "Wallet", "sid": "d1", "skind": "ShadowItem",
         "scat": "drug_trafficking"},
        {"entity": "w", "etype": "Wallet", "sid": "d2", "skind": "ShadowItem",
         "scat": "drop_recruitment"},
    ]
    r_base = actors._score_actors(base)[0]["actor_risk"]
    r_cross = actors._score_actors(cross)[0]["actor_risk"]
    assert r_cross > r_base
