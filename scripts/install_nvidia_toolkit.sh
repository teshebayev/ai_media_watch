#!/usr/bin/env bash
# Установка nvidia-container-toolkit для доступа docker-контейнеров к GPU (Ubuntu 24.04).
# Нужен ДЛЯ vLLM в Docker. Требует root (sudo) и РЕСТАРТА docker-демона.
#
# Что важно знать перед запуском:
#   - systemctl restart docker остановит контейнеры без restart-policy.
#     На этой машине: infra-qdrant/infra-neo4j (policy=no) → скрипт поднимет их обратно.
#     pronto_sage_* (policy=unless-stopped) → вернутся сами.
#
# Запуск:   bash scripts/install_nvidia_toolkit.sh     (спросит пароль sudo)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Репозиторий NVIDIA Container Toolkit"
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --batch --yes --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null

echo "==> Установка пакета"
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

echo "==> Регистрация nvidia-runtime в docker + рестарт демона"
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

echo "==> Восстанавливаю infra-контейнеры (qdrant/neo4j; policy=no не вернулись сами)"
docker compose -f infra/docker-compose.yml up -d qdrant neo4j

echo "==> Проверка доступа к GPU из контейнера"
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi -L

echo "==> Готово. Дальше можно поднять малый vLLM (см. scripts/run_vllm.sh)."
