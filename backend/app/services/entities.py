"""Entity Service: regex (детерминированный проход) + опциональный LLM-добор.

Первый проход — src/extraction/regex_extractors (формальные сущности из ТЗ §10).
Второй проход (LLM) добирает названия проектов, организации, pressure-фразы.
"""

from __future__ import annotations

import json

from openai import AsyncOpenAI

from backend.app.config import get_settings
from backend.app.schemas.models import Entities
from src.extraction.regex_extractors import extract_entities

ENRICH_PROMPT = (
    "Извлеки из текста сущности, которые сложно поймать регулярками. Верни СТРОГО JSON: "
    '{"organizations": ["..."], "project_names": ["..."], "pressure_phrases": ["..."]}. '
    "organizations — упомянутые организации/госорганы/банки (eGov, КНБ, Нацбанк, казино-бренды). "
    "project_names — названия инвест-проектов/платформ/каналов. "
    "pressure_phrases — фразы психологического давления (срочность, угроза, секретность). "
    "Если чего-то нет — пустой список. Только JSON, без пояснений."
)


def extract_regex_entities(combined_text: str) -> Entities:
    return Entities(**extract_entities(combined_text))


async def enrich_with_llm(text: str, entities: Entities) -> Entities:
    """Добрать organizations через LLM (vLLM). project_names/pressure_phrases
    возвращаются в отчёт как evidence, организации — в entities.organizations.

    При выключенном ENABLE_LLM или ошибке — возвращаем entities без изменений.
    """
    s = get_settings()
    if not s.enable_llm:
        return entities
    try:
        llm = AsyncOpenAI(base_url=s.llm_base_url, api_key=s.llm_api_key)
        resp = await llm.chat.completions.create(
            model=s.llm_model,
            messages=[
                {"role": "system", "content": ENRICH_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception:  # noqa: BLE001
        return entities

    orgs = data.get("organizations", [])
    if isinstance(orgs, list):
        merged = list(dict.fromkeys([*entities.organizations, *map(str, orgs)]))
        entities = entities.model_copy(update={"organizations": merged})
    return entities


def enrich_with_ner(text: str, entities: Entities) -> Entities:
    """Этап 8.4: казахский NER (KazNERD) вторым проходом — добор организаций.

    Best-effort: если transformers/модель не установлены, возвращаем entities как есть.
    """
    from src.extraction.kaznerd_ner import extract_kk_entities

    found = extract_kk_entities(text)
    orgs = found.get("organizations", [])
    if orgs:
        merged = list(dict.fromkeys([*entities.organizations, *orgs]))
        entities = entities.model_copy(update={"organizations": merged})
    return entities
