"""Batch-прогон + оценка датасета Digital Shadow через пайплайн.

Студенты дополняют JSONL (формат ShadowItem + gold_category/gold_signals) и гоняют этот скрипт:
он прогоняет каждую строку через analyze_item, сверяет предсказанную категорию и сигналы с
эталоном и печатает метрики (точность категории, покрытие сигналов, разбивка по категориям).

Запуск:
    python -m apps.digital_shadow.run_batch [path.jsonl]   # по умолч. data/shadow/seed.jsonl
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import defaultdict

from apps.digital_shadow.pipeline import analyze_item
from apps.digital_shadow.schemas import ShadowItem

DEFAULT = "data/shadow/seed.jsonl"


def _load(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


async def main(path: str) -> None:
    rows = _load(path)
    cat_ok = 0
    recall_sum = 0.0
    per_cat = defaultdict(lambda: {"n": 0, "cat_ok": 0, "recall": 0.0})
    misses = []

    for r in rows:
        item = ShadowItem(
            id=r["id"], source_type=r.get("source_type", "clearweb"),
            platform=r.get("platform"), language=r.get("language", "ru"), text=r["text"],
        )
        f = await analyze_item(item, driver=None)  # без графа — чистая оценка детекции
        gold_cat = r.get("gold_category", "unknown")
        gold_sig = set(r.get("gold_signals", []))

        ok = f.category == gold_cat
        recall = 1.0 if not gold_sig else len(gold_sig & set(f.signals)) / len(gold_sig)
        cat_ok += ok
        recall_sum += recall
        pc = per_cat[gold_cat]
        pc["n"] += 1
        pc["cat_ok"] += ok
        pc["recall"] += recall
        if not ok or recall < 1.0:
            misses.append((r["id"], gold_cat, f.category, sorted(gold_sig - set(f.signals))))

    n = len(rows)
    print(f"\nДатасет: {n} строк  ({path})")
    print(f"Точность категории : {cat_ok}/{n} = {cat_ok / n:.0%}")
    print(f"Покрытие сигналов  : {recall_sum / n:.0%} (доля gold-сигналов, реально сработавших)\n")
    print(f"{'категория':22}{'n':>4}{'cat_acc':>9}{'sig_recall':>12}")
    for cat, d in sorted(per_cat.items()):
        print(f"{cat:22}{d['n']:>4}{d['cat_ok'] / d['n']:>8.0%}{d['recall'] / d['n']:>11.0%}")

    if misses:
        print(f"\nРасхождения ({len(misses)}):")
        for mid, g, p, missing in misses[:25]:
            note = f"кат: {g}→{p}" if g != p else f"нет сигналов: {missing}"
            print(f"  {mid:12} {note}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT))
