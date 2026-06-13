"""Unit tests for tools — all external clients are mocked."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── prometheus_tool ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_alerts_returns_list():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": {"alerts": [{"state": "firing", "labels": {"alertname": "SparkWorkerDown"}}]}
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("tools.prometheus_tool.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        from tools import prometheus_tool
        alerts = await prometheus_tool.get_alerts()

    assert isinstance(alerts, list)
    assert alerts[0]["labels"]["alertname"] == "SparkWorkerDown"


@pytest.mark.asyncio
async def test_get_service_health_healthy():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": {"result": [{"value": ["1234567890", "1"]}]}
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("tools.prometheus_tool.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        from tools import prometheus_tool
        health = await prometheus_tool.get_service_health("spark")

    assert health["healthy"] is True


# ── docker_tool ────────────────────────────────────────────────────────────────

def test_docker_tool_allowlist_accepts_restart():
    from tools.docker_tool import _validate_action
    _validate_action("restart")  # should not raise


def test_docker_tool_allowlist_rejects_delete():
    from tools.docker_tool import _validate_action
    with pytest.raises(ValueError, match="not allowed"):
        _validate_action("delete")


def test_docker_tool_blocked_keyword_rm():
    from tools.docker_tool import _validate_command
    with pytest.raises(ValueError, match="Blocked keyword"):
        _validate_command("rm -rf /data")


def test_restart_container_dry_run():
    from tools.docker_tool import restart_container
    result = restart_container("aiops-spark-worker", dry_run=True)
    assert result["status"] == "skipped"
    assert result["dry_run"] is True


def test_container_status_not_found():
    with patch("tools.docker_tool._client") as mock_docker:
        import docker
        mock_client = MagicMock()
        mock_client.containers.get.side_effect = docker.errors.NotFound("not found")
        mock_docker.return_value = mock_client

        from tools.docker_tool import container_status
        result = container_status("nonexistent")

    assert result["status"] == "not_found"


# ── postgres_tool ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_postgres_health_check_connected():
    with patch("tools.postgres_tool.execute_query", AsyncMock(return_value=[{"alive": 1}])):
        from tools import postgres_tool
        result = await postgres_tool.health_check()
    assert result["healthy"] is True


@pytest.mark.asyncio
async def test_postgres_health_check_failed():
    with patch("tools.postgres_tool.execute_query", AsyncMock(side_effect=Exception("connection refused"))):
        from tools import postgres_tool
        result = await postgres_tool.health_check()
    assert result["healthy"] is False
    assert "connection refused" in result["message"]


# ── kafka_tool ─────────────────────────────────────────────────────────────────

def test_kafka_health_check_error():
    with patch("tools.kafka_tool._admin") as mock_admin:
        mock_admin.side_effect = Exception("broker not available")
        from tools.kafka_tool import health_check
        result = health_check()
    assert result["healthy"] is False


# ── web_search_tool ────────────────────────────────────────────────────────────

def test_web_search_no_api_key():
    with patch("tools.web_search_tool.settings") as mock_settings:
        mock_settings.tavily_api_key = ""
        from tools import web_search_tool
        with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
            web_search_tool.search_solution("test query")
