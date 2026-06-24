#!/usr/bin/env bash
# Поднять backend (FastAPI :8080) + Next-фронт (:3000, репо av1cu/ai_media_watch_frontend).
# Инфра (qdrant/neo4j/postgres) поднимается этим же скриптом (см. ниже).
#
# LLM-слой (vLLM) — опционально:
#   WITH_LLM=true bash scripts/run_fullstack.sh   → скрипт сам поднимет vLLM на :8100
#                                                    и включит ENABLE_LLM (нужен свободный GPU).
#   без WITH_LLM → агент работает на гибридном поиске + fallback из карточек (LLM off).
#
# Запуск:  bash scripts/run_fullstack.sh        (Ctrl+C — остановить оба)
set -euo pipefail
cd "$(dirname "$0")/.."

FRONTEND_DIR="${FRONTEND_DIR:-$HOME/ai_media_watch_frontend}"
[ -d "$FRONTEND_DIR" ] || { echo "Нет фронта в $FRONTEND_DIR — склонируй av1cu/ai_media_watch_frontend"; exit 1; }

export PYTHONPATH=. CUDA_VISIBLE_DEVICES="" TOKENIZERS_PARALLELISM=false
export ENABLE_SIMILARITY=true ENABLE_GRAPH=true
export ENABLE_DB=${ENABLE_DB:-true}
export ENABLE_LLM=${ENABLE_LLM:-false}
export LLM_BASE_URL=${LLM_BASE_URL:-http://localhost:8100/v1}
export LLM_MODEL=${LLM_MODEL:-Qwen/Qwen2.5-7B-Instruct-AWQ}
export QDRANT_URL=${QDRANT_URL:-http://localhost:6333}
export NEO4J_URI=${NEO4J_URI:-bolt://localhost:7687}
export NEO4J_PASSWORD=${NEO4J_PASSWORD:-finguard_pass}
export DATABASE_URL=${DATABASE_URL:-postgresql+asyncpg://finguard:finguard_pass@localhost:5433/finguard}

# 1. Инфра в контейнерах (лёгкая, без сборки тяжёлого api-образа)
echo "→ Поднимаю qdrant / neo4j / postgres…"
docker compose -f infra/docker-compose.yml up -d qdrant neo4j postgres >/dev/null
for i in $(seq 1 30); do
  docker exec infra-postgres-1 pg_isready -U "${POSTGRES_USER:-finguard}" >/dev/null 2>&1 && break; sleep 1
done

# 1b. vLLM (LLM-слой) — только по флагу WITH_LLM=true (требует свободный GPU).
#     run_vllm.sh поднимает контейнер и ждёт готовности на :8100; модель/GPU-util
#     наследуются из LLM_MODEL/VLLM_* (по умолчанию безопасный Qwen2.5-3B).
if [ "${WITH_LLM:-false}" = "true" ]; then
  echo "→ WITH_LLM=true: поднимаю vLLM (LLM_MODEL=$LLM_MODEL)…"
  bash scripts/run_vllm.sh || true
  # Готовность проверяем явно (run_vllm.sh может выйти с 0, даже не дождавшись модели).
  if curl -s -m3 "$LLM_BASE_URL/models" >/dev/null 2>&1; then
    export ENABLE_LLM=true
    echo "✓ vLLM готов → ENABLE_LLM=true (агент отвечает через LLM)"
  else
    echo "⚠ vLLM не отвечает на $LLM_BASE_URL — ENABLE_LLM=$ENABLE_LLM (агент на fallback из карточек)"
  fi
fi

# 2. Миграции Postgres (хост-URL :5433)
DATABASE_URL="${DATABASE_URL/@postgres:5432/@localhost:5433}" .venv/bin/alembic upgrade head 2>/dev/null || true

API_HOST_PORT="${API_HOST_PORT:-8088}"
echo "→ Backend  http://localhost:$API_HOST_PORT  (docs /docs)"
echo "→ Frontend http://localhost:3000  (API base = http://localhost:$API_HOST_PORT)"

# хост-бэкенд ходит в БД по localhost:5433 (наружный порт postgres)
export DATABASE_URL="${DATABASE_URL/@postgres:5432/@localhost:5433}"
.venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port "$API_HOST_PORT" & BE=$!
( cd "$FRONTEND_DIR" && NEXT_PUBLIC_API_BASE="http://localhost:$API_HOST_PORT" npm run dev ) & FE=$!
trap 'kill $BE $FE 2>/dev/null' EXIT INT TERM
wait
