# FakeFace FinGuard + Shadow Graph

Мультимодальная аналитическая система выявления **риск-сигналов мошенничества** в видео,
постах и звонках: реклама онлайн-казино, финансовые пирамиды, фишинг, fake eGov/КНБ-звонки,
deepfake-реклама и связанные цифровые следы.

> Система не выносит юридическое обвинение. Она выявляет риск-сигналы, объясняет причины
> и передаёт материал на ручную проверку аналитика. (ТЗ §0)

Стек: **uv + FastAPI + vLLM (Qwen2.5) + Qdrant + Neo4j + Postgres + Next.js + Docker Compose**.
ТЗ — [`fakeface_finguard_student_task.md`](fakeface_finguard_student_task.md),
план инфраструктуры — [`finguard_infra_plan.md`](finguard_infra_plan.md),
полная схема — [`docs/pipeline.md`](docs/pipeline.md), сервисы и доступы — [`docs/services.md`](docs/services.md).

## Пайплайн (ТЗ §2)
```
media → combined_text → entities (regex+NER+LLM) → scenario (LLM)
→ similarity (Qdrant) + graph (Neo4j) + deepfake + OSINT → risk engine → Analyst Report → Postgres
```
Поверх той же Qdrant — **AFM Knowledge Agent** (RAG): гибридный поиск (dense e5 + sparse BM25, RRF)
по базе знаний АФМ + ответ vLLM (`/agent/*`). Полная mermaid-схема — в [`docs/pipeline.md`](docs/pipeline.md).

## Структура
```
backend/app/        FastAPI: api/ (analyze/graph/search/sessions/agent/health), services/ (pipeline/ingest/scenario/similarity/graph/deepfake/osint/knowledge/sessions), clients/, schemas/, db/ (SQLAlchemy + Alembic)
src/extraction/     regex_extractors, signal_extractor, kaznerd_ner
src/media/          asr_whisper, ocr (EasyOCR), asr_check, fakeface_*
src/synthetic/      gen_call_scripts, gen_posts, tts_batch (MMS-TTS)
src/ingest/         url_fetcher — ссылка → текст (yt-dlp + httpx + OCR превью/кадров)
external/           fakeface-detector (изолированный venv, deepfake-детектор; gitignored)
src/graph/ risk/ parsers/   Shadow Graph, risk_engine, парсеры; index_dataset.py, build_dataset.py
frontend/           index.html (статика) + vendor/vis-network.min.js — фронт с граф-визуализацией
scripts/            run_demo.sh, itest_services.py, itest_http.py
infra/              docker-compose.yml · presentation/ — слайды · docs/ — гайды + asr_kk_findings
data/raw, data/processed   датасеты · tests/ — юнит-тесты
```

## Запуск — порядок (НЕ запускать, пока занят GPU)
> ⚠️ На этой машине vLLM требует GPU. Если идёт другая GPU-задача — поднимать vLLM нельзя
> (out-of-memory). Можно работать без LLM: `ENABLE_LLM=false` — пайплайн считается на regex.

**Самый быстрый путь — одна команда** (всё в контейнерах, см. `make stack-docker` ниже).
Ручной порядок для разработки:

1. Зависимости (uv, **без pip**):
   ```bash
   uv sync           # по pyproject.toml + uv.lock
   ```
   OCR — EasyOCR (ставится вместе с torch, отдельной установки не требует). Тяжёлый
   обучающий/синтетический стек (KazNERD, MMS-TTS) — опционально, у того, кто им занимается.

2. Окружение:
   ```bash
   cp .env.example .env
   ```

3. Инфраструктура (без GPU): qdrant + neo4j + postgres + adminer
   ```bash
   docker compose -f infra/docker-compose.yml up -d qdrant neo4j postgres adminer
   ```
   vLLM поднимается отдельно (профиль `gpu`): `docker compose --profile gpu up -d vllm`.

### ⚠️ Порт-конфликты на этой машине
- **host:8000 уже занят** сторонним `embeddings-service` (uvicorn). Поэтому vLLM наружу
  отдаётся на `VLLM_HOST_PORT` (по умолчанию **8100**). Внутри docker-сети сервис всё
  равно слушает `8000`, backend ходит на `http://vllm:8000/v1` — клиент менять не нужно.
- Проверьте, что свободны: `6333/6334` (Qdrant), `7474/7687` (Neo4j), `8088` (API; наружу проброшен `8088→8080`, см. `API_HOST_PORT`).

## Проверки (план, этапы 1–6)
```bash
curl localhost:8100/v1/models     # vLLM (наружный порт)
curl localhost:6333/collections   # Qdrant
# Neo4j Browser: http://localhost:7474
curl localhost:8088/health        # пинг всех сервисов
make test                         # risk engine + regex
```

## Минимальный жизнеспособный срез (без GPU/внешних сервисов)
Текстовый пайплайн (regex + signal_extractor + risk_engine) работает без vLLM/Qdrant/Neo4j —
выставьте флаги `ENABLE_LLM/ENABLE_SIMILARITY/ENABLE_GRAPH=false` и дёргайте `POST /analyze/text`.

## Фронтенды
Два варианта UI поверх одного API:
- **Next.js-консоль** (репо [av1cu/ai_media_watch_frontend](https://github.com/av1cu/ai_media_watch_frontend)) —
  основной фронт (лендинг + `/console`), контракт 1-в-1 с нашим API. Запуск всей связки:
  ```bash
  docker compose -f infra/docker-compose.yml up -d qdrant neo4j postgres   # инфра
  git clone https://github.com/av1cu/ai_media_watch_frontend ~/ai_media_watch_frontend
  cd ~/ai_media_watch_frontend && npm install && cd -
  bash scripts/run_fullstack.sh        # backend :8088 + Next :3000 (API base = :8088)
  ```
  Адрес API можно сменить в шапке консоли (localStorage) или через `NEXT_PUBLIC_API_BASE`.
- **Статический `frontend/index.html`** — лёгкий запасной UI без сборки (вкладки: текст,
**ссылка/URL**, аудио, Shadow Graph с визуализацией графа, похожие кейсы).

Ingest по ссылке (`POST /analyze/url`):
- **Видео** (YouTube / Instagram / TikTok / др., через yt-dlp): название + описание + авто-субтитры
  + **OCR превью** (промокод/домен часто только на обложке) — без скачивания видео;
  с `deep:true` дополнительно качает низкокач. копию и OCR-ит кадры (ffmpeg + EasyOCR).
  Guard-ы deep: видео длиннее 10 мин не качаются (OCR кадров пропускается, в ответе `ocr_note`),
  лимит размера ~60 МБ, ≤6 кадров, таймаут ffmpeg — настраиваются в `src/ingest/url_fetcher.py`.
- **HTML-страница / Telegram-пост** (httpx): видимый текст + og-метаданные.

Дальше — общий пайплайн. Только публичные страницы, GET, с таймаутом и лимитом (ТЗ §0).
OCR — EasyOCR на CPU (кириллица+латиница). Instagram/некоторые TikTok могут требовать
cookies → при отказе вернётся понятная ошибка, можно вставить текст вручную.

Запуск всего демо на CPU (Qdrant/Neo4j уже должны быть подняты):

```bash
docker compose -f infra/docker-compose.yml up -d qdrant neo4j   # инфра без vLLM
bash scripts/run_demo.sh                                         # FastAPI :8088 + фронт :8090
# открыть http://localhost:8090   (в поле API вверху — http://localhost:8088)
```

Или по отдельности: `make api-cpu` (бэкенд, LLM off) и `make front` (статик-сервер :8090).
LLM-слой (scenario detection) включается, когда поднят vLLM и `ENABLE_LLM=true`.

## Постоянное хранилище (Postgres)
Каждый вызов `/analyze/*` пишется в Postgres: таблицы `analysis_sessions` (журнал/аудит) и
`analyst_reviews` (ручная проверка, ТЗ §0). Эндпоинты `GET /sessions`, `GET /sessions/{id}`,
`POST /sessions/{id}/review`, `GET /stats`; на фронте — вкладка **«История / Статистика»**.

```bash
docker compose -f infra/docker-compose.yml up -d postgres     # на :5433 (5432 часто занят)
DATABASE_URL=postgresql+asyncpg://finguard:finguard_pass@localhost:5433/finguard \
  uv run alembic upgrade head                                  # накатить миграции
```
Новая схема → `alembic revision --autogenerate -m "..."` → `alembic upgrade head`.
Без БД: `ENABLE_DB=false` (анализ работает, сеансы не пишутся).

## AFM Knowledge Agent (RAG-агент)
Вопрос-ответ по базе знаний АФМ («что делать при подозрительном звонке/сообщении»).
Хранилище — **та же Qdrant**, отдельная коллекция `afm_knowledge` с **гибридным поиском**:
плотный `multilingual-e5` + разрежённый BM25, слияние RRF на сервере Qdrant. Ответ генерирует
vLLM; без LLM — детерминированный fallback из полей карточки. На фронте — вкладка «AFM-агент».

```bash
make index-kb          # залить базу знаний в Qdrant (или само при старте, если коллекция пуста)
curl localhost:8088/agent/status                       # включён ли, сколько карточек, тип поиска
curl -X POST localhost:8088/agent/ask -H 'Content-Type: application/json' \
     -d '{"question":"звонят из банка, просят код из смс — что делать?"}'
```
Флаги: `ENABLE_KB` (по умолч. true), `KB_COLLECTION=afm_knowledge`, `KB_TOP_K`. Эндпоинты — `/agent/{ask,search,reindex,status}`.

## Deepfake-детектор (видео, кейс 9)
Внешний детектор (репо `fakeface-deepfake-detector`, Студент 6) подключён через **изолированный venv**
(их `torch 2.6 / transformers 4.49` конфликтуют с нашими `2.12 / 5.12`), вызывается subprocess'ом:
видео → ViT по лицам (`possible_deepfake`) + Wav2Vec2 по голосу (`synthetic_voice_suspected`) →
`media_anomalies` → risk-сигналы (`+25/+25/+20`). Работает для `POST /analyze/video` и `/analyze/url` c `deep:true`.

```bash
# разовая установка изолированного детектора (~2.5 ГБ torch, в свой venv):
git clone https://github.com/Denryy/fakeface-deepfake-detector external/fakeface-detector
uv venv external/fakeface-detector/.venv --python 3.13
uv pip install --python external/fakeface-detector/.venv/bin/python \
  opencv-python-headless "transformers==4.49.0" "huggingface-hub<1.0" "tokenizers<0.22" \
  imageio-ffmpeg soundfile "torch==2.6.0" "torchvision==0.21.0"
# включить: ENABLE_DEEPFAKE=true (по умолчанию off; см. .env.example)
```
По умолчанию — 1 ViT + Wav2Vec2 (лёгкий профиль рядом с vLLM); полный ансамбль (NPR/DFDC) — опция.

## Команды
- **`make stack-docker`** — весь стек в контейнерах одной командой (qdrant+neo4j+postgres+**api+frontend**; vLLM: `--profile gpu`). api-образ слим (~2.3 ГБ, CPU-torch).
- **`make stack`** — то же на хосте без сборки образов (инфра-контейнеры + backend на venv + Next-фронт) — для dev / забитого диска.
- `make api-cpu` · `make front` — backend без GPU · статический фронт :8090.
- `make test` · `make lint` · `make index` — pytest · ruff · индексация Qdrant.
- ⚠️ Не запускай `make stack` и `make stack-docker` одновременно — оба берут :8088/:3000.

## Безопасность данных (ТЗ §0)
Никаких реальных карт/ИИН/SMS-кодов/CVV/паролей. Реквизиты — только маска или sha256-хэш.
Приватные чаты и утечки не парсим. Вывод — только risk scoring `low/medium/high/critical`.
