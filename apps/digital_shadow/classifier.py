"""ML-классификатор категорий (инференс). Опциональный запасной слой к правилам taxonomy.

Модель обучается `train_classifier.py` и лежит в data/shadow/category_model.joblib. Если файла
нет или sklearn недоступен — `predict` возвращает None (пайплайн тихо остаётся на правилах).
"""

from __future__ import annotations

import os
from functools import lru_cache

MODEL_PATH = os.environ.get("SHADOW_MODEL_PATH", "data/shadow/category_model.joblib")


@lru_cache(maxsize=1)
def _load():
    try:
        import joblib
        return joblib.load(MODEL_PATH)
    except Exception:  # noqa: BLE001 — модели нет / sklearn недоступен
        return None


def has_model() -> bool:
    return _load() is not None


def predict(text: str) -> tuple[str, float] | None:
    """Вернуть (category, proba) или None, если модель недоступна."""
    model = _load()
    if model is None or not text.strip():
        return None
    proba = model.predict_proba([text])[0]
    classes = model.classes_
    i = int(proba.argmax())
    return str(classes[i]), float(proba[i])
