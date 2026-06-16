#!/usr/bin/env bash
# Поднять vLLM в Docker. Требует установленного nvidia-container-toolkit
# (см. scripts/install_nvidia_toolkit.sh).
#
# По умолчанию — БЕЗОПАСНЫЙ малый профиль: Qwen2.5-3B в ~12 ГБ (gpu-util 0.5),
# чтобы влезть рядом с занятым GPU и не уронить чужие процессы по OOM.
# Когда GPU полностью свободен — можно полный 7B: VLLM_GPU_UTIL=0.9 LLM_MODEL=Qwen/Qwen2.5-7B-Instruct.
#
# Запуск:  bash scripts/run_vllm.sh
set -euo pipefail
cd "$(dirname "$0")/.."

export LLM_MODEL="${LLM_MODEL:-Qwen/Qwen2.5-3B-Instruct}"
export VLLM_GPU_UTIL="${VLLM_GPU_UTIL:-0.5}"
export VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-4096}"
export VLLM_HOST_PORT="${VLLM_HOST_PORT:-8100}"
# переиспользуем уже скачанные модели хоста (Qwen качали при GPU-прогоне)
export HF_CACHE="${HF_CACHE:-$HOME/.cache/huggingface}"

echo "vLLM: $LLM_MODEL  util=$VLLM_GPU_UTIL  len=$VLLM_MAX_MODEL_LEN  port=$VLLM_HOST_PORT"
echo "ВНИМАНИЕ: проверь свободную память GPU (nvidia-smi) — util берётся от ПОЛНОГО объёма."
docker compose -f infra/docker-compose.yml up -d vllm

echo "Ждём готовности vLLM…"
for i in $(seq 1 90); do
  if curl -s -m2 "localhost:${VLLM_HOST_PORT}/v1/models" >/dev/null 2>&1; then
    echo "✓ vLLM готов: http://localhost:${VLLM_HOST_PORT}/v1"
    curl -s "localhost:${VLLM_HOST_PORT}/v1/models"; echo
    echo "→ запускай бэкенд с ENABLE_LLM=true LLM_BASE_URL=http://localhost:${VLLM_HOST_PORT}/v1"
    exit 0
  fi
  sleep 4
done
echo "vLLM не ответил за ~6 мин — смотри: docker logs infra-vllm-1"
