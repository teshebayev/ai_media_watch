# FakeFace FinGuard — пошаговый план работы

Рабочий чек-лист. Дополняет [`finguard_infra_plan.md`](finguard_infra_plan.md)
(архитектура и этапы) и ТЗ [`fakeface_finguard_student_task.md`](fakeface_finguard_student_task.md)
(данные и разметка). Отмечай `[x]` по мере выполнения.

> Обновлено: 2026-06-22. Базовый стек работает на **CPU**; **LLM-слой (vLLM) и AFM-агент**
> прогнаны на GPU. Для CPU-запусков моделей рядом с занятым GPU — `CUDA_VISIBLE_DEVICES=""`.

---

## Что уже сделано и проверено

**Каркас и ядро**
- [x] Структура репо: `backend/`, `src/`, `infra/`, `data/`, `docs/`, `tests/`, `frontend/`, `presentation/`, `scripts/`
- [x] FastAPI: роутеры `/analyze/{text,url,audio,video}`, `/graph/{entity,network}`, `/search/similar`, `/health` + CORS
- [x] Детерминированное ядро: regex-экстракторы (§10), signal_extractor (+этапы звонка), risk_engine (§11)
- [x] `pytest` 9/9; byte-compile чистый

**Данные (Этап 8 + сбор)**
- [x] `gen_call_scripts.py` → **160** ru/kk сценариев звонков
- [x] `gen_posts.py` → **81** пост (казино/пирамида/фишинг/крипта + 29 legit/education) — баланс «kk≠scam»
- [x] `tts_batch.py` (Meta **MMS-TTS** ru/kk, CPU) → **160 wav** 16 кГц + авторазметка `synthetic_voice_suspected`
- [x] **Stop-Piramida**: 593 видео транскрибированы Whisper → классификация/NER; + аугментация kk (перевод, LLM-генерация, code-switch)
- [x] `build_dataset.py` → единый **`ai_media_watch_dataset.jsonl`, 834 строки, 0 невалидных** (Pydantic)
- [x] Классификатор `notebooks/fraud_classifier.ipynb`: TF-IDF/Word2Vec/mBERT/e5 × 5 моделей; лучший **e5+LogReg, macro-F1 ≈ 0.82**

**Модели на CPU**
- [x] **Whisper ASR** по 160 звонкам → WER ru 0.29 / kk 0.91 (`docs/asr_kk_findings.md`; kk нужен Soyle)
- [x] **KazNERD** (`yeshpanovrustem/xlm-roberta-large-ner-kazakh`) — `enrich_with_ner`, включён в пайплайн для kk
- [x] **EasyOCR** (кириллица+латиница) — OCR кадров/превью, заменил заглушку PaddleOCR

**Инфраструктура и интеграция**
- [x] **Qdrant + Neo4j** в Docker (без GPU); датасет проиндексирован (**834 точки**), Shadow Graph построен (**834 узла, 875 связей**)
- [x] Интеграция против живых Qdrant/Neo4j (`scripts/itest_services.py`): `analyze_text` → `similar_to_known_scam` + `graph_entity_reuse`
- [x] HTTP-слой + CORS проверены in-process (`scripts/itest_http.py`, TestClient): `/analyze/text`, `/graph/network`, `/search/similar`

**Персистентность (Postgres)**
- [x] Postgres (:5433) + SQLAlchemy async + **Alembic** (миграция 0001): `analysis_sessions` + `analyst_reviews`
- [x] `/analyze/*` пишут сеанс; эндпоинты `/sessions`, `/sessions/{id}`, `/sessions/{id}/review`, `/stats`
- [x] фронт-вкладка «История / Статистика» (список + фильтр + форма ревью + сводка)

**Deepfake / OSINT / фронт / docker**
- [x] Deepfake-детектор (внешний venv) → `media_anomalies` в `/analyze/video`+`url(deep)`; OSINT-репутация доменов
- [x] **AFM Knowledge Agent** (`/agent/*`): RAG поверх Qdrant `afm_knowledge`, гибридный поиск (dense e5 + sparse BM25, RRF) + ответ vLLM/fallback; вкладка «AFM-агент» на фронте
- [x] **Next.js-консоль** (`av1cu/ai_media_watch_frontend`) подключена к API; контракт 1-в-1
- [x] **Один docker-стек** `make stack-docker` (infra+api+frontend), слим api-образ ~2.3 ГБ; `make stack` — хост-режим

**Фронтенд и ingest**
- [x] Статический `frontend/index.html` (без сборки): вкладки Текст / Ссылка / Аудио / Shadow Graph / Похожие / История
- [x] **Граф-визуализация** (vis-network, вендорнут офлайн): `/graph/network` — окрестность сущности + обзор кластеров
- [x] **Ingest по ссылке** `/analyze/url`: YouTube/Instagram/TikTok (yt-dlp: метаданные+субтитры+**OCR превью**) и HTML/Telegram (httpx+текст)
- [x] **Deep-режим** (OCR кадров) с guard-ами: лимит длительности 10 мин, размера ~60 МБ, ≤6 кадров, таймаут ffmpeg

**Осталось — только GPU-зависимое и живой сервер**
- [x] vLLM (LLM-слой: scenario detection + LLM-добор сущностей) — поднят, scenario detection вживую
- [ ] Deepfake-видео (SadTalker/Wav2Lip/LivePortrait) ≥20 + negative-класс · Студент 6 — GPU (детектор уже интегрирован)
- [ ] Whisper-large / быстрый ASR; Soyle для kk-аудио
- [ ] Долгоживущий FastAPI/Next по HTTP (раннер песочницы убивает; в терминале поднимается штатно)
- [ ] 3 демо-сценария «вживую» прогнать на запущенном стеке

---

## Как поднять прямо сейчас (CPU, без GPU)

```bash
docker compose -f infra/docker-compose.yml up -d qdrant neo4j   # инфра без vLLM (уже поднято)
bash scripts/run_demo.sh                                         # FastAPI :8088 + фронт :8090
# открыть http://localhost:8090  (поле API → http://localhost:8088)
```

Воспроизвести данные/проверки:
```bash
CUDA_VISIBLE_DEVICES="" .venv/bin/python -m src.synthetic.gen_call_scripts
CUDA_VISIBLE_DEVICES="" .venv/bin/python -m src.synthetic.gen_posts
CUDA_VISIBLE_DEVICES="" .venv/bin/python -m src.synthetic.tts_batch data/raw/kz_calls/kz_call_scripts.csv
CUDA_VISIBLE_DEVICES="" .venv/bin/python -m src.build_dataset
CUDA_VISIBLE_DEVICES="" QDRANT_URL=http://localhost:6333 .venv/bin/python -m src.index_dataset data/processed/ai_media_watch_dataset.jsonl
NEO4J_URI=bolt://localhost:7687 NEO4J_PASSWORD=finguard_pass .venv/bin/python -m src.graph.build_from_dataset
CUDA_VISIBLE_DEVICES="" .venv/bin/python -m src.media.asr_check          # WER ru/kk
.venv/bin/python -m pytest -q
```

---

## Что делать, когда освободится GPU

### A. LLM-слой — статус и путь к vLLM
- [x] **LLM scenario detection прогнан на GPU** через transformers (Qwen2.5-3B, `scripts/llm_scenario_gpu.py`):
      казино/eGov(ru+kk)/пирамида определяются верно, legit→`legit_finance` (после ужесточения промпта)
- [x] Промпт `scenario.py` ужесточён: только русский, `risk_signals` строго из словаря §9, явная ветка legit
- [x] **vLLM поднят** (`bash scripts/run_vllm.sh` / `docker compose --profile gpu up -d vllm`): scenario detection в `/analyze/*` вживую; модель малая в свободную память, `VLLM_GPU_UTIL=0.9 LLM_MODEL=…7B-Instruct` когда GPU свободен
- [x] `ENABLE_LLM=true LLM_BASE_URL=http://localhost:8100/v1` → `scenario`/`enrich_with_llm` + ответы AFM-агента в пайплайне
- [ ] (альт. без vLLM) локальный transformers-бэкенд LLM — обсуждалось как «опция 2», пока не делаем
- [ ] Правило: **LLM не ставит risk_score**, только сигналы и категорию

### B. Замкнуть медиа-петлю на демо (~1 ч)
- [ ] `/analyze/audio` на ru-звонке (Whisper) и kk (через Soyle-адаптер, если подключишь)
- [ ] `/analyze/video` на казино-ролике: ffmpeg → ASR + **OCR кадров** (EasyOCR) → отчёт
- [ ] `/analyze/url` с `deep:true` на реальном казино-видео (промокод на экране)

### C. Deepfake-датасет (Студент 6, ~2 ч)
- [ ] SadTalker/Wav2Lip/LivePortrait → ≥20 talking-head + negative-класс реальных тиммейтов
- [ ] авторазметка `possible_deepfake: true`, `case_type: deepfake_financial_promo`
- [ ] добавить в датасет, перепроиндексировать Qdrant (`make index`)

### D. Финальное демо (~2 ч)
- [ ] 3 сценария ТЗ §18: gambling-видео, eGov-звонок, deepfake promo — вживую на стеке
- [ ] Обновить цифры/скрины в `presentation/index.html`
- [ ] Проверить `docker compose up` поднимает всё одной командой

---

## Карта владельцев (ТЗ §13)

| Зона | Кто | Статус |
|---|---|---|
| ASR/OCR | Студент 4 | ✅ Whisper + EasyOCR на CPU |
| entity + risk | Студент 7 | ✅ regex + signals + risk_engine |
| Shadow Graph + UI | Студент 8 | ✅ Neo4j + граф-виз + фронт |
| KZ calls | Студент 5 | ✅ 160 синтетических звонков |
| FakeFace | Студент 6 | ⏳ deepfake-видео (нужен GPU) |
| ready datasets | Студент 3 | ⏳ нормализатор готов, данные не залиты |
| YouTube / Telegram | Студенты 1–2 | ⏳ парсеры готовы, реальный сбор не делали |

## Принципы (не нарушать)

- Безопасность данных ТЗ §0: только маска/хэш реквизитов, никаких приватных чатов и утечек.
- LLM не ставит risk_score — скоринг детерминированный (`src/risk/risk_engine.py`).
- Любой тяжёлый слой за фичефлагом: система работает минимальным срезом без GPU.
- Зависимости только через `uv add` / `uv sync`. Запуск моделей — с `CUDA_VISIBLE_DEVICES=""`, пока GPU занят.
