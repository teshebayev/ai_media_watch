# core — общий движок FinGuard

Фасад над уже существующим кодом (`backend/`, `src/`). Не перемещает модули — даёт
единую точку импорта общего движка для обоих продуктов.

```python
from core import (
    AnalysisRecord, Entities, FraudType, RiskLevel,   # формат §5 + словари
    extract_regex_entities, extract_signals,           # сущности + сигналы
    evaluate, signal_weight,                           # risk engine §11
    graph_service, similarity_service, osint_service,  # Neo4j / Qdrant / OSINT
)
```

## Что входит в общий слой
| Группа | Источник | Назначение |
|---|---|---|
| Схемы/словари | `backend/app/schemas/` | единый JSONL-формат §5, `FraudType`/`Label`/`RiskLevel`/`RISK_SIGNALS` |
| Risk Engine | `src/risk/risk_engine.py` | детерминированный скоринг (§11), `SIGNAL_WEIGHTS` |
| Извлечение | `src/extraction/`, `services/entities.py` | regex-сущности + риск-сигналы |
| Shadow Graph | `services/graph.py` → Neo4j | узлы/связи, повторяемость, кросс-продуктовый граф |
| Similarity | `services/similarity.py` → Qdrant | похожие известные кейсы |
| OSINT | `services/osint.py` | репутация доменов |

## Кто использует
- `apps/media_watch/` — контентный продукт (видео/аудио/url → ASR/OCR/deepfake → scenario).
- `apps/digital_shadow/` — OSINT/даркнет продукт (коллекторы → контрабанда/дропы/крипто/утечки).

Оба пишут сущности в **один** Neo4j → кошелёк/домен из TikTok-скама и из даркнет-листинга
сходятся в один узел. Это и есть «дополнение» двух продуктов друг другом.

> Перенос модулей физически внутрь `core/` — отдельный рефакторинг; сейчас фасад тянет их по месту,
> чтобы не трогать рабочий стек.
