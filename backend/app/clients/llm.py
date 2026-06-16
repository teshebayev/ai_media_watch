"""LLM-клиент: vLLM отдаёт OpenAI-совместимый API, поэтому клиент один."""

from openai import AsyncOpenAI

from backend.app.config import get_settings


def make_llm_client() -> AsyncOpenAI:
    s = get_settings()
    return AsyncOpenAI(base_url=s.llm_base_url, api_key=s.llm_api_key)
