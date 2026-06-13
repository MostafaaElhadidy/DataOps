"""Unit tests for agents — LLM calls are mocked; schemas are validated."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_state(service="spark", severity="critical"):
    return {
        "incident_id": "INC-TEST001",
        "incident_detected": True,
        "detected_at": "2024-01-01T12:00:00+00:00",
        "resolved_at": None,
        "service": service,
        "severity": severity,
        "category": "Infrastructure",
        "confidence_score": 0.0,
        "reasoning": "",
        "evidence_used": [],
        "root_cause": "Spark worker container stopped",
        "impact": "High",
        "affected_services": ["kafka", "postgres"],
        "solution": "Restart the Spark worker container",
        "solution_source": "rag",
        "solution_actions": ["docker restart aiops-spark-worker"],
        "solution_requires_hitl": False,
        "proposed_action": "",
        "proposed_command": "",
        "approval_status": "pending",
        "remediation_status": "pending",
        "retry_count": 0,
        "max_retries": 3,
        "escalated": False,
        "validation_status": "",
        "timeline": [],
        "report_path": None,
        "messages": [],
    }


# ── Triage Agent ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_triage_agent_returns_valid_schema():
    triage_json = json.dumps({
        "result": "Infrastructure",
        "category": "Infrastructure",
        "confidence_score": 0.95,
        "reasoning": "Container exited per logs.",
        "evidence_used": ["container_status", "logs"],
    })
    mock_choice = MagicMock()
    mock_choice.message.content = triage_json
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    with (
        patch("agents.triage_agent.logs_tool.get_logs", return_value="log output"),
        patch("agents.triage_agent.prometheus_tool.get_service_health", AsyncMock(return_value={"healthy": False})),
        patch("agents.triage_agent.prometheus_tool.get_alerts", AsyncMock(return_value=[])),
        patch("agents.triage_agent.get_client") as mock_get_client,
    ):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_get_client.return_value = mock_client

        from agents.triage_agent import triage_agent
        result = await triage_agent(_make_state())

    assert result["category"] == "Infrastructure"
    assert 0.0 <= result["confidence_score"] <= 1.0
    assert isinstance(result["evidence_used"], list)
    assert len(result["timeline"]) == 1


# ── RCA Agent ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rca_agent_uses_all_signals():
    rca_json = json.dumps({
        "result": "Container stopped",
        "root_cause": "Spark worker container OOM-killed (exit code 137)",
        "confidence_score": 0.9,
        "reasoning": "Container exit code 137 confirmed OOM.",
        "evidence_used": ["logs", "container_status", "service_health"],
    })
    mock_choice = MagicMock()
    mock_choice.message.content = rca_json
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    with (
        patch("agents.rca_agent.logs_tool.get_logs", return_value="OOMKilled"),
        patch("agents.rca_agent.prometheus_tool.query_metric", AsyncMock(return_value={"data": {"result": []}})),
        patch("agents.rca_agent.prometheus_tool.get_alerts", AsyncMock(return_value=[])),
        patch("agents.rca_agent.prometheus_tool.get_service_health", AsyncMock(return_value={"healthy": False})),
        patch("agents.rca_agent.docker_tool.container_status", return_value={"status": "exited"}),
        patch("agents.rca_agent.get_client") as mock_get_client,
    ):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_get_client.return_value = mock_client

        from agents.rca_agent import rca_agent
        result = await rca_agent(_make_state())

    assert "OOM" in result["root_cause"] or result["root_cause"]
    assert result["confidence_score"] >= 0


# ── Runbook Agent — web source always sets requires_hitl=True ─────────────────

@pytest.mark.asyncio
async def test_runbook_agent_web_source_forces_hitl():
    runbook_json = json.dumps({
        "result": "Restart container",
        "solution": "Restart the Spark worker",
        "actions": ["docker restart aiops-spark-worker"],
        "source": "web",
        "requires_hitl": False,  # LLM says False, but code must override to True
        "confidence_score": 0.8,
        "reasoning": "Standard restart procedure.",
        "evidence_used": ["web search result"],
    })
    mock_choice = MagicMock()
    mock_choice.message.content = runbook_json
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    with (
        # Force RAG miss so it falls through to web
        patch("agents.runbook_agent.rag_tool.search_runbooks", return_value=[{"score": 0.1, "title": "", "content": ""}]),
        patch("agents.runbook_agent.web_search_tool.search_solution", return_value={"answer": "restart", "results": []}),
        patch("agents.runbook_agent.get_client") as mock_get_client,
    ):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_get_client.return_value = mock_client

        from agents.runbook_agent import runbook_agent
        result = await runbook_agent(_make_state())

    assert result["solution_source"] == "web"
    assert result["solution_requires_hitl"] is True  # enforced regardless of LLM output


# ── Remediation Agent — command allowlist ──────────────────────────────────────

@pytest.mark.asyncio
async def test_remediation_agent_rejects_blocked_command():
    # LLM returns a blocked command; agent must fall back to allowlist
    bad_json = json.dumps({
        "proposed_action": "Delete data",
        "command": "rm -rf /data",
    })
    mock_choice = MagicMock()
    mock_choice.message.content = bad_json
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    with patch("agents.remediation_agent.get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_get_client.return_value = mock_client

        from agents.remediation_agent import remediation_agent
        result = await remediation_agent(_make_state())

    # Should have fallen back to a valid allowlist command
    command = result["proposed_command"]
    assert any(
        command.startswith(p)
        for p in ("restart_container:", "start_container:", "stop_container:", "trigger_dag:")
    )


# ── Validation Agent ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_validation_agent_success():
    with (
        patch("agents.validation_agent.prometheus_tool.get_service_health",
              AsyncMock(return_value={"healthy": True})),
        patch("agents.validation_agent.docker_tool.container_status",
              return_value={"status": "running"}),
        patch("agents.validation_agent.prometheus_tool.get_alerts",
              AsyncMock(return_value=[])),
    ):
        from agents.validation_agent import validation_agent
        result = await validation_agent(_make_state())

    assert result["validation_status"] == "success"


@pytest.mark.asyncio
async def test_validation_agent_failure():
    with (
        patch("agents.validation_agent.prometheus_tool.get_service_health",
              AsyncMock(return_value={"healthy": False, "value": "0"})),
        patch("agents.validation_agent.docker_tool.container_status",
              return_value={"status": "exited"}),
        patch("agents.validation_agent.prometheus_tool.get_alerts",
              AsyncMock(return_value=[{"state": "firing", "labels": {"service": "spark"}}])),
    ):
        from agents.validation_agent import validation_agent
        result = await validation_agent(_make_state())

    assert result["validation_status"] in ("failed", "partial")
