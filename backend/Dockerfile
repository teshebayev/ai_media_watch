# Слим-образ backend. Build-контекст — корень репозитория (см. infra/docker-compose.yml: context: ..)
# Ключевая экономия (чтобы не дублировать ~8 ГБ хост-venv):
#   - CPU-torch (без CUDA-библиотек ~3 ГБ) — backend в контейнере GPU не трогает, LLM идёт в vLLM по HTTP;
#   - только runtime-зависимости (requirements-runtime.txt), без gensim/sklearn/matplotlib/notebook.
FROM python:3.12-slim

# ffmpeg — извлечение аудио/кадров (Media Service); нужен и PyAV для faster-whisper
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_SYSTEM_PYTHON=1 UV_NO_CACHE=1 PYTHONUNBUFFERED=1

# 1) CPU-torch/torchvision с отдельного индекса (иначе transformers/easyocr подтянут CUDA-сборку ~3 ГБ)
RUN uv pip install --system torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 2) Остальные runtime-зависимости (torch уже стоит → не переустанавливается)
COPY backend/requirements-runtime.txt ./
RUN uv pip install --system -r requirements-runtime.txt

COPY backend/ ./backend/
COPY src/ ./src/
COPY alembic.ini ./
ENV PYTHONPATH=/app

# Миграции Postgres → затем API (alembic не валит старт, если БД недоступна)
CMD ["sh", "-c", "alembic upgrade head 2>/dev/null || true; uvicorn backend.app.main:app --host 0.0.0.0 --port 8080"]
