# Killer-сценарий: синергия Media Watch ↔ Digital Shadow

Главная ценность монорепо — **общий Neo4j**: один и тот же кошелёк/домен/`@ник` из
соцвидео (AI Media Watch) и из даркнет-листинга (Digital Shadow) сходится в ОДИН узел
(ключи канонизируются, см. [shadow_graph_schema.md](shadow_graph_schema.md)). Так
вскрывается связь, невидимая каждому продукту по отдельности.

## Сценарий
1. **Media Watch** ловит TikTok-инвестскам блогера: в кадре/описании — крипто-кошелёк
   `0xcafe…babe` и домен `promo-invest.kz` → узлы `:Video → :Wallet/:Domain`.
2. **Digital Shadow** ловит даркнет-листинг вербовки дропов: тот же кошелёк `0xcafe…babe`
   в тексте → узел `:ShadowItem → :Wallet` (тот же узел Wallet).
3. Кошелёк теперь упомянут источниками **двух типов** → `/shadow/cross` и `/shadow/clusters`
   показывают его как **мост Media↔Shadow**: «промо-блогер ↔ даркнет-дроп ↔ кошелёк».

## Запуск
```bash
ENABLE_GRAPH=true NEO4J_URI=bolt://localhost:7687 NEO4J_PASSWORD=finguard_pass \
PYTHONPATH=. python scripts/demo_cross_product.py     # или: make shadow-demo
```

## Результат (на демо-данных)
```
/shadow/cross — кросс-продуктовые сущности: 3
  0xcafe…babe          Wallet            kinds=['Video', 'ShadowItem']
  @drop_team_kz        TelegramUsername  kinds=['Video', 'ShadowItem']
  @vape_opt_kz         TelegramUsername  kinds=['Video', 'ShadowItem']
Метрика синергии: 3/9 = 33% теневых сущностей встречаются и в медиа-контенте.
```
Цифра «**33% теневых сущностей всплывают и в медиа-контенте**» считается запросом
`BRIDGE_PCT_QUERY` (в скрипте) — это и есть аргумент за единый граф, а не два изолированных репозитория.

## Честные метрики (см. также run_batch --holdout)
На **ручном hold-out** реалистичных кейсов (`data/shadow/holdout_real.jsonl`, НЕ из
gen_llm-самопроверки): **FPR = 0%** на legit-контрпримерах (нет ложных тревог — главная
OSINT-метрика, борьба с alert fatigue), при macro-F1 категорий ≈ 0.49 (против 0.98 на
синтетике — разрыв честно показывает, что классификация категорий лексиконом-вперёд
ещё сыровата: crypto/alcohol/counterfeit путаются — точка роста). Разделение
«синтетика vs real» — в выводе `run_batch`.
