"""Тесты дедупликации/инкрементального сбора (SeenStore) — на временном файле, без сети."""

from __future__ import annotations

from apps.digital_shadow.seen_store import SeenStore, content_key


def test_content_key_normalizes_whitespace_and_case():
    assert content_key("Продам  БАЗУ\nРК") == content_key("продам базу рк")
    assert content_key("a") != content_key("b")


def test_new_then_seen(tmp_path):
    store = SeenStore(str(tmp_path / "seen.txt"))
    kw = {"source_type": "darknet", "item_id": "x1", "text": "вейпы оптом без акциз"}
    assert store.is_new(**kw) is True
    store.mark(**kw)
    assert store.is_new(**kw) is False


def test_same_content_new_id_is_dedup(tmp_path):
    """Тот же текст под новым id — дубль (контентный хэш)."""
    store = SeenStore(str(tmp_path / "seen.txt"))
    store.mark(source_type="darknet", item_id="x1", text="одинаковый текст листинга")
    assert store.is_new(
        source_type="darknet", item_id="x2", text="одинаковый текст листинга") is False


def test_persistence_across_instances(tmp_path):
    path = str(tmp_path / "seen.txt")
    s1 = SeenStore(path)
    s1.mark(source_type="paste", item_id="p1", text="дамп базы рк")
    assert s1.flush() >= 1
    # новый инстанс читает файл → помнит
    s2 = SeenStore(path)
    assert s2.is_new(source_type="paste", item_id="p1", text="дамп базы рк") is False


def test_flush_returns_zero_when_nothing_new(tmp_path):
    store = SeenStore(str(tmp_path / "seen.txt"))
    assert store.flush() == 0
