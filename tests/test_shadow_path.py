"""Тесты объяснимости пути в графе (graph_service.explain_link) — чистые помощники
на фейковых neo4j-подобных узлах/путях, без сети."""

from __future__ import annotations

from backend.app.services import graph as g


class _FakeNode:
    """Минимальный neo4j-подобный узел: dict(node) + .labels + .element_id."""

    def __init__(self, labels, props, eid="x"):
        self.labels = labels
        self._props = props
        self.element_id = eid

    def keys(self):
        return self._props.keys()

    def __getitem__(self, k):
        return self._props[k]


class _FakeRel:
    def __init__(self, rtype, start, end):
        self.type = rtype
        self.start_node = start
        self.end_node = end


class _FakePath:
    def __init__(self, nodes, rels):
        self.nodes = nodes
        self.relationships = rels


def test_node_caption_includes_category():
    n = _FakeNode(["ShadowItem"], {"id": "dn_drug_001", "category": "drug_trafficking"})
    assert g._node_caption(n) == "ShadowItem dn_drug_001 [drug_trafficking]"


def test_node_caption_skips_unknown_category():
    n = _FakeNode(["Wallet"], {"address": "bc1qxy", "category": "unknown"})
    assert g._node_caption(n) == "Wallet bc1qxy"


def test_explain_shared_source_is_human_readable():
    """A ← источник → B: объяснение = «обе упомянуты в одном источнике»."""
    wallet = _FakeNode(["Wallet"], {"address": "bc1qxy"}, "w")
    src = _FakeNode(["ShadowItem"], {"id": "dn1", "category": "drug_trafficking"}, "s")
    tg = _FakeNode(["TelegramUsername"], {"name": "@drop_kz"}, "t")
    path = _FakePath(
        [wallet, src, tg],
        [_FakeRel("MENTIONS", src, wallet), _FakeRel("MENTIONS", src, tg)])
    expl = g._explain_path(path)
    assert len(expl) == 1
    assert "одном источнике" in expl[0]
    assert "dn1" in expl[0] and "drug_trafficking" in expl[0]


def test_explain_multihop_chain():
    """Длинная цепочка → пошаговое объяснение каждого ребра."""
    w = _FakeNode(["Wallet"], {"address": "w1"}, "w")
    s1 = _FakeNode(["ShadowItem"], {"id": "s1"}, "s1")
    d = _FakeNode(["Domain"], {"name": "x.com"}, "d")
    s2 = _FakeNode(["ShadowItem"], {"id": "s2"}, "s2")
    tg = _FakeNode(["TelegramUsername"], {"name": "@t"}, "t")
    path = _FakePath(
        [w, s1, d, s2, tg],
        [_FakeRel("MENTIONS", s1, w), _FakeRel("MENTIONS", s1, d),
         _FakeRel("MENTIONS", s2, d), _FakeRel("MENTIONS", s2, tg)])
    expl = g._explain_path(path)
    assert len(expl) == 4
    assert all("→" in step for step in expl)
