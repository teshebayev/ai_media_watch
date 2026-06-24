# FakeFace FinGuard — план инфраструктуры MVP

Стек: **uv + FastAPI + vLLM + Qdrant + Neo4j + Postgres + Next.js + Docker Compose**

Целевая (= итоговая) схема:

```text
Браузер: Next.js-консоль (:3000) / статический фронт / curl
        │  fetch :8088 (CORS *)
        ▼
┌──────────────────────────────────────────────┐
│  FastAPI (api)  — оркестратор пайплайна        │
│  ├── Ingest        url_fetcher (yt-dlp/httpx)  │
│  ├── Media         ffmpeg · Whisper · EasyOCR  │
│  ├── Entity        regex + KazNERD + LLM-добор │
│  ├── Scenario      LLM-классификация (vLLM)    │
│  ├── Similarity    Qdrant (scam_cases)         │
│  ├── Graph         Neo4j (Shadow Graph)        │
│  ├── Deepfake      внешний venv (ViT+Wav2Vec2) │
│  ├── OSINT         репутация доменов (+PhishTank)│
│  ├── Risk Engine   детерминированный скоринг §11│
│  └── AFM-агент     RAG: Qdrant afm_knowledge + LLM│
└──┬─────┬─────┬─────┬───────────────────────────┘
   ▼     ▼     ▼     ▼
 vLLM  Qdrant Neo4j Postgres        Deepfake (свой venv, subprocess)
(LLM) (вектора)(граф)(сеансы+ревью)
```

Развёртывание — один `docker compose` (`make stack-docker`): qdrant·neo4j·postgres·adminer·api·frontend;
vLLM — в профиле `gpu`. api-образ слим ~2.3 ГБ (CPU-torch, runtime-only). Подробности — `docs/pipeline.md` и `docs/services.md`.

---

## Статус реализации (2026-06-13)

Что собрано и работает **на CPU** (GPU занят сторонней задачей; для моделей — `CUDA_VISIBLE_DEVICES=""`):

| Слой | Статус | Чем реализован / отклонения от плана |
|---|---|---|
| FastAPI каркас (Этап 3) | ✅ | роутеры `/analyze/{text,url,audio,video}`, `/graph/{entity,network}`, `/search`, `/health` + CORS |
| Risk Engine (Этап 6) | ✅ | детерминированный `src/risk/risk_engine.py` (§11) + regex (§10) + signal_extractor |
| Qdrant (Этап 4) | ✅ | поднят в Docker, **834 точки** (`scam_cases`); `multilingual-e5`; `.search`→`query_points` (API 1.12) |
| Neo4j / Shadow Graph (Этап 5) | ✅ | **834 узла, 875 связей**; повторяемость доменов/промокодов; `/graph/network` для виз-графа |
| Media ASR (Этап 8.2) | ✅ | faster-whisper на CPU; WER ru 0.29 / kk 0.91 (`docs/asr_kk_findings.md`) |
| Media OCR (Этап 4) | ✅ | **EasyOCR** вместо PaddleOCR (надёжнее ставится: torch уже есть); кадры + превью видео |
| TTS (Этап 8.2) | ✅ | **Meta MMS-TTS** (`facebook/mms-tts-rus`/`-kaz`) вместо Silero/KazakhTTS2 — один CPU-стек |
| KZ NER (Этап 8.4) | ✅ | KazNERD `yeshpanovrustem/xlm-roberta-large-ner-kazakh`, второй проход для kk |
| Синтетика (Этап 8.1) | ✅ | 160 звонков + 81 пост + **Stop-Piramida 593** (Whisper) + аугментация kk (перевод/LLM/code-switch) → единый датасет **834 строки** |
| LLM-слой (Этап 2) | ✅ | vLLM (Qwen2.5) поднят, scenario detection в `/analyze/*` вживую |
| AFM Knowledge Agent | ✅ | RAG поверх Qdrant (`afm_knowledge`): гибридный поиск dense e5 + sparse BM25 (RRF) + ответ vLLM/fallback; `/agent/*` |
| Классификатор | ✅ | `notebooks/fraud_classifier.ipynb`: TF-IDF/Word2Vec/mBERT/e5 × 5 моделей; лучший e5+LogReg, macro-F1 ≈ 0.82 |
| Deepfake (Этап 8.3) | ✅ | внешний детектор `external/fakeface-detector` (свой venv, ViT+Wav2Vec2) через subprocess → `media_anomalies` в `/analyze/video`+`url(deep)` |
| OSINT / репутация | ✅ | `services/osint.py`: тайпсквоттинг KZ-брендов + TLD (+опц. PhishTank) → `phishing_url`/`suspicious_domain` |
| Постоянное хранилище | ✅ | **Postgres** (:5433) + SQLAlchemy async + Alembic; `analysis_sessions`(+media_anomalies) + `analyst_reviews`; `/sessions` `/stats` |
| Фронтенд | ✅ | Next.js-консоль (`av1cu/ai_media_watch_frontend`, лендинг+`/console`) + статический `frontend/index.html` |
| Docker-стек | ✅ | `docker compose up` → infra+api+frontend; **слим api-образ ~2.3 ГБ** (CPU-torch, runtime-only); vLLM в профиле `gpu` |

**Сверх плана добавлено:**
- **Ingest по ссылке** (`/analyze/url`, `src/ingest/`): YouTube/Instagram/TikTok через yt-dlp
  (метаданные + субтитры + OCR превью; deep-режим — OCR кадров + deepfake с guard-ами); HTML/Telegram через httpx.
- **OSINT/репутация** (`services/osint.py`) и **deepfake-детектор** (`services/deepfake.py` → внешний venv).
- **AFM Knowledge Agent** (`services/knowledge.py`, `/agent/*`): RAG-Q&A по базе АФМ, гибридный поиск (dense e5 + sparse BM25, серверный RRF в Qdrant) + ответ vLLM/fallback; на фронте — вкладка «AFM-агент».
- **Next.js-фронт** (`av1cu/ai_media_watch_frontend`) + статический `frontend/index.html` (vis-network граф, История).
- **Классификатор** `notebooks/fraud_classifier.ipynb` (TF-IDF/Word2Vec/mBERT/e5 × 5 моделей).
- **Один docker-стек** (`make stack-docker`) со слим api-образом; запуск на хосте — `make stack` / `scripts/run_fullstack.sh`.
- Скрипты проверки: `scripts/itest_services.py`, `scripts/itest_http.py`.

Подробный чек-лист и команды — [`finguard_work_plan.md`](finguard_work_plan.md).

---

## Этап 0. Репозиторий и uv (30 мин)

1. Создать repo, скопировать структуру папок из ТЗ (раздел 16) + добавить `infra/` и `backend/`.

2. Инициализировать проект через uv:

```bash
uv init finguard --python 3.12
cd finguard
uv add fastapi "uvicorn[standard]" pydantic-settings httpx
uv add qdrant-client neo4j openai          # openai-клиент → vLLM (OpenAI-compatible)
uv add faster-whisper easyocr sentence-transformers
uv add python-multipart yt-dlp sqlalchemy asyncpg alembic
uv add --dev pytest ruff
```

3. Зафиксировать: `uv lock`. В репо коммитим `pyproject.toml` + `uv.lock`.

4. Договориться с командой: **никаких pip install — только `uv add` / `uv sync`**.

Фактическая структура (на 2026-06-13):

```text
ai_media_watch/
├── pyproject.toml · uv.lock · .env.example · Makefile · alembic.ini
├── infra/docker-compose.yml          # qdrant·neo4j·postgres·api·frontend (+vllm profile gpu)
├── backend/
│   ├── Dockerfile · requirements-runtime.txt   # слим-образ: CPU-torch + runtime-only
│   └── app/
│       ├── main.py · config.py
│       ├── api/        # analyze (text/url/audio/video), graph, search, sessions, health
│       ├── services/   # media, entities, scenario, similarity, graph, risk, pipeline, ingest, deepfake, osint, sessions
│       ├── clients/    # qdrant.py, neo4j.py, llm.py, db.py (DI)
│       ├── db/         # SQLAlchemy-модели + Alembic-миграции (Postgres)
│       └── schemas/    # Pydantic-модели + enums (единый JSONL-формат §5)
├── src/
│   ├── extraction/ # regex_extractors, signal_extractor, kaznerd_ner
│   ├── media/      # asr_whisper, ocr (EasyOCR), ocr_paddle (альт.), asr_check, fakeface_*
│   ├── synthetic/  # gen_call_scripts, gen_posts, tts_batch (MMS-TTS)
│   ├── ingest/     # url_fetcher (yt-dlp + httpx + OCR превью/кадров)
│   ├── graph/      # graph_schema.cypher, build_graph, build_from_dataset
│   ├── risk/       # risk_engine
│   ├── parsers/    # parse_youtube/telegram/ready/kz
│   ├── index_dataset.py · build_dataset.py
│   └── app/        # streamlit_app.py (альт. UI)
├── frontend/       # index.html (статика) + vendor/vis-network.min.js
├── external/       # fakeface-detector (свой venv, deepfake) — gitignored
├── scripts/        # run_fullstack.sh, run_demo.sh, run_vllm.sh, itest_*, process_stop_piramida.py
├── presentation/   # index.html (слайды архитектуры)
├── notebooks/      # fraud_classifier.ipynb (классификатор)
├── docs/           # pipeline.md, asr_kk_findings.md, гайды
├── tests/          # test_risk_engine, test_regex_extractors
└── data/{raw,processed}/
# рядом (отдельный репо): ~/ai_media_watch_frontend — Next.js-консоль
```

---

## Этап 1. Docker Compose — поднять всю инфраструктуру (1–1.5 ч)

> ℹ️ Ниже — исходный план. **Итоговый** `infra/docker-compose.yml` отличается: добавлены
> `postgres`, `adminer`, `frontend`; `vllm` вынесен в профиль `gpu`; api наружу на `:8088→8080`;
> api-образ слим (CPU-torch). Актуальную схему см. в `docs/pipeline.md` / `docs/services.md`.

`infra/docker-compose.yml` (план):

```yaml
services:
  vllm:
    image: vllm/vllm-openai:latest
    command: >
      --model Qwen/Qwen2.5-7B-Instruct
      --max-model-len 8192
      --gpu-memory-utilization 0.90
    ports: ["8000:8000"]
    volumes:
      - hf_cache:/root/.cache/huggingface
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333", "6334:6334"]   # REST + gRPC
    volumes:
      - qdrant_data:/qdrant/storage

  neo4j:
    image: neo4j:5
    ports: ["7474:7474", "7687:7687"]   # browser + bolt
    environment:
      NEO4J_AUTH: neo4j/finguard_pass
    volumes:
      - neo4j_data:/data

  api:
    build: ../backend
    ports: ["8080:8080"]
    env_file: ../.env
    depends_on: [vllm, qdrant, neo4j]
    volumes:
      - ../data:/app/data

volumes:
  hf_cache:
  qdrant_data:
  neo4j_data:
```

`backend/Dockerfile` (с uv):

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ ./backend/
CMD ["uv", "run", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Чек-лист этапа:

- [ ] `docker compose up -d` — все 4 контейнера живы
- [ ] `curl localhost:8000/v1/models` — vLLM отвечает
- [ ] `curl localhost:6333/collections` — Qdrant отвечает
- [ ] Neo4j Browser открывается на `localhost:7474`
- [ ] Если GPU нет/слабый — fallback: vLLM с `Qwen2.5-1.5B-Instruct`, либо временно Ollama, интерфейс тот же (OpenAI-compatible)

---

## Этап 2. vLLM — LLM-слой (1 ч)

vLLM даёт OpenAI-совместимый API, поэтому клиент один:

```python
# clients/llm.py
from openai import AsyncOpenAI

llm = AsyncOpenAI(base_url="http://vllm:8000/v1", api_key="dummy")
```

Три задачи LLM в пайплайне:

1. **Scenario detection** — классификация `combined_text` в `fraud_type` (список из ТЗ §7). Промпт: system с описанием категорий + few-shot из размеченных примеров, ответ строго JSON (`{"fraud_type": ..., "confidence": ..., "evidence_spans": [...]}`).
2. **Entity extraction (второй проход)** — regex ловит формальные сущности (ТЗ §10), LLM добирает названия проектов, организации, pressure-фразы.
3. **Объяснение для Analyst Report** — генерация человекочитаемого summary по найденным сигналам.

Правило для надёжности: LLM **не ставит** risk_score — только сигналы и категории. Скоринг детерминированный (этап 6).

- [ ] Проверить JSON-output на 5 примерах из ТЗ (gambling, eGov call, пирамида)
- [ ] Замерить латентность; если > 5 c на запрос — уменьшить max_tokens / модель

---

## Этап 3. FastAPI backend — каркас и пайплайн (2–3 ч)

Слоистая структура (как в твоих FastAPI-проектах):

```text
api/routers      → /analyze, /graph, /search, /health
services/        → бизнес-логика, каждый агент из ТЗ = сервис
clients/         → подключения (DI через Depends + lifespan)
schemas/         → Pydantic-модели = единый JSONL-формат ТЗ §5
```

Ключевые эндпоинты:

| Метод | Путь | Что делает |
|---|---|---|
| `POST` | `/analyze/video` | upload видео → ffmpeg → Whisper + кадры → OCR → полный пайплайн |
| `POST` | `/analyze/audio` | звонок → Whisper → stage detection → пайплайн |
| `POST` | `/analyze/text` | пост/текст → entity → scenario → пайплайн |
| `POST` | `/analyze/url` | ссылка (YouTube/IG/TikTok/HTML) → ingest (метаданные+субтитры+OCR превью; `deep` — OCR кадров) → пайплайн |
| `GET` | `/graph/entity/{value}` | повторяемость сущности из Neo4j |
| `GET` | `/graph/network` | подграф nodes/edges для визуализации (окрестность сущности / обзор кластеров) |
| `GET` | `/search/similar` | похожие кейсы из Qdrant |
| `GET` | `/sessions` · `/sessions/{id}` | история анализов из Postgres |
| `POST` | `/sessions/{id}/review` | ручная проверка аналитика (confirm/override) |
| `GET` | `/stats` | агрегаты: по risk_level, топ fraud_type, сколько проверено |
| `GET` | `/health` | пинг vLLM/Qdrant/Neo4j |

*(реализовано синхронно: `/analyze/*` сразу возвращают Analyst Report; вариант с `job_id`/`GET /report/{id}` — на будущее под нагрузку.)*

Пайплайн внутри `/analyze/*` (последовательность из ТЗ §2):

```text
media → combined_text → entities (regex+LLM) → scenario (LLM)
→ similarity (Qdrant) → graph upsert (Neo4j) → risk engine → report
```

Whisper/OCR — синхронные и тяжёлые → выносить в `run_in_executor` или фоновую задачу с job-таблицей (aiosqlite, как в твоём транскрибере). Для хакатона достаточно: `POST /analyze` возвращает `job_id`, `GET /report/{id}` отдаёт результат.

- [ ] `/analyze/text` работает end-to-end на синтетическом примере
- [ ] `/analyze/audio` работает на одном синтетическом звонке
- [ ] `/analyze/video` работает на одном ролике

---

## Этап 4. Qdrant — векторный слой (1–1.5 ч)

Зачем Qdrant в этом проекте: **поиск похожих известных scam-кейсов** — «этот текст похож на 7 уже размеченных gambling-промо» → это и сигнал (`similar_to_known_scam`), и evidence для отчёта.

1. Модель эмбеддингов: `intfloat/multilingual-e5-base` (ru/kz/en) через `sentence-transformers` (добавить `uv add sentence-transformers`), либо отдавать эмбеддинги через vLLM, если поднимете embedding-модель отдельно.

2. Коллекция:

```python
client.create_collection(
    "scam_cases",
    vectors_config=VectorParams(size=768, distance=Distance.COSINE),
)
```

   Payload = весь объект единого JSONL-формата (label, fraud_type, risk_level, entities).

3. Скрипт `src/index_dataset.py`: прочитать `ai_media_watch_dataset.jsonl` → эмбеддинг `combined_text` → upsert в Qdrant. Запускать каждый раз, когда студенты доливают разметку.

4. В пайплайне: top-5 ближайших; если ≥3 соседа с label=scam и score > 0.8 → сигнал `similar_to_known_scam` (+20 к скорингу — согласовать с командой).

- [ ] 200 примеров из датасета проиндексированы
- [ ] `/search/similar?text=...` возвращает осмысленных соседей

---

## Этап 5. Neo4j — Shadow Graph (1.5–2 ч)

1. Схема — ровно из ТЗ §12: constraints на уникальность ключевых узлов:

```cypher
CREATE CONSTRAINT IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (t:TelegramUsername) REQUIRE t.name IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (p:PromoCode) REQUIRE p.code IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (w:Wallet) REQUIRE w.address IS UNIQUE;
```

2. `services/graph.py`: после entity extraction — `MERGE` узлов и связей:

```cypher
MERGE (v:Video {id: $id})
MERGE (d:Domain {name: $domain})
MERGE (v)-[:MENTIONS]->(d)
```

   Телефоны и карты — **только хэш/маска** (правило безопасности из ТЗ §0).

3. Ключевой запрос «повторяемость» (главная фича для демо):

```cypher
MATCH (d:Domain)<-[:MENTIONS]-(v:Video)
WITH d, count(v) AS uses
WHERE uses > 1
RETURN d.name, uses ORDER BY uses DESC
```

   Если сущность встречается в ≥2 источниках → сигнал `graph_entity_reuse` (+25 по таблице ТЗ §11).

4. Загрузить `entities_nodes.csv` / `entities_edges.csv` от Студента 8 скриптом `src/graph/build_graph.py`.

- [ ] Кластер `blogger → video → domain → promo → telegram` виден в Neo4j Browser
- [ ] `/graph/entity/{domain}` возвращает повторяемость

---

## Этап 6. Risk Engine (1 ч)

Чисто детерминированный, без LLM:

1. Таблица весов из ТЗ §11 → dict в `services/risk.py`.
2. `risk_score = min(100, sum(weights[s] for s in signals))`.
3. Пороги: 0–24 low, 25–49 medium, 50–79 high, 80–100 critical.
4. Вход — сигналы из всех слоёв: text (regex/LLM) + media anomalies + qdrant similarity + graph reuse + OSINT (PhishTank, если успеете).
5. Выход — Analyst Report (Pydantic): evidence_spans, entities, triggered signals с баллами, recommendation. Формулировка из ТЗ §0: система выявляет риск-сигналы и передаёт на ручную проверку, не обвиняет.

- [ ] Юнит-тест: пример kz_call_001 из ТЗ даёт critical (95±)

---

## Этап 7. Сборка демо (2 ч)

1. Next.js-консоль (Студент 8, репо `av1cu/ai_media_watch_frontend`) ходит в FastAPI: анализ → отчёт + граф + История/Статистика + AFM-агент. Запасной — статический `frontend/index.html`.
2. Прогнать три демо-сценария из ТЗ §18: gambling-видео, eGov-звонок, deepfake promo.
3. `make stack-docker` — одна команда поднимает весь стек (инфра+api+фронт; vLLM — профиль `gpu`).
4. `.env.example` + README с командами запуска.

---


## Этап 8. Synthetic Data Generation — голос, лица, текст (kk-акцент)

Отдельный пайплайн, не зависит от бэкенда — можно запускать с первого часа параллельно. Главная фишка: **синтетика размечает себя сама** — если аудио сгенерировано TTS, то `synthetic_voice_suspected = true` по построению; если видео собрано talking-head моделью, то `possible_deepfake = true`. Бесплатные ground-truth метки.

```text
Сценарии (текст, ru/kk)
   ↓
TTS: KazakhTTS2 / EmoTTS  →  .wav   (synthetic_voice_suspected = true)
   ↓
Лицо: StyleGAN / SDXL (несуществующее) или согласившийся тиммейт
   ↓
Talking head: SadTalker / Wav2Lip / LivePortrait  →  .mp4   (possible_deepfake = true)
   ↓
Авторазметка → строки в ai_media_watch_dataset.jsonl
```

### 8.1. Текст: сценарии звонков и постов

Без отдельной казахской LLM. Источники сценариев:

1. **Шаблоны + подстановка** — взять ключевые фразы из ТЗ §2.4 (ru и kk: «қауіпсіз шот», «SMS кодын айтыңыз», «ешкімге айтпаңыз»…) и собрать генератор-комбинатор: `этап звонка × организация × требуемый секрет × pressure-фраза`. 5 этапов × 4 организации × 4 секрета = десятки уникальных диалогов из одного скрипта `src/synthetic/gen_call_scripts.py`.
2. **Уже поднятый vLLM (Qwen2.5)** — сносно пишет по-казахски для уровня учебных сценариев; генерировать по few-shot из шаблонов п.1, носитель из команды вычитывает.
3. **Выход:** `kz_call_scripts.csv` (колонки: `id, language, case_type, stage, text`) — deliverable Студента 5 из ТЗ.

Параллельно — 30–40 **legit-примеров** (официальные предупреждения, обычные финансовые посты), иначе классификатор выучит «казахский язык = scam».

### 8.2. Голос: казахский TTS

- **KazakhTTS2 (ISSAI)** — открытый корпус ~270 ч, 5 дикторов, готовые ESPnet-рецепты и чекпойнты (GitHub IS2AI, HF issai). Базовый вариант: батч-скрипт текст → wav.
- **Kazakh Emotional TTS (ISSAI, 2024)** — эмоциональный синтез; для scam-звонков критично: срочность, давление, страх. Использовать для «горячих» этапов звонка (КНБ, безопасный счёт).
- **Русские реплики** — любой ru TTS (Silero — лёгкий, ставится через `uv add torch silero`, работает на CPU).
- Для разнообразия дикторов: прогнать один сценарий несколькими голосами/эмоциями.
- Скрипт `src/synthetic/tts_batch.py`: csv сценариев → `data/raw/kz_calls/*.wav` + сразу JSONL-строка с `modality: audio`, `source: synthetic_tts`, `media_anomalies.synthetic_voice_suspected: true`.

**Замкнуть петлю:** прогнать полученные wav через свой же `/analyze/audio` — это одновременно тест пайплайна и готовые transcript-поля.

### 8.3. Лица и видео: deepfake-примеры

Правило (из ТЗ §0 и кейса 9.3): **никаких реальных публичных лиц**. Детектору не нужны личности — он учится на артефактах синтеза. Три легальных источника:

- **Несуществующие лица:** StyleGAN2/3 или SDXL → портрет → анимировать talking-head моделью под TTS-аудио:
  - **SadTalker** — фото + аудио → говорящая голова, самый простой путь;
  - **Wav2Lip** — перерисовка губ под аудио; даёт хрестоматийные `lip_sync_anomaly`;
  - **LivePortrait** — анимация по driving-видео, качество выше.
- **Согласившиеся тиммейты:** записать друг друга → сделать дипфейк коллеги. Для защиты это сильный слайд: «реальный человек vs его дипфейк, система ловит».
- **Готовые датасеты из ТЗ §3.3:** FaceForensics++, DFDC, FakeAVCeleb — там уже есть мультимодальные дипфейки (включая известных людей), собранные легально под research-лицензией. Если на демо нужен сюжет «известное лицо + финансовый призыв» — брать оттуда, не генерировать самим.

Каждое сгенерированное видео → JSONL с `possible_deepfake: true`, `case_type: deepfake_financial_promo`; реальные записи тиммейтов до обработки → negative-класс (`possible_deepfake: false`). Это deliverable Студента 6.

### 8.4. Казахский NER и ASR-проверка

- **KazNERD (ISSAI)** — ~112k размеченных kk-предложений, 25 классов + готовые модели на HF. Подключить в Entity Service вторым проходом после regex: организации, имена, локации в казахском тексте.
- **KSC2 / Soyle (ISSAI)** — взять 20–30 казахских записей и замерить WER Whisper'а на kk. Если Whisper плохо тянет казахский — переключить kk-аудио на модель Soyle, интерфейс сервиса не меняется (адаптер в `services/media.py`).

#### Чек-лист этапа

- [ ] `gen_call_scripts.py` генерирует ≥30 ru/kk сценариев в `kz_call_scripts.csv`
- [ ] `tts_batch.py` озвучивает их в `data/raw/kz_calls/*.wav` с авторазметкой `synthetic_voice_suspected: true`
- [ ] ≥20 deepfake-видео (talking-head) + negative-класс реальных тиммейтов
- [ ] полученные wav прогнаны через `/analyze/audio` (петля проверки)
- [ ] KazNERD подключён вторым проходом в Entity Service для kk-текста


## Порядок работ и зависимости

```text
Этап 0 (uv, repo)          ──┐
Этап 1 (docker compose)    ──┼─→ Этап 3 (FastAPI каркас)
Этап 2 (vLLM промпты)      ──┘        │
                                      ├─→ Этап 4 (Qdrant)   ─┐
                                      ├─→ Этап 5 (Neo4j)    ─┼─→ Этап 6 (Risk) → Этап 7 (демо)
                                      └─→ media-сервисы      ─┘

Этап 8 (synthetic data)   ───────────────────────────────────→ кормит датасет на всех этапах
   (независим, с 1-го часа; нужен только vLLM для kk-генерации и /analyze/audio для петли)
```

Этапы 4 и 5 независимы — можно делать параллельно двумя людьми. Этап 8 не зависит от бэкенда и поставляет размеченные данные (self-labeled синтетика) параллельно остальным. Если время горит, минимальный жизнеспособный срез: **Этап 0–3 + 6** (текстовый пайплайн с regex + LLM + скоринг), Qdrant и граф добавляются поверх без переделки API.

## Риски и запасные варианты

| Риск | План Б |
|---|---|
| Нет GPU для vLLM | Меньшая модель (1.5B) или Ollama; клиентский код не меняется |
| Whisper медленный | faster-whisper `small`, int8; для демо — заранее посчитанные транскрипты |
| OCR тяжело ставится | Используем EasyOCR (ставится с torch); можно прогнать OCR заранее и отдавать из кэша |
| Не успели Qdrant | Сигнал similarity выключается флагом, скоринг работает |
| Не успели Neo4j | Граф рисуется из CSV / статического фронта (vis-network) |
| KazakhTTS2/talking-head тяжело ставить | Текстовый слой (`gen_call_scripts.py`) + ru Silero на CPU; deepfake-видео берём из готовых FaceForensics++/DFDC/FakeAVCeleb |
| Whisper плохо тянет kk | Замерить WER на KSC2/Soyle; адаптер в `services/media.py` переключает kk-аудио на Soyle |
