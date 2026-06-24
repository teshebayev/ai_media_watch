# Два продукта на одном движке: AI Media Watch + Digital Shadow

Проект разделён на **два продукта поверх общего ядра** (`core`). Ядро — то, что реально
общее (формат данных, risk engine, сущности, граф, similarity); продукты различаются только
источниками данных и доменной спецификой.

```
                       ┌──────────────────── core (общий движок) ───────────────────┐
                       │ schemas §5 · risk_engine §11 · entities · signals           │
                       │ Neo4j Shadow Graph · Qdrant similarity · OSINT              │
                       └───────────────▲───────────────────────────▲────────────────┘
                                       │                            │
        ┌──────────────────────────────┘                            └──────────────────────────────┐
        │ apps/media_watch                                           apps/digital_shadow             │
        │ соцвидео IG/TikTok/YouTube                                 clearweb + DarkNet + paste       │
        │ → ASR/OCR/deepfake → scenario                             → контрабанда/дропы/крипто/утечки │
        │ → risk → отчёт + история                                  → risk → приоритизация угроз      │
        └───────────────────────────────────────────────────────────────────────────────────────────┘
                                  общий Neo4j = кросс-продуктовая теневая сеть
```

## Что общее (core)
Фасад `core/` (см. [`core/README.md`](../core/README.md)) даёт единый импорт: формат §5,
`risk_engine` (§11), извлечение сущностей и сигналов, **один Neo4j**, Qdrant, OSINT.
Физически модули остаются в `backend/`+`src/` (чтобы не ломать рабочий стек) — core тянет их по месту.

## Продукт 1 — AI Media Watch (контент)
Постоянный анализ видео/аудио/постов соцплатформ: нелицензионные казино, «гарантированный доход»,
пирамиды, реферальные схемы, deepfake. **Это уже построенный бэкенд** (карта — [`apps/media_watch/README.md`](../apps/media_watch/README.md)).
Доработки: непрерывные коллекторы соцвидео, визуальные маркеры (логотипы/QR), трекинг блогеров.

## Продукт 2 — Digital Shadow (OSINT/DarkNet)
Мониторинг открытых ресурсов и DarkNet: контрабанда (вейпы/алкоголь/наркотики), дропы,
подозрительные криптокошельки, утечки баз РК. Скелет — [`apps/digital_shadow/`](../apps/digital_shadow/README.md):

| Модуль | Назначение |
|---|---|
| `collectors/` | clearweb (httpx) · darknet (мок для демо / реальный Tor) · paste-сайты |
| `taxonomy.py` | категории + лексикон (ru/kk) контрабанды/дропов/утечек + шадоу-сигналы и веса |
| `crypto_risk.py` | оценка кошельков: формат, badlist, миксеры → сигналы |
| `leak_detector.py` | детект утечек БД РК (.kz, маски ИИН, breach-лексика) |
| `prioritization.py` | threat = severity × confidence × источник × повторяемость в графе |
| `pipeline.py` | сырой элемент → сущности → сигналы → риск → приоритет → находка |
| `app.py` | автономный FastAPI `/shadow/*` (отдельный порт) |

Новые сигналы (`darknet_listing`, `contraband_keyword`, `drug_slang`, `drop_recruitment`,
`kz_data_leak`, `iin_dump_mention`, `bad_crypto_wallet`, `mixer_or_tumbler`, …) добавлены
**поверх** общего движка, не меняя общий `enums`/`risk_engine`; их веса — в `taxonomy.py`.

## Синергия (главное «дополнение»)
Оба продукта пишут сущности в **один Neo4j**. Кошелёк/домен/Telegram из TikTok-инвест-скама
(Media Watch) и из даркнет-листинга (Digital Shadow) сходятся в **один узел** → видна общая
теневая сеть: «промо-блогер ↔ даркнет-дроп ↔ кошелёк ↔ утечка». Это аргумент за монорепо,
а не два изолированных репозитория.

## Структура монорепо
```
core/                 фасад общего движка
apps/media_watch/     app.py (= backend) + pipeline.py (поверхность media-пайплайна)
apps/digital_shadow/  app.py · pipeline.py · taxonomy · crypto_risk · leak_detector
                      · prioritization · persistence · collectors/
backend/ · src/       реализация (общий движок + media-пайплайн) — на месте
infra/                один docker compose (общие Qdrant + Neo4j + Postgres)
```

## Запуск — два независимых end-to-end сервиса на общем движке
Оба поднимают инфраструктуру в своём lifespan и пишут в **общий Neo4j + Postgres**.
Сначала инфра: `docker compose -f infra/docker-compose.yml up -d qdrant neo4j postgres`.

```bash
# Продукт 1 — AI Media Watch (:8088): apps/media_watch/app.py = полный backend
make media          # или: make stack-docker (контейнеры: +фронт :3000)

# Продукт 2 — Digital Shadow (:8090): отдельный сервис, не мешает основному
make shadow                                         # API :8090
make shadow-front                                   # статический фронт :8091 → API :8090
curl localhost:8090/shadow/health                   # {graph_connected, db_enabled}
curl -X POST localhost:8090/shadow/collect/mock     # даркнет-листинги → находки (граф+БД)
curl localhost:8090/shadow/graph                    # общий теневой граф (узлы/рёбра)
curl localhost:8090/shadow/sessions                 # сохранённые находки (Postgres)
```

Сбор данных под Digital Shadow (что искать, где, формат, правила §0) — ТЗ для студентов:
[`digital_shadow_data_task.md`](digital_shadow_data_task.md).

Проверено end-to-end: `collect/mock` → 4 находки классифицированы (drug/drop/leak/vape),
сущности влиты в общий Neo4j, находки сохранены в Postgres (таблица `shadow_findings`).

## Дорожная карта Digital Shadow
- [x] общий Neo4j-driver в `app.py`, кросс-продуктовый граф вживую (связка по кошельку проверена)
- [x] персистентность находок — своя таблица `shadow_findings` (Alembic 0003), фильтры в `/shadow/sessions`
- [x] коллекторы-фреймворк: `FileCollector` / `HttpPageCollector` (+Tor через `--proxy`) / `RssCollector` + CLI `collect.py`
- [x] ML-классификатор категорий (`train_classifier.py`, macro-F1 ≈ 0.98) + опц. fallback к правилам (`SHADOW_ML=1`)
- [x] триаж + ревью аналитика (`shadow_findings.status` + `shadow_reviews`, `/shadow/queue`, `/review`)
- [x] watchlist отслеживаемых сущностей (`shadow_watchlist`, сигнал `watchlisted`) + профили акторов (`/shadow/actors`, `/cross`)
- [ ] парсеры конкретных площадок (`clearweb.py`) и paste-фиды (`paste_sites.py`) — точечно под источники
- [ ] фид «плохих» кошельков + цепочная аналитика (метки бирж/миксеров) — `crypto_risk.py`
- [ ] курируемый лексикон контрабанды/дропов (ru+kk) со специалистами — `taxonomy.py`

## Заказчик и ценность (РК)
Покупатель — **АФМ РК** (Агентство по финансовому мониторингу), AML-подразделения банков
и финмониторинг. Ценность в их терминах: (1) **вскрытые сети** — общий граф связывает
блогера-инвестскам, даркнет-дроп, кошелёк и утечку в один кластер (на демо-данных **33%
теневых сущностей всплывают и в медиа-контенте**, [cross_product_demo.md](cross_product_demo.md));
(2) **сэкономленные часы аналитика** — триаж по threat_score, объяснимое evidence и flywheel
(подтверждённый индикатор сам поднимает приоритет будущих находок) сокращают ручной разбор;
(3) **низкий шум** — FPR 0% на legit-контрпримерах (hold-out), то есть мало ложных тревог.
Система выявляет риск-сигналы и **передаёт на ручную проверку**, не выносит обвинение (§0).

## Безопасность (§0, для обоих продуктов)
Только публичные источники; ПДн из утечек/дампов не сохраняем (маски/хэши); система выявляет
риск-сигналы и передаёт на ручную проверку, не выносит обвинение.
