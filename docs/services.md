# Сервисы: где смотреть данные и как открывать

Все поднимаются `docker compose -f infra/docker-compose.yml up -d` (см. `make stack-docker`).
Адреса — с **хоста** (браузер). Внутри docker-сети сервисы зовут друг друга по именам
(`qdrant`, `neo4j`, `postgres`, `vllm`), наружу проброшены на порты ниже.

> **Пароли/доступы** (значения — из `.env`, дефолт для dev):
> - **Neo4j** — логин `neo4j`, пароль `finguard_pass`
> - **Postgres / Adminer** — пользователь `finguard`, пароль `finguard_pass`, база `finguard`
> - **Qdrant / API / Frontend** — без авторизации
> - **vLLM** — `LLM_API_KEY=dummy` (любой непустой)
>
> ⚠️ Это dev-дефолты. Для прод-развёртывания смени `NEO4J_PASSWORD`/`POSTGRES_PASSWORD` в `.env`.

| Сервис | Открыть в браузере | Логин/доступ | Что внутри |
|---|---|---|---|
| **API (FastAPI)** | http://localhost:8088/docs | — | Swagger: все эндпоинты, можно дёргать вручную |
| **Frontend (Next.js)** | http://localhost:3000 · /console | — | UI аналитика (анализ, граф, История/Статистика, **AFM-агент**) |
| **AFM-агент (RAG)** | http://localhost:8088/agent/status · UI: /console → «AFM-агент» | — | Q&A по базе знаний AFM; гибридный поиск в Qdrant + ответ vLLM |
| **Neo4j Browser** | http://localhost:7474 | `neo4j` / `finguard_pass` (bolt://localhost:7687) | Shadow Graph: узлы/связи, повторяемость |
| **Qdrant dashboard** | http://localhost:6333/dashboard | — | Коллекция `scam_cases`: точки, payload, поиск |
| **Adminer (Postgres UI)** | http://localhost:8081 | см. ниже | Таблицы `analysis_sessions`, `analyst_reviews` |
| **Postgres (прямое)** | `localhost:5433` | `finguard` / `finguard_pass` / db `finguard` | для psql / DBeaver / pgAdmin |
| **vLLM (LLM API)** | http://localhost:8100/v1/models | — | OpenAI-совместимый; **только при профиле `gpu`** (см. ниже) |

---

## Neo4j Browser (http://localhost:7474)
1. Connect URL `bolt://localhost:7687`, логин `neo4j`, пароль `finguard_pass`.
2. Примеры Cypher:
```cypher
MATCH (n) RETURN n LIMIT 50;                                  // что есть
MATCH (d:Domain)<-[:MENTIONS]-(s) WITH d, count(s) AS uses     // повторяемость доменов
  WHERE uses > 1 RETURN d.name, uses ORDER BY uses DESC;
MATCH p=(:Post)-[:MENTIONS]->(:Domain) RETURN p LIMIT 25;      // кластер
```

## Qdrant dashboard (http://localhost:6333/dashboard)
- Collections → `scam_cases` → вкладка **Points** (payload = единый формат §5: label, fraud_type, risk_level…).
- Из консоли: `curl localhost:6333/collections/scam_cases` · `curl localhost:6333/collections`.

## Postgres — через Adminer (http://localhost:8081)
В форме входа:
- **System:** PostgreSQL
- **Server:** `postgres`  (сервер уже подставлен через `ADMINER_DEFAULT_SERVER`)
- **Username:** `finguard` · **Password:** `finguard_pass` · **Database:** `finguard`

Дальше: `analysis_sessions` (журнал каждого `/analyze` + отчёт, сигналы, `media_anomalies`),
`analyst_reviews` (ручная проверка). Можно и SQL:
```sql
SELECT created_at, modality, risk_level, fraud_type, risk_score FROM analysis_sessions ORDER BY created_at DESC LIMIT 20;
SELECT risk_level, count(*) FROM analysis_sessions GROUP BY risk_level;
```
Без UI — через psql:
```bash
docker exec -it infra-postgres-1 psql -U finguard -d finguard -c "\dt"
# или с хоста: psql postgresql://finguard:finguard_pass@localhost:5433/finguard
```

---

## Почему vLLM не запущен и как запустить

**Это нормально — vLLM не стартует по умолчанию специально:**
- он в **профиле `gpu`** docker-compose → обычный `docker compose up -d` его пропускает;
- ему нужна **видеокарта** (+ `nvidia-container-toolkit`), а весь остальной стек работает на CPU;
- он тяжёлый (большой образ + модель в память GPU), держать его постоянно — занимать GPU зря.

Старый контейнер `infra-vllm-1` в статусе `Exited (137)` — это прошлый запуск, убитый по памяти; он не мешает.

**Запустить отдельно, когда нужен LLM-слой** (классификация `fraud_type` моделью + ответы AFM-агента):
```bash
# Qwen2.5-7B-Instruct-AWQ (4-bit), дефолт util=0.5 → vLLM ~12 ГБ, оставляет ~12 ГБ
# под deepfake-детектор (CUDA) при полном пайплайне. OCR/whisper/NER — на CPU.
bash scripts/run_vllm.sh
# свободный GPU и нужен максимум контекста/пропускной способности:
VLLM_GPU_UTIL=0.9 VLLM_MAX_MODEL_LEN=8192 bash scripts/run_vllm.sh
# или через compose-профиль:
docker compose -f infra/docker-compose.yml --profile gpu up -d vllm
# проверить:  curl localhost:8100/v1/models
```
Затем включить LLM в backend: `ENABLE_LLM=true` + `LLM_BASE_URL=http://localhost:8100/v1`
(в docker — это уже зашито на сервис `vllm`; на хосте — переменные окружения).

**Без vLLM работает всё, кроме LLM scenario detection** — risk-скоринг, сигналы, граф,
similarity, deepfake, OSINT остаются (`ENABLE_LLM=false` по умолчанию). AFM-агент тоже
работает: гибридный поиск по карточкам + fallback-ответ из карточки (без генерации LLM).

---

## AFM Knowledge Agent (RAG-агент по базе знаний)

Вопрос-ответ агент по базе знаний AFM (`data/raw/AFM_stage3_json_pack(2)` — что делать
при подозрительных звонках/сообщениях). **Хранилище — та же Qdrant**, отдельная коллекция
`afm_knowledge` с **гибридным поиском**: плотный `multilingual-e5` + разрежённый BM25,
слияние RRF на сервере Qdrant (IDF считает сам Qdrant). Ответ генерирует наш LLM в **vLLM**;
если LLM выключен/недоступен — детерминированный fallback из полей карточки.

**Эндпоинты** (`/agent/*`, см. также Swagger):
```bash
curl localhost:8088/agent/status                                  # включён ли, сколько карточек, тип поиска
curl "localhost:8088/agent/search?q=просят код из смс&limit=4"    # только гибридный поиск (без LLM) — отладка
curl -X POST localhost:8088/agent/ask -H 'Content-Type: application/json' \
     -d '{"question":"звонят из банка и просят код из смс, что делать?"}'
curl -X POST localhost:8088/agent/reindex                          # пересобрать коллекцию из карточек
```
В UI: **http://localhost:3000/console → вкладка «AFM-агент»** (чат + карточки + источники).

**Запуск через Make:**
```bash
make index-kb            # разово залить базу знаний в Qdrant (или само при старте backend, если пусто)
make ask                 # чат с агентом в терминале (нужны qdrant + vllm)
make stack               # инфра + backend + фронт (агент на гибридном поиске + fallback, LLM off)
make stack-llm           # то же + сам поднимает vLLM и включает LLM (нужен свободный GPU)
```

Флаги (`.env` / окружение): `ENABLE_KB` (по умолч. true), `KB_COLLECTION=afm_knowledge`,
`KB_TOP_K=4`, `EMBEDDING_MODEL`. LLM-ответы требуют `ENABLE_LLM=true` + поднятый vLLM.

---

## Шпаргалка
```bash
docker compose -f infra/docker-compose.yml ps        # статус сервисов
docker compose -f infra/docker-compose.yml logs -f api   # логи бэкенда
docker compose -f infra/docker-compose.yml --profile gpu up -d   # + vLLM
docker compose -f infra/docker-compose.yml down      # остановить всё
```
