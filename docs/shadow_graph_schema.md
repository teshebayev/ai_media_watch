# Общая схема графа (контракт для двух команд)

Оба продукта пишут в **один Neo4j** через `core.graph_service.upsert_entities(...)`. Граф —
точка, где находки AI Media Watch и Digital Shadow связываются. Чтобы связка работала, обе
команды соблюдают единые правила ниже.

## Узлы

**Источники (различаются по продукту → разный label):**
| Label | Кто создаёт | Ключ |
|---|---|---|
| `:Video` `:Post` `:Call` | AI Media Watch | `id` |
| `:ShadowItem` | Digital Shadow | `id` |

`source_label` передаётся в `upsert_entities(..., source_label=...)` и берётся только из
allowlist `_SOURCE_LABELS` (`Video/Post/Call/ShadowItem/Source`).

**Сущности (ОБЩИЕ для обоих продуктов — это и есть мост):**
| Label | Ключ (уникален) | Из чего |
|---|---|---|
| `:Domain` | `name` | домены из текста/URL |
| `:TelegramUsername` | `name` | `@ник` |
| `:PromoCode` | `code` | промокоды |
| `:Wallet` | `address` | крипто-кошельки |

Констрейнты уникальности — `src/graph/graph_schema.cypher` (применяются `ensure_constraints`).

## Рёбра
```
(:Video|:Post|:Call|:ShadowItem)-[:MENTIONS]->(:Domain|:TelegramUsername|:Wallet)
(:Video|:Post|:Call|:ShadowItem)-[:HAS_PROMO]->(:PromoCode)
```

## Правила контракта (не нарушать — иначе связка ломается)
1. **Сущности — общие узлы, не дублировать по продукту.** Один и тот же домен/кошелёк/`@ник`
   из TikTok-скама (Media) и из даркнет-листинга (Shadow) обязан быть ОДНИМ узлом. Поэтому
   ключи канонические (`name`/`code`/`address`), а различается только label ИСТОЧНИКА.
2. **Кошельки и telegram пишем всегда** — это самые ценные кросс-продуктовые связки.
3. **Реквизиты-ПДн — только маска/хэш** (телефоны/карты), §0. Кошельки — публичные адреса.
4. Менять схему/ключи узлов — через core-команду + обновить этот файл и `test_core_contract`.

## Кросс-продуктовый запрос (главная ценность)
«Сущности, которые всплывают и в контенте, и в теневых источниках» — мост между продуктами:
```cypher
MATCH (e)<-[:MENTIONS]-(s)
WITH e, collect(DISTINCT labels(s)[0]) AS kinds, count(DISTINCT s) AS uses
WHERE ('ShadowItem' IN kinds) AND
      (('Video' IN kinds) OR ('Post' IN kinds) OR ('Call' IN kinds))
RETURN coalesce(e.name, e.code, e.address) AS entity, kinds, uses
ORDER BY uses DESC;
```
Повторяемость одной сущности среди источников любого типа считает
`core.graph_service.entity_reuse(value)` (по `name|code|address`) → сигнал `graph_entity_reuse`.

## Где в коде
- запись: `core.graph_service.upsert_entities(driver, id, entities, source_label=...)`
- повторяемость: `entity_reuse(driver, value)` · подграф: `neighborhood` / `overview`
- контракт зафиксирован тестом `tests/test_core_contract.py::test_graph_supports_wallet_reuse`.
