# Гайд по проекту: что где лежит

Карта репозитория для студентов — куда заходить, что читать и где какой код.
Система выявляет **риск-сигналы мошенничества** в видео/постах/звонках и в открытых
источниках/DarkNet. Это **два продукта на одном ядре** (см. [two_products.md](two_products.md)).

```
AI Media Watch (контент IG/TikTok/YouTube)  ┐
                                            ├─ общее ядро core (формат, risk, граф, similarity, OSINT)
Digital Shadow (clearweb + DarkNet + paste) ┘
```

---

## 1. С чего начать (читать по порядку)

| Файл | Что внутри |
|---|---|
| [README.md](../README.md) | Обзор, стек, структура, порядок запуска |
| [docs/two_products.md](two_products.md) | Два продукта поверх общего ядра — общая картина |
| [docs/run.md](run.md) | Только команды запуска (Media :8088, Shadow :8090) |
| [docs/guide.md](guide.md) | Запуск + таблица сервисов и доступов (Neo4j/Qdrant/Adminer) |
| [docs/services.md](services.md) | Сервисы, порты, учётки подробно |
| [docs/pipeline.md](pipeline.md) | Полная mermaid-схема пайплайна |
| [fakeface_finguard_student_task.md](../fakeface_finguard_student_task.md) | Исходное ТЗ |

---

## 2. Карта директорий

```
ai_media_watch/
├── core/             ← общий «движок»: единый фасад импортов (README объясняет, что общее)
├── apps/             ← ДВА ПРОДУКТА (точки входа)
│   ├── media_watch/      AI Media Watch — контент-антифрод (API :8088)
│   └── digital_shadow/   Digital Shadow — OSINT/DarkNet (API :8090, UI :8091)
├── backend/app/      ← основной FastAPI-бэкенд (API, сервисы, БД, клиенты)
├── src/              ← библиотеки обработки: извлечение, медиа, граф, risk, синтетика
├── frontend/         ← статический фронт Media Watch (index.html + vis-network)
├── scripts/          ← запуск, тесты, индексация, demo
├── infra/            ← docker-compose (qdrant, neo4j, postgres, adminer, vllm)
├── data/             ← датасеты (raw / processed / shadow)
├── docs/             ← вся документация (этот файл здесь же)
├── tests/            ← юнит-тесты
├── presentation/     ← слайды (HTML)
└── notebooks/        ← Jupyter (обучение fraud-классификатора)
```

---

## 3. Backend — где какой код ([backend/app/](../backend/app/))

| Папка/файл | За что отвечает |
|---|---|
| [main.py](../backend/app/main.py) | Точка входа FastAPI, сборка приложения |
| [config.py](../backend/app/config.py) | Настройки/переменные окружения |
| `api/` | HTTP-эндпоинты: [analyze.py](../backend/app/api/analyze.py), [graph.py](../backend/app/api/graph.py), [search.py](../backend/app/api/search.py), [sessions.py](../backend/app/api/sessions.py), [knowledge.py](../backend/app/api/knowledge.py), [health.py](../backend/app/api/health.py) |
| `services/` | Логика пайплайна: [pipeline.py](../backend/app/services/pipeline.py), [ingest.py](../backend/app/services/ingest.py), [scenario.py](../backend/app/services/scenario.py), [similarity.py](../backend/app/services/similarity.py), [graph.py](../backend/app/services/graph.py), [deepfake.py](../backend/app/services/deepfake.py), [osint.py](../backend/app/services/osint.py), [knowledge.py](../backend/app/services/knowledge.py), [risk.py](../backend/app/services/risk.py) |
| `clients/` | Внешние подключения: [llm.py](../backend/app/clients/llm.py) (vLLM), [qdrant.py](../backend/app/clients/qdrant.py), [neo4j.py](../backend/app/clients/neo4j.py), [db.py](../backend/app/clients/db.py) |
| `schemas/` | Pydantic-модели и enum'ы запросов/ответов |
| `db/` | SQLAlchemy-модели + Alembic-миграции ([db/models.py](../backend/app/db/models.py), `db/migrations/versions/`) |

Пайплайн: `media → текст → сущности → сценарий → similarity+граф+deepfake+OSINT → risk → отчёт → Postgres`.

---

## 4. Два продукта — точки входа ([apps/](../apps/))

**AI Media Watch** — [apps/media_watch/](../apps/media_watch/) ([README](../apps/media_watch/README.md))
- [app.py](../apps/media_watch/app.py) — приложение, [pipeline.py](../apps/media_watch/pipeline.py) — связка с backend.

**Digital Shadow** — [apps/digital_shadow/](../apps/digital_shadow/) ([README](../apps/digital_shadow/README.md))

| Файл | Назначение |
|---|---|
| [app.py](../apps/digital_shadow/app.py) / [pipeline.py](../apps/digital_shadow/pipeline.py) | API и пайплайн OSINT |
| [collectors/](../apps/digital_shadow/collectors/) | Сбор: clearweb, darknet_mock, paste_sites, rss, file, http_page |
| [taxonomy.py](../apps/digital_shadow/taxonomy.py) | Категории + лексикон (ru/kk), сигналы и веса |
| [crypto_risk.py](../apps/digital_shadow/crypto_risk.py) | Оценка криптокошельков |
| [leak_detector.py](../apps/digital_shadow/leak_detector.py) | Детект утечек баз |
| [classifier.py](../apps/digital_shadow/classifier.py) / [train_classifier.py](../apps/digital_shadow/train_classifier.py) | Классификатор находок |
| [prioritization.py](../apps/digital_shadow/prioritization.py) / [actors.py](../apps/digital_shadow/actors.py) / [persistence.py](../apps/digital_shadow/persistence.py) | Приоритизация угроз, акторы, хранение |
| [frontend/index.html](../apps/digital_shadow/frontend/index.html) | UI Shadow (вкладки: Анализ/Сбор/Находки/Граф/Очередь/Watchlist/Акторы) |

Подробнее: [docs/digital_shadow_architecture.md](digital_shadow_architecture.md).

---

## 5. Библиотеки обработки ([src/](../src/))

| Папка | Что делает |
|---|---|
| [src/extraction/](../src/extraction/) | regex-экстракторы, signal_extractor, KazNERD NER |
| [src/media/](../src/media/) | ASR (Whisper), OCR (EasyOCR/Paddle), deepfake-стаб |
| [src/ingest/](../src/ingest/) | url_fetcher: ссылка → текст (yt-dlp + httpx + OCR кадров) |
| [src/graph/](../src/graph/) | построение Shadow Graph (Neo4j) |
| [src/risk/](../src/risk/) | risk_engine — расчёт риск-скоринга |
| [src/parsers/](../src/parsers/) | парсеры датасетов (telegram, youtube, kz_calls, пирамиды) |
| [src/synthetic/](../src/synthetic/) | генерация синтетики: посты, скрипты звонков, TTS, code-switch |
| [src/index_dataset.py](../src/index_dataset.py) · [src/build_dataset.py](../src/build_dataset.py) | индексация в Qdrant и сборка датасета |

---

## 6. Инфра, скрипты, данные

- **Инфра:** [infra/docker-compose.yml](../infra/docker-compose.yml) — qdrant, neo4j, postgres, adminer, vllm (профиль `gpu`).
- **Скрипты:** [scripts/](../scripts/) — [run_demo.sh](../scripts/run_demo.sh), [run_fullstack.sh](../scripts/run_fullstack.sh), [run_vllm.sh](../scripts/run_vllm.sh), [index_afm_kb.py](../scripts/index_afm_kb.py), [ask_afm.py](../scripts/ask_afm.py), `itest_*.py`.
- **Данные:** [data/raw/](../data/raw/) (исходники: phishing, telegram, youtube, deepfake, kz_calls…), `data/processed/`, `data/shadow/`.
- **Конфиг окружения:** [.env.example](../.env.example) → копировать в `.env`.

---

## 7. Быстрый старт (TL;DR)

```bash
# 1. зависимости (uv, без pip)
uv sync && cp .env.example .env

# 2. инфра (без GPU)
docker compose -f infra/docker-compose.yml up -d qdrant neo4j postgres adminer

# 3. продукты
make media          # AI Media Watch → API :8088, фронт :3000
make shadow         # Digital Shadow → API :8090
make shadow-front   #                  UI  :8091

# проверка
curl localhost:8088/health
curl localhost:8090/shadow/health
```

> ⚠️ vLLM (LLM-слой) требует свободный GPU. Без него работает всё, кроме LLM scenario detection —
> можно запускать с `ENABLE_LLM=false`. Полный список команд — [docs/run.md](run.md).

Открыть в браузере: **Media** http://localhost:8088/docs · **Shadow** http://localhost:8091 ·
**Neo4j** http://localhost:7474 · **Qdrant** http://localhost:6333/dashboard · **Adminer** http://localhost:8081
(логины — в [docs/guide.md](guide.md)).
