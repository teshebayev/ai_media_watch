.PHONY: install lock up down logs api test lint index demo

# --- Локальная разработка (uv) ---
install:           ## Установить зависимости из lock
	uv sync

lock:              ## Зафиксировать зависимости
	uv lock

api:               ## Запустить backend локально (нужны поднятые qdrant/neo4j/vllm или флаги off)
	uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8080

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

demo:              ## Запустить Streamlit-демо
	API_URL=http://localhost:8080 uv run streamlit run src/app/streamlit_app.py

front:             ## Поднять статический фронт (frontend/index.html) на :8090
	cd frontend && python3 -m http.server 8090

# Бэкенд для фронта без GPU: LLM выключен, Qdrant+Neo4j на localhost.
api-cpu:           ## FastAPI на CPU (LLM off, similarity+graph on)
	ENABLE_LLM=false ENABLE_SIMILARITY=true ENABLE_GRAPH=true \
	CUDA_VISIBLE_DEVICES="" QDRANT_URL=http://localhost:6333 \
	NEO4J_URI=bolt://localhost:7687 NEO4J_PASSWORD=finguard_pass \
	uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8080
