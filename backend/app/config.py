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

    # AFM Knowledge Agent (RAG-агент по базе знаний AFM stage3)
    # Отдельная Qdrant-коллекция с гибридным поиском: плотный e5 + разрежённый BM25.
    enable_kb: bool = True
    kb_collection: str = "afm_knowledge"
    # Папка с JSONL-карточками и agent_config (см. data/raw/AFM_stage3_json_pack(2)).
    # Относительный путь работает и локально (cwd=репо), и в Docker (WORKDIR=/app, data→/app/data).
    kb_dir: str = "data/raw/AFM_stage3_json_pack(2)"
    kb_cards_file: str = "AFM_stage3_knowledge_cards.jsonl"
    kb_config_file: str = "AFM_stage3_agent_config.json"
    kb_top_k: int = 4  # сколько карточек подмешивать в контекст LLM

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

    # OSINT / репутация доменов (эвристика офлайн всегда; PhishTank — по флагу, сеть)
    enable_osint: bool = True
    enable_phishtank: bool = False
    phishtank_api_key: str = ""

    # Данные
    data_dir: str = "/app/data"
    dataset_path: str = "/app/data/processed/ai_media_watch_dataset.jsonl"

    # ASR (Whisper). large-v3 заметно точнее на kk/ru; на GPU ~3 ГБ float16.
    asr_model_size: str = "large-v3"
    asr_device: str = "auto"        # auto|cuda|cpu
    asr_compute_type: str = "auto"  # auto → float16 на cuda, int8 на cpu
    # Казахский: при детекте kk переключаемся на дообученную модель (transformers).
    asr_kk_enabled: bool = True
    asr_kk_model: str = "shyngys879/kazakh-whisper-large-v3-turbo"


@lru_cache
def get_settings() -> Settings:
    return Settings()
