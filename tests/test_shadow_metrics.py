"""Тесты Фазы 4: честные метрики run_batch (P/R/F1 + FPR на legit) и наличие hold-out."""

from __future__ import annotations

import asyncio
import json
import pathlib

from apps.digital_shadow.run_batch import _prf, evaluate

HOLDOUT = pathlib.Path("data/shadow/holdout_real.jsonl")


def test_prf_math():
    p, r, f1 = _prf(tp=8, fp=2, fn=2)
    assert round(p, 2) == 0.80 and round(r, 2) == 0.80 and round(f1, 2) == 0.80
    assert _prf(0, 0, 0) == (0.0, 0.0, 0.0)   # без деления на ноль


def test_holdout_file_present_and_has_legit():
    """Hold-out существует, размечен вручную и содержит legit-контрпримеры (для FPR)."""
    assert HOLDOUT.exists(), "нет ручного hold-out data/shadow/holdout_real.jsonl"
    rows = [json.loads(line) for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line]
    assert len(rows) >= 20
    assert sum(r.get("legit") is True for r in rows) >= 5     # есть контрпримеры


def test_evaluate_computes_fpr_and_f1():
    rows = [
        {"id": "a", "source_type": "darknet",
         "text": "Клад по городу, оплата криптой, session", "gold_category": "drug_trafficking"},
        {"id": "b", "source_type": "clearweb",
         "text": "Вакансия менеджер, оклад 250000, офис", "gold_category": "unknown",
         "legit": True},
    ]
    m = asyncio.run(evaluate(rows))
    assert m["n"] == 2
    assert m["legit_total"] == 1
    assert "macro_f1" in m and 0.0 <= m["macro_f1"] <= 1.0
    # legit-вакансия не должна давать high-priority (FPR=0 на этом примере)
    assert m["legit_fp"] == 0
