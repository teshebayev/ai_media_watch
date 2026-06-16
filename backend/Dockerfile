# Build-контекст — корень репозитория (см. infra/docker-compose.yml: context: ..)
FROM python:3.12-slim

# ffmpeg нужен для извлечения аудио/кадров из видео (Media Service)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Слой зависимостей кешируется отдельно от кода
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/ ./backend/
COPY src/ ./src/

ENV PATH="/app/.venv/bin:$PATH"
CMD ["uv", "run", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
