"""Этап 8.4 — казахский NER (KazNERD, ISSAI) как второй проход после regex.

Подключается в Entity Service для kk-текста: добирает организации, имена, локации,
которые regex (ТЗ §10) не ловит. Модель грузится лениво (transformers), при отсутствии
библиотеки/модели возвращается пустой результат — пайплайн не падает.

Установка (когда понадобится): `uv add transformers torch`, модель с HF (issai/kaznerd).
"""

from __future__ import annotations

from functools import lru_cache

# KazNERD: 25 классов (IOB2). Нас интересуют организации/проекты, персоны, локации.
ORG_LABELS = {"ORGANISATION", "ORG", "ORGANIZATION", "PROJECT"}
PERSON_LABELS = {"PERSON", "PER"}
LOCATION_LABELS = {"LOCATION", "LOC", "GPE"}

# Лучшая публичная модель по KazNERD (XLM-RoBERTa-large, F1 97.2% на тесте).
_MODEL_NAME = "yeshpanovrustem/xlm-roberta-large-ner-kazakh"


@lru_cache(maxsize=1)
def _get_pipeline():
    import torch
    from transformers import pipeline  # тяжёлый импорт — лениво

    device = 0 if torch.cuda.is_available() else -1
    return pipeline("token-classification", model=_MODEL_NAME,
                    aggregation_strategy="simple", device=device)


def extract_kk_entities(text: str) -> dict[str, list[str]]:
    """Вернуть {organizations, persons, locations}. Пустые списки, если NER недоступен."""
    empty = {"organizations": [], "persons": [], "locations": []}
    try:
        ner = _get_pipeline()
    except Exception:  # noqa: BLE001 — нет transformers/модели → graceful fallback
        return empty

    out = {"organizations": [], "persons": [], "locations": []}
    for ent in ner(text):
        group = str(ent.get("entity_group", "")).upper()
        word = ent.get("word", "").strip()
        if not word:
            continue
        if group in ORG_LABELS:
            out["organizations"].append(word)
        elif group in PERSON_LABELS:
            out["persons"].append(word)
        elif group in LOCATION_LABELS:
            out["locations"].append(word)
    return {k: list(dict.fromkeys(v)) for k, v in out.items()}
