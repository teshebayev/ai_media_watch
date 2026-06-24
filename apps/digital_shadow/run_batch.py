"""Batch-прогон + честная оценка датасета Digital Shadow через пайплайн.

Сверяет предсказанную категорию/сигналы с эталоном и печатает метрики:
precision/recall/F1 по категориям, macro-F1, и — главное для OSINT — FPR на
legit-контрпримерах (доля законных объявлений, поднявших high-priority): это про
шум/alert fatigue. Режим --holdout честно помечает прогон как «реальный hold-out»
против синтетики (gen_llm самопроверки).

Запуск:
    python -m apps.digital_shadow.run_batch [path.jsonl]            # синтетика (seed)
    python -m apps.digital_shadow.run_batch --holdout data/shadow/holdout_real.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict

from apps.digital_shadow.pipeline import analyze_item
from apps.digital_shadow.schemas import ShadowItem

DEFAULT = "data/shadow/seed.jsonl"
_HIGH_PRIORITY = {"high", "urgent"}
_HIGH_RISK = {"high", "critical"}


def _load(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1


async def evaluate(rows: list[dict]) -> dict:
    """Прогнать строки через пайплайн, вернуть метрики (чистая детекция, без графа)."""
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    recall_sum = 0.0
    cat_ok = 0
    legit_total = 0
    legit_fp = 0          # legit, поднявший high-priority/high-risk → ложная тревога
    legit_fp_ids: list[str] = []
    misses: list[tuple] = []

    for r in rows:
        item = ShadowItem(
            id=r["id"], source_type=r.get("source_type", "clearweb"),
            platform=r.get("platform"), language=r.get("language", "ru"), text=r["text"])
        f = await analyze_item(item, driver=None)   # без графа — чистая оценка детекции
        gold_cat = r.get("gold_category", "unknown")
        gold_sig = set(r.get("gold_signals", []))

        if f.category == gold_cat:
            cat_ok += 1
            tp[gold_cat] += 1
        else:
            fp[f.category] += 1
            fn[gold_cat] += 1
            misses.append((r["id"], f"кат: {gold_cat}→{f.category}"))
        recall = 1.0 if not gold_sig else len(gold_sig & set(f.signals)) / len(gold_sig)
        recall_sum += recall

        if r.get("legit"):
            legit_total += 1
            if f.priority in _HIGH_PRIORITY or f.risk_level in _HIGH_RISK:
                legit_fp += 1
                legit_fp_ids.append(r["id"])

    cats = sorted(set(tp) | set(fp) | set(fn))
    per_cat = {c: _prf(tp[c], fp[c], fn[c]) for c in cats}

    def _macro(keys: list[str]) -> float:
        return sum(per_cat[c][2] for c in keys) / len(keys) if keys else 0.0

    # 'unknown' — негативный/legit-класс: включён в общий macro-F1, но даём и срез
    # только по реальным категориям (честнее отражает детекцию угроз).
    real_cats = [c for c in cats if c != "unknown"]
    return {
        "n": len(rows), "cat_ok": cat_ok, "recall": recall_sum / max(1, len(rows)),
        "per_cat": per_cat, "macro_f1": _macro(cats), "macro_f1_no_unknown": _macro(real_cats),
        "legit_total": legit_total, "legit_fp": legit_fp, "legit_fp_ids": legit_fp_ids,
        "misses": misses,
    }


def _print(path: str, m: dict, *, real: bool) -> None:
    kind = "РЕАЛЬНЫЙ hold-out (ручная разметка)" if real else "СИНТЕТИКА (seed/gen_llm)"
    n = m["n"] or 1
    print(f"\n=== {kind} ===")
    print(f"Датасет: {m['n']} строк  ({path})")
    print(f"Точность категории : {m['cat_ok']}/{m['n']} = {m['cat_ok'] / n:.0%}")
    print(f"Покрытие сигналов  : {m['recall']:.0%}")
    print(f"macro-F1 (вкл. класс 'unknown'/legit): {m['macro_f1']:.3f}")
    print(f"macro-F1 (только реальные категории) : {m['macro_f1_no_unknown']:.3f}\n")
    print(f"{'категория':22}{'P':>8}{'R':>8}{'F1':>8}")
    for c, (p, r, f1) in m["per_cat"].items():
        print(f"{c:22}{p:>8.2f}{r:>8.2f}{f1:>8.2f}")

    if m["legit_total"]:
        fpr = m["legit_fp"] / m["legit_total"]
        print(f"\nFPR на legit-контрпримерах: {m['legit_fp']}/{m['legit_total']} = {fpr:.0%} "
              "(доля законных, поднявших high-priority/high-risk — шум для аналитика)")
        if m["legit_fp_ids"]:
            print(f"  ложные тревоги: {', '.join(m['legit_fp_ids'])}")
    else:
        print("\nFPR: legit-контрпримеров в датасете нет (добавьте \"legit\": true) — "
              "без них метрика шума не считается.")

    if m["misses"]:
        print(f"\nРасхождения категорий ({len(m['misses'])}):")
        for mid, note in m["misses"][:25]:
            print(f"  {mid:16} {note}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=DEFAULT)
    ap.add_argument("--holdout", help="путь к реальному hold-out (честно метит прогон)")
    args = ap.parse_args()
    path = args.holdout or args.path
    _print(path, await evaluate(_load(path)), real=bool(args.holdout))


if __name__ == "__main__":
    asyncio.run(main())
