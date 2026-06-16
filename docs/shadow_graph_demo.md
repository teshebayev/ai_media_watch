# Shadow Graph — демо

Схема — `src/graph/graph_schema.cypher` (ТЗ §12). Что должен показать граф (ТЗ §12.3):

1. Один и тот же домен в разных видео.
2. Один Telegram-ник в разных постах.
3. Один промокод у разных блогеров.
4. Один кошелёк в разных источниках.
5. Кластер `блогер → видео → сайт → Telegram → risk_signal`.

## Повторяемость → сигнал
Если сущность встречается в ≥2 источниках → сигнал `graph_entity_reuse` (+25, ТЗ §11).

```cypher
MATCH (d:Domain)<-[:MENTIONS]-(v:Video)
WITH d, count(v) AS uses WHERE uses > 1
RETURN d.name, uses ORDER BY uses DESC;
```

API: `GET /graph/entity/{value}` → `{value, uses, graph_entity_reuse}`.
Запасной вариант без Neo4j (план «Риски»): рисовать граф из CSV в Streamlit (networkx/pyvis).
