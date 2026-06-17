# FakeFace FinGuard + Shadow Graph

Мультимодальная аналитическая система выявления **риск-сигналов мошенничества** в видео,
постах и звонках: реклама онлайн-казино, финансовые пирамиды, фишинг, fake eGov/КНБ-звонки,
deepfake-реклама и связанные цифровые следы.

> Система не выносит юридическое обвинение. Она выявляет риск-сигналы, объясняет причины
> и передаёт материал на ручную проверку аналитика. (ТЗ §0)

Стек: **uv + FastAPI + vLLM + Qdrant + Neo4j + Docker Compose**.
ТЗ — [`fakeface_finguard_student_task.md`](fakeface_finguard_student_task.md),
план инфраструктуры — [`finguard_infra_plan.md`](finguard_infra_plan.md).

## Пайплайн (ТЗ §2)
```
media → combined_text → entities (regex+LLM) → scenario (LLM)
→ similarity (Qdrant) → graph upsert (Neo4j) → risk engine → Analyst Report
```

## Структура
```
backend/app/        FastAPI: api/ (analyze/graph/search/sessions/health), services/ (+ pipeline/ingest/sessions), clients/, schemas/, db/ (SQLAlchemy + Alembic)
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

1. Зависимости (uv, **без pip**):
   ```bash
   uv sync           # по pyproject.toml + uv.lock
   ```
   `uv.lock` ещё не зафиксирован — первый человек делает `uv lock` и коммитит.
   PaddleOCR/paddlepaddle ставятся отдельно (тяжёлые), у того, кто делает OCR.
   Этап 8 (синтетика) подтягивает свои опциональные пакеты у того, кто им занимается:
   `uv add torch silero` (ru TTS), `uv add transformers` (KazNERD); KazakhTTS2/talking-head — отдельно.

2. Окружение:
   ```bash
   cp .env.example .env
   ```

3. Инфраструктура:
   ```bash
   make up           # docker compose: vllm + qdrant + neo4j + api
   ```

### ⚠️ Порт-конфликты на этой машине
- **host:8000 уже занят** сторонним `embeddings-service` (uvicorn). Поэтому vLLM наружу
  отдаётся на `VLLM_HOST_PORT` (по умолчанию **8100**). Внутри docker-сети сервис всё
  равно слушает `8000`, backend ходит на `http://vllm:8000/v1` — клиент менять не нужно.
- Проверьте, что свободны: `6333/6334` (Qdrant), `7474/7687` (Neo4j), `8080` (API).

## Проверки (план, этапы 1–6)
```bash
curl localhost:8100/v1/models     # vLLM (наружный порт)
curl localhost:6333/collections   # Qdrant
# Neo4j Browser: http://localhost:7474
curl localhost:8080/health        # пинг всех сервисов
make test                         # risk engine + regex
```

## Минимальный жизнеспособный срез (без GPU/внешних сервисов)
Текстовый пайплайн (regex + signal_extractor + risk_engine) работает без vLLM/Qdrant/Neo4j —
выставьте флаги `ENABLE_LLM/ENABLE_SIMILARITY/ENABLE_GRAPH=false` и дёргайте `POST /analyze/text`.

## Фронтенд / демо (без GPU)
Статический фронт `frontend/index.html` ходит в FastAPI через `fetch` (вкладки: текст,
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
bash scripts/run_demo.sh                                         # FastAPI :8080 + фронт :8090
# открыть http://localhost:8090   (в поле API вверху — http://localhost:8080)
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
`make api` — backend локально · `make api-cpu` — backend без GPU (LLM off) · `make front` — статик-фронт ·
`make test` · `make lint` · `make index` — индексация в Qdrant · `make demo` — Streamlit.

## Безопасность данных (ТЗ §0)
Никаких реальных карт/ИИН/SMS-кодов/CVV/паролей. Реквизиты — только маска или sha256-хэш.
Приватные чаты и утечки не парсим. Вывод — только risk scoring `low/medium/high/critical`.
