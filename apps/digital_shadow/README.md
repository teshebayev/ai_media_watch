# app: Digital Shadow (OSINT / DarkNet мониторинг)

Мониторинг открытых интернет-ресурсов и сегментов DarkNet для выявления признаков незаконной
деятельности и оценки рисков: контрабанда (вейпы/алкоголь/наркотики), дропы, подозрительные
криптокошельки, утечки баз данных РК. Сбор и сопоставление данных, скрытые связи, риск-сигналы,
приоритизация угроз.

> Сервис **end-to-end**: поднимает общий Neo4j + Postgres в lifespan, пишет находки в ту же БД
> и тот же граф, что AI Media Watch. Реальные сетевые коллекторы (clearweb/Tor/paste) пока `TODO`;
> DarkNet для демо — **синтетический мок** (`collectors/darknet_mock.py`).

📖 **Архитектура (с mermaid-диаграммами):** [`docs/digital_shadow_architecture.md`](../../docs/digital_shadow_architecture.md)
· **Презентация модуля:** `presentation/digital_shadow.html` (открыть в браузере)
· **Схема графа:** [`docs/shadow_graph_schema.md`](../../docs/shadow_graph_schema.md)

## Структура
```
apps/digital_shadow/
├── pipeline.py        raw item → entities → signals → risk → priority → graph (общий Neo4j)
├── taxonomy.py        категории/лексикон контрабанды (ru+kk) + шадоу-сигналы и веса
├── schemas.py         ShadowItem (сырое) · ShadowFinding (проанализированное)
├── crypto_risk.py     оценка кошельков (формат, badlist, миксеры) → сигналы
├── leak_detector.py   детект утечек БД РК (.kz, маски ИИН, breach-лексика)
├── prioritization.py  threat = severity × confidence × источник × повторяемость
├── persistence.py     находки → Postgres (общая таблица, modality="shadow")
├── persistence.py     находки → таблица shadow_findings (Postgres)
├── collectors/
│   ├── base.py            Collector ABC + RawItem
│   ├── file_collector.py  JSONL экспортированных листингов              [готово]
│   ├── http_page.py       публичные страницы (httpx; .onion через --proxy) [готово]
│   ├── rss.py             RSS/Atom-ленты (stdlib xml)                   [готово]
│   ├── darknet_mock.py    синтетические .onion-листинги для демо        [готово]
│   ├── paste_sites.py     paste/leak-мониторинг (фильтр по утечкам РК)  [готово]
│   └── clearweb.py        парсеры конкретных площадок                   [TODO]
├── seen_store.py      дедуп/инкрементальный сбор (id + контентный хэш)
├── collect.py         CLI: коллектор → пайплайн → граф+БД → топ угроз
├── app.py             автономный FastAPI (/shadow/*), отдельный порт
├── seed_data.py       генератор синтетического seed → data/shadow/seed.jsonl
├── gen_llm.py         LLM-генерация через vLLM + самопроверка → llm_gen.jsonl
├── train_classifier.py / classifier.py   ML-категории (TF-IDF+LogReg, опц. fallback к правилам)
├── run_batch.py       прогон датасета через пайплайн + метрики (точность/покрытие)
└── frontend/index.html   статическая консоль (анализ · сбор · находки · граф)
```

**Данные:** `make shadow-seed` → `make shadow-eval`; `make shadow-gen` (LLM); датасет 326 строк.

**Сбор (реальные источники):**
```bash
make shadow-collect ARGS="--file data/shadow/inbox.jsonl"   # экспортированные листинги
make shadow-collect ARGS="--rss https://site/feed.xml"      # RSS-лента
make shadow-collect ARGS="--paste https://paste/site/raw1"  # пасты → фильтр по утечкам БД РК
make shadow-collect ARGS="--url https://page --proxy socks5h://127.0.0.1:9050"  # страница / Tor
make shadow-collect ARGS="--mock"                            # демо
```
**Инкрементальный сбор:** повторные прогоны пропускают уже виденные элементы (по id и
контентному хэшу, `data/shadow/seen.txt`). Выключить — `ARGS="... --no-dedup"`.

**Кросс-категория и объяснимость связей (граф):**
```bash
curl -X POST localhost:8090/shadow/collect/demo  # наполнить граф демо-кластерами по торговлям
curl "localhost:8090/shadow/clusters"          # кластеры: cross_category, hub («вожак»), risk
curl "localhost:8090/shadow/actors/scored"     # скоринг акторов: actor_risk, co_actors, cross_category
curl "localhost:8090/shadow/path?a=@drop_kz&b=TQn9...Kcbk2v"   # почему две сущности связаны
curl "localhost:8090/shadow/signals"           # легенда: код · вес · описание сигнала
```

**Классификатор категорий (поверх правил):**
```bash
make shadow-train                       # → data/shadow/category_model.joblib (macro-F1 ~0.98)
# включить ML-fallback в пайплайне (когда правила дали unknown):
SHADOW_ML=1 make shadow
```

**Фронт:** `make shadow-front` → http://localhost:8091 (вкладки: Анализ, Сбор-мок, Находки, Теневой граф; поле API → :8090).

**Сбор данных:** ТЗ для студентов (что искать, где, формат, правила §0) — [`docs/digital_shadow_data_task.md`](../../docs/digital_shadow_data_task.md).

## Связь с общим движком
Импортирует всё из `core`: извлечение сущностей, risk_engine, **тот же Neo4j-граф** и Qdrant.
За счёт общего графа находки Digital Shadow и AI Media Watch связываются: например, крипто-кошелёк
из даркнет-листинга = кошелёк из TikTok-инвест-скама → один узел, общая «теневая» сеть.

## Запуск (end-to-end)
```bash
docker compose -f infra/docker-compose.yml up -d qdrant neo4j postgres   # общая инфра
make shadow                                            # сервис на :8090 (граф+БД)

curl localhost:8090/shadow/health                      # {graph_connected, db_enabled}
curl -X POST localhost:8090/shadow/collect/mock        # синтетические даркнет-листинги → находки
curl -X POST localhost:8090/shadow/analyze -H 'Content-Type: application/json' \
     -d '{"id":"t1","source_type":"darknet","text":"продам вейпы оптом без документов, оплата USDT, telegram @dropshop_kz"}'
curl localhost:8090/shadow/graph                       # общий теневой граф (узлы/рёбра)
curl localhost:8090/shadow/sessions                    # сохранённые находки (Postgres)
```

## Реальный Tor (опционально, не для демо)
Поднять Tor SOCKS-прокси (`tor` → `127.0.0.1:9050`), задать `DARKNET_SOCKS=socks5h://127.0.0.1:9050`,
реализовать `collectors/clearweb.py`/`darknet` поверх httpx с этим прокси. Юридически — только с
явным разрешением; ПДн не хранить, только маски/хэши (правило §0).
