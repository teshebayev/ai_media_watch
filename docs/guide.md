# Гайд: запуск и сервисы

## Запуск инференса

Поднять всю систему (анализ текста/ссылок/аудио/видео) одной командой:

```bash
make stack-docker   # всё в контейнерах (api + frontend собираются образами)
```

Альтернативы:

```bash
make stack          # инфра в docker + backend и фронт на хосте (без GPU)
make stack-llm      # то же + поднимает vLLM и включает LLM (нужен свободный GPU)
```

LLM-слой (scenario detection + ответы AFM-агента) опционален — требует GPU. Поднять отдельно:

```bash
bash scripts/run_vllm.sh                       # util=0.5 (безопасно рядом с другими процессами)
VLLM_GPU_UTIL=0.9 bash scripts/run_vllm.sh     # на свободном GPU
# или через compose:
docker compose -f infra/docker-compose.yml --profile gpu up -d vllm
```

Без vLLM работает всё, кроме LLM scenario detection (risk-скоринг, сигналы, граф, similarity, deepfake, OSINT остаются).

Эндпоинты API: `/analyze/{text,url,audio,video}`, `/graph`, `/search/similar`, `/sessions`, `/stats`, `/agent/*`, `/health`.

Остановить всё:

```bash
docker compose -f infra/docker-compose.yml down
```

---

## Сервисы: куда заходить и учётки

Адреса — с **хоста** (браузер). Внутри docker-сети сервисы зовут друг друга по именам.

| Сервис | Открыть | Логин / доступ |
|---|---|---|
| **Frontend (Next.js)** | http://localhost:3000 · /console | — |
| **API (FastAPI)** | http://localhost:8088/docs | — |
| **AFM-агент (RAG)** | http://localhost:8088/agent/status · UI: /console → «AFM-агент» | — |
| **Neo4j Browser** | http://localhost:7474 (bolt://localhost:7687) | `neo4j` / `finguard_pass` |
| **Qdrant dashboard** | http://localhost:6333/dashboard | — |
| **Adminer (Postgres UI)** | http://localhost:8081 | см. ниже |
| **Postgres (прямое)** | `localhost:5433` | `finguard` / `finguard_pass` / db `finguard` |
| **vLLM (LLM API)** | http://localhost:8100/v1/models | `LLM_API_KEY=dummy` (любой непустой); только при профиле `gpu` |

**Adminer / Postgres** — в форме входа: System `PostgreSQL`, Server `postgres` (уже подставлен), Username `finguard`, Password `finguard_pass`, Database `finguard`.

> ⚠️ Пароли (`finguard_pass`) — dev-дефолты из `.env`. Для прода смени `NEO4J_PASSWORD` / `POSTGRES_PASSWORD`.

Подробнее по каждому сервису (примеры Cypher / SQL, объяснение vLLM) — в [services.md](services.md).
