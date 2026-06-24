"""Обучение ML-классификатора категорий Digital Shadow (поверх правил).

Правила (taxonomy) точны, но не обобщают на новые формулировки. ML-классификатор учится на
размеченном датасете (`data/shadow/all.jsonl` = seed + llm_gen) и служит запасным определением
категории, когда правила вернули `unknown`.

TF-IDF (слова 1–2 + символьные n-граммы для устойчивости к опечаткам/смешению ru/kk) →
LogisticRegression. Метрика — macro-F1 (классы несбалансированы).

Запуск:
    python -m apps.digital_shadow.train_classifier --data data/shadow/all.jsonl
    make shadow-train
"""

from __future__ import annotations

import argparse
import json
import os

import joblib

DEFAULT_DATA = "data/shadow/all.jsonl"
DEFAULT_MODEL = "data/shadow/category_model.joblib"


def load(path: str) -> tuple[list[str], list[str]]:
    texts, labels = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            t = d.get("text") or d.get("combined_text")
            y = d.get("gold_category")
            if t and y:
                texts.append(t)
                labels.append(y)
    return texts, labels


def reviews_to_examples(rows: list[dict]) -> tuple[list[str], list[str]]:
    """Active learning: размеченные ревью → (тексты, метки). confirmed → метка = категория
    находки (позитив); dismissed → 'unknown' (hard-negative: «это НЕ та категория»);
    in_review/без текста — пропуск. Чистая функция (для теста на пустом входе)."""
    texts, labels = [], []
    for r in rows:
        text, cat, decision = r.get("text"), r.get("category"), r.get("decision")
        if not text:
            continue
        if decision == "confirm" and cat:
            texts.append(text)
            labels.append(cat)
        elif decision == "dismiss":
            texts.append(text)
            labels.append("unknown")
    return texts, labels


def load_review_examples() -> tuple[list[str], list[str]]:
    """Подтянуть размеченные ревью из shadow_reviews (async) → примеры. Best-effort."""
    import asyncio

    from apps.digital_shadow import persistence

    try:
        rows = asyncio.run(persistence.fetch_review_rows())
    except Exception as e:  # noqa: BLE001 — БД недоступна → без ревью
        print(f"ревью недоступны ({e}); обучаюсь без них")
        return [], []
    return reviews_to_examples(rows)


def build_pipeline():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, Pipeline

    word = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, sublinear_tf=True)
    return Pipeline([
        ("feats", FeatureUnion([("word", word), ("char", char)])),
        ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
    ])


def main() -> None:
    from sklearn.metrics import classification_report, f1_score
    from sklearn.model_selection import train_test_split

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--test-size", type=float, default=0.25)
    ap.add_argument("--with-reviews", action="store_true",
                    help="подмешать размеченные ревью аналитика (active learning)")
    args = ap.parse_args()

    X, y = load(args.data)
    print(f"Загружено из датасета: {len(X)} примеров, классов: {len(set(y))}")

    if args.with_reviews:
        rx, ry = load_review_examples()
        X += rx
        y += ry
        print(f"Добавлено из ревью: {len(rx)} (confirmed→категория, dismissed→unknown)")

    # stratify по возможности (нужно ≥2 на класс)
    from collections import Counter
    strat = y if min(Counter(y).values()) >= 2 else None
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=args.test_size, random_state=42, stratify=strat)

    pipe = build_pipeline()
    pipe.fit(X_tr, y_tr)
    pred = pipe.predict(X_te)
    macro = f1_score(y_te, pred, average="macro")
    print(f"\nmacro-F1 (hold-out): {macro:.3f}\n")
    print(classification_report(y_te, pred, zero_division=0))

    # финальная модель — на всех данных
    pipe.fit(X, y)
    os.makedirs(os.path.dirname(args.model), exist_ok=True)
    joblib.dump(pipe, args.model)
    print(f"Модель сохранена → {args.model}")


if __name__ == "__main__":
    main()
