"""Web search tool — Tavily for LLM-optimised external results."""

from tavily import TavilyClient

from core.config import settings
from core.observability import get_logger

logger = get_logger("web_search_tool")


def _client() -> TavilyClient:
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured.")
    return TavilyClient(api_key=settings.tavily_api_key)


def search_solution(query: str, max_results: int = 5) -> dict:
    """Search for a remediation solution. Always marks results as source='web'."""
    logger.info("web_search", query=query)
    results = _client().search(
        query=query, max_results=max_results, search_depth="advanced"
    )
    return {
        "query": query,
        "source": "web",
        "answer": results.get("answer", ""),
        "results": results.get("results", []),
    }
