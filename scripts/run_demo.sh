#!/usr/bin/env bash
# Поднять демо FakeFace FinGuard без GPU: FastAPI (CPU) + статический фронт.
# Требует поднятых Qdrant/Neo4j:  docker compose -f infra/docker-compose.yml up -d qdrant neo4j
#
# Запуск:  bash scripts/run_demo.sh        (Ctrl+C останавливает оба сервера)
set -euo pipefail
cd "$(dirname "$0")/.."

# LLM включён, если поднят vLLM на :8100 (иначе ENABLE_LLM=false для regex-режима)
export ENABLE_LLM=${ENABLE_LLM:-true} ENABLE_SIMILARITY=true ENABLE_GRAPH=true
export LLM_BASE_URL=${LLM_BASE_URL:-http://localhost:8100/v1}
export LLM_MODEL=${LLM_MODEL:-Qwen/Qwen2.5-3B-Instruct}
export CUDA_VISIBLE_DEVICES=""          # бэкенд сам GPU не трогает (LLM — через vLLM по HTTP)
export QDRANT_URL=${QDRANT_URL:-http://localhost:6333}
export NEO4J_URI=${NEO4J_URI:-bolt://localhost:7687}
export NEO4J_PASSWORD=${NEO4J_PASSWORD:-finguard_pass}
# Postgres (сеансы анализа) — наружу на 5433 (см. docker-compose)
export ENABLE_DB=${ENABLE_DB:-true}
export DATABASE_URL=${DATABASE_URL:-postgresql+asyncpg://finguard:finguard_pass@localhost:5433/finguard}
export TOKENIZERS_PARALLELISM=false

echo "→ FastAPI:  http://localhost:8088  (docs: /docs)"
echo "→ Фронт:    http://localhost:8090"
echo

# бэкенд
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8088 &
API=$!
# статический фронт
python3 -m http.server 8090 --directory frontend &
FRONT=$!

trap 'kill $API $FRONT 2>/dev/null' EXIT INT TERM
wait
