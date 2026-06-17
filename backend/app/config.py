"""Конфигурация через pydantic-settings — все URL/ключи берутся из окружения (.env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8080

    # LLM (vLLM, OpenAI-compatible)
    llm_base_url: str = "http://vllm:8000/v1"
    llm_api_key: str = "dummy"
    llm_model: str = "Qwen/Qwen2.5-7B-Instruct"

    # Qdrant
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "scam_cases"
    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_dim: int = 768

    # Neo4j
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "finguard_pass"

    # Postgres (персистентные сеансы анализа + ручная проверка)
    database_url: str = "postgresql+asyncpg://finguard:finguard_pass@postgres:5432/finguard"
    enable_db: bool = True

    # Фичефлаги — позволяют отключать тяжёлые слои (план «Риски и запасные варианты»)
    enable_similarity: bool = True
    enable_graph: bool = True
    enable_llm: bool = True

    # Deepfake-детектор (внешний репо в своём venv — изоляция от конфликта зависимостей)
    enable_deepfake: bool = False
    deepfake_dir: str = "external/fakeface-detector"
    deepfake_python: str = "external/fakeface-detector/.venv/bin/python"
    deepfake_timeout: int = 120

    # Данные
    data_dir: str = "/app/data"
    dataset_path: str = "/app/data/processed/ai_media_watch_dataset.jsonl"


@lru_cache
def get_settings() -> Settings:
    return Settings()
