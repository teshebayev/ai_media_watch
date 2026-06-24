.PHONY: install lock up down logs api test lint index index-kb ask demo stack stack-llm stack-docker media shadow shadow-front shadow-seed shadow-eval shadow-gen shadow-collect shadow-train

# --- Локальная разработка (uv) ---
install:           ## Установить зависимости из lock
	uv sync

lock:              ## Зафиксировать зависимости
	uv lock

api:               ## Запустить backend локально (нужны поднятые qdrant/neo4j/vllm или флаги off)
	uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8088

test:              ## Прогнать тесты
	uv run pytest -q

lint:              ## Линт
	uv run ruff check .

# --- Инфраструктура (docker compose) ---
up:                ## Поднять vllm + qdrant + neo4j + api
	docker compose -f infra/docker-compose.yml up -d

down:              ## Остановить
	docker compose -f infra/docker-compose.yml down

logs:              ## Логи всех сервисов
	docker compose -f infra/docker-compose.yml logs -f

# --- Данные / демо ---
index:             ## Проиндексировать датасет в Qdrant
	uv run python -m src.index_dataset data/processed/ai_media_watch_dataset.jsonl

index-kb:          ## Проиндексировать базу знаний AFM в Qdrant (гибридный поиск dense+sparse)
	QDRANT_URL=http://localhost:6333 uv run python scripts/index_afm_kb.py

ask:               ## Чат с AFM-агентом в терминале (нужны qdrant + vllm; LLM_MODEL переопределяемо)
	QDRANT_URL=http://localhost:6333 LLM_BASE_URL=http://localhost:8100/v1 \
	LLM_MODEL=$${LLM_MODEL:-Qwen/Qwen2.5-7B-Instruct-AWQ} uv run python scripts/ask_afm.py

demo:              ## Запустить Streamlit-демо
	API_URL=http://localhost:8088 uv run streamlit run src/app/streamlit_app.py

front:             ## Поднять статический фронт (frontend/index.html) на :8090
	cd frontend && python3 -m http.server 8090

stack:             ## Одной командой: инфра + миграции + backend(:8088) + Next-фронт(:3000)
	bash scripts/run_fullstack.sh

stack-llm:         ## То же + сам поднимает vLLM и включает LLM (нужен свободный GPU)
	WITH_LLM=true bash scripts/run_fullstack.sh

stack-docker:      ## Всё в контейнерах: docker compose up (api+frontend собираются; нужен диск)
	docker compose -f infra/docker-compose.yml up -d --build
	@echo "Фронт: http://localhost:3000 · API: http://localhost:8088 · (+vLLM: --profile gpu)"

# --- Два продукта на общем движке core (см. docs/two_products.md) ---
media:             ## AI Media Watch end-to-end (:8088) — контентный продукт
	ENABLE_LLM=$${ENABLE_LLM:-false} QDRANT_URL=http://localhost:6333 \
	NEO4J_URI=bolt://localhost:7687 NEO4J_PASSWORD=finguard_pass \
	DATABASE_URL=postgresql+asyncpg://finguard:finguard_pass@localhost:5433/finguard \
	uv run uvicorn apps.media_watch.app:app --host 0.0.0.0 --port 8088

shadow:            ## Digital Shadow end-to-end (:8090) — OSINT/DarkNet, общий граф+БД
	PYTHONPATH=. CUDA_VISIBLE_DEVICES="" ENABLE_GRAPH=true ENABLE_DB=true \
	NEO4J_URI=bolt://localhost:7687 NEO4J_PASSWORD=finguard_pass \
	DATABASE_URL=postgresql+asyncpg://finguard:finguard_pass@localhost:5433/finguard \
	uv run uvicorn apps.digital_shadow.app:app --host 0.0.0.0 --port 8090

shadow-front:      ## Статический фронт Digital Shadow (:8091, ходит в API :8090)
	cd apps/digital_shadow/frontend && python3 -m http.server 8091

shadow-seed:       ## Сгенерировать синтетический seed-датасет → data/shadow/seed.jsonl
	PYTHONPATH=. uv run python -m apps.digital_shadow.seed_data

shadow-eval:       ## Прогнать датасет через пайплайн и оценить (по умолч. seed.jsonl; DATA=path)
	PYTHONPATH=. CUDA_VISIBLE_DEVICES="" uv run python -m apps.digital_shadow.run_batch $(DATA)

shadow-gen:        ## LLM-генерация синтетики через vLLM (:8100) → data/shadow/llm_gen.jsonl (SCALE=0.3)
	PYTHONPATH=. CUDA_VISIBLE_DEVICES="" uv run python -m apps.digital_shadow.gen_llm --scale $(or $(SCALE),1.0)

shadow-collect:    ## Сбор источника → пайплайн → граф+БД (ARGS="--mock" | "--file p.jsonl" | "--rss URL")
	PYTHONPATH=. CUDA_VISIBLE_DEVICES="" ENABLE_GRAPH=true ENABLE_DB=true \
	NEO4J_URI=bolt://localhost:7687 NEO4J_PASSWORD=finguard_pass \
	DATABASE_URL=postgresql+asyncpg://finguard:finguard_pass@localhost:5433/finguard \
	uv run python -m apps.digital_shadow.collect $(or $(ARGS),--mock)

shadow-train:      ## Обучить ML-классификатор категорий (DATA=path, по умолч. all.jsonl)
	PYTHONPATH=. CUDA_VISIBLE_DEVICES="" uv run python -m apps.digital_shadow.train_classifier \
	  --data $(or $(DATA),data/shadow/all.jsonl)

# Бэкенд для фронта без GPU: LLM выключен, Qdrant+Neo4j на localhost.
api-cpu:           ## FastAPI на CPU (LLM off, similarity+graph on)
	ENABLE_LLM=false ENABLE_SIMILARITY=true ENABLE_GRAPH=true \
	CUDA_VISIBLE_DEVICES="" QDRANT_URL=http://localhost:6333 \
	NEO4J_URI=bolt://localhost:7687 NEO4J_PASSWORD=finguard_pass \
	uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8088
