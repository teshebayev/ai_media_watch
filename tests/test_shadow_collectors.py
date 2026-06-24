"""Тесты коллекторов и ML-классификатора Digital Shadow (без сети)."""

from __future__ import annotations

import asyncio
import json

import pytest

from apps.digital_shadow import classifier
from apps.digital_shadow.collectors import FileCollector
from apps.digital_shadow.collectors.http_page import strip_html
from apps.digital_shadow.collectors.rss import parse_feed


def test_file_collector(tmp_path):
    p = tmp_path / "items.jsonl"
    p.write_text(
        json.dumps({"id": "a1", "source_type": "clearweb", "text": "Ищем дропов, карта в аренду"},
                   ensure_ascii=False) + "\n"
        + json.dumps({"id": "a2", "text": "Продам базу РК, дамп"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    async def run():
        return [it async for it in FileCollector(str(p)).collect()]

    items = asyncio.run(run())
    assert len(items) == 2
    assert items[0].id == "a1" and "дропов" in items[0].text
    assert items[1].source_type == "clearweb"  # дефолт, если не указан


def test_strip_html():
    html = "<html><head><style>x{}</style></head><body><p>Привет <b>мир</b></p>" \
           "<script>bad()</script></body></html>"
    out = strip_html(html)
    assert "Привет" in out and "мир" in out
    assert "bad()" not in out and "<" not in out


def test_parse_rss():
    feed = """<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>Продажа базы</title><description>дамп РК</description>
        <link>http://x/1</link></item>
      <item><title>Вторая</title><description>текст</description><link>http://x/2</link></item>
    </channel></rss>"""
    items = parse_feed(feed)
    assert len(items) == 2
    assert items[0]["title"] == "Продажа базы"
    assert items[0]["link"] == "http://x/1"


@pytest.mark.skipif(not classifier.has_model(), reason="модель не обучена")
def test_classifier_predict():
    res = classifier.predict("Ищем дропов: карта в аренду за процент, приём переводов, оплата USDT")
    assert res is not None
    category, proba = res
    assert category == "drop_recruitment"
    assert 0.0 <= proba <= 1.0
