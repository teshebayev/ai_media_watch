#!/usr/bin/env bash
# Поднять vLLM в Docker. Требует установленного nvidia-container-toolkit
# (см. scripts/install_nvidia_toolkit.sh).
#
# По умолчанию — Qwen2.5-7B-Instruct-AWQ (4-bit, ~6 ГБ весов): лучше держит
# казахский/русский, чем 3B, и спокойно влезает в 24 ГБ 4090.
#
# БЮДЖЕТ VRAM ПОД ПОЛНЫЙ ПАЙПЛАЙН (24 ГБ 4090):
#   util=0.5 → vLLM ~12 ГБ (веса 6 + KV-cache). Остаётся ~12 ГБ под deepfake-детектор
#   (CUDA, ~3–5 ГБ). OCR/whisper/NER идут на CPU и VRAM не трогают. vLLM резервирует
#   память ОДИН РАЗ на старте и не отдаёт — поэтому util ставим до запуска.
#   Свободный GPU и нужен максимум контекста/пропускной способности? → VLLM_GPU_UTIL=0.9.
#   max-model-len=4096 хватает для агента и классификации fraud_type (промпты короткие).
#
# Запуск:  bash scripts/run_vllm.sh
set -euo pipefail
cd "$(dirname "$0")/.."

export LLM_MODEL="${LLM_MODEL:-Qwen/Qwen2.5-7B-Instruct-AWQ}"
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
