"""AI Media Watch — end-to-end сервис (контентный продукт).

Реализация продукта = уже построенный backend FakeFace FinGuard (lifespan поднимает
vLLM/Qdrant/Neo4j/Postgres, роутеры `/analyze/*`, `/graph`, `/search`, `/sessions`, `/agent`).
Этот модуль — единая точка входа продукта, параллельная `apps/digital_shadow/app.py`.

Запуск:
    uvicorn apps.media_watch.app:app --port 8088
    # или весь стек в контейнерах:  make stack-docker
"""

from __future__ import annotations

from backend.app.main import app

__all__ = ["app"]
