"""Prometheus query tool — metrics, alerts, and per-service health."""

from typing import Any

import httpx

from core.config import settings
from core.observability import get_logger

logger = get_logger("prometheus_tool")


async def query_metric(promql: str, time: str | None = None) -> dict[str, Any]:
    """Run an instant PromQL query."""
    params: dict[str, str] = {"query": promql}
    if time:
        params["time"] = time
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{settings.prometheus_url}/api/v1/query", params=params)
        resp.raise_for_status()
    return resp.json()


async def get_alerts() -> list[dict]:
    """Return all currently active Prometheus alerts."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{settings.prometheus_url}/api/v1/alerts")
        resp.raise_for_status()
    return resp.json().get("data", {}).get("alerts", [])


async def get_service_health(service: str) -> dict[str, Any]:
    """Query the 'up' metric for a named scrape job."""
    data = await query_metric(f'up{{job="{service}"}}')
    results = data.get("data", {}).get("result", [])
    if not results:
        return {"service": service, "healthy": False, "value": None}
    value = results[0]["value"][1]
    return {"service": service, "healthy": value == "1", "value": value}


async def get_kafka_consumer_lag(topic: str = "pipeline-events") -> dict[str, Any]:
    """Return total consumer lag for a topic across all groups."""
    data = await query_metric(f'sum(kafka_consumer_group_lag{{topic="{topic}"}})')
    results = data.get("data", {}).get("result", [])
    lag = float(results[0]["value"][1]) if results else 0.0
    return {"topic": topic, "total_lag": lag}
