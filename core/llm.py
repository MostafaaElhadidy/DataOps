from openai import AsyncOpenAI
from core.config import settings

_client: AsyncOpenAI | None = None

HEAVY_AGENTS = {"rca", "lineage", "runbook"}


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
    return _client


def get_model(agent_type: str) -> str:
    if agent_type in HEAVY_AGENTS:
        return settings.llm_model_heavy
    return settings.llm_model_standard
