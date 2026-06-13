"""Integration smoke tests for the LangGraph workflow."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_minimal_state(incident_id="INC-SMOKE001"):
    from workflows.incident_graph import make_initial_state
    return make_initial_state(incident_id)


# ── State initialisation ──────────────────────────────────────────────────────

def test_initial_state_defaults():
    from workflows.incident_graph import make_initial_state
    state = make_initial_state("INC-001")
    assert state["incident_id"] == "INC-001"
    assert state["incident_detected"] is False
    assert state["retry_count"] == 0
    assert state["max_retries"] == 3
    assert state["escalated"] is False
    assert state["approval_status"] == "pending"
    assert state["timeline"] == []


# ── Routing functions ─────────────────────────────────────────────────────────

def test_route_monitoring_no_incident():
    from workflows.incident_graph import _route_after_monitoring
    state = _make_minimal_state()
    state["incident_detected"] = False
    assert _route_after_monitoring(state) == "__end__"


def test_route_monitoring_incident():
    from workflows.incident_graph import _route_after_monitoring
    state = _make_minimal_state()
    state["incident_detected"] = True
    assert _route_after_monitoring(state) == "triage"


def test_route_validate_success():
    from workflows.incident_graph import _route_after_validate
    state = _make_minimal_state()
    state["validation_status"] = "success"
    assert _route_after_validate(state) == "postmortem"


def test_route_validate_retry():
    from workflows.incident_graph import _route_after_validate
    state = _make_minimal_state()
    state["validation_status"] = "failed"
    state["retry_count"] = 1
    state["max_retries"] = 3
    assert _route_after_validate(state) == "increment_retry"


def test_route_validate_escalate():
    from workflows.incident_graph import _route_after_validate
    state = _make_minimal_state()
    state["validation_status"] = "failed"
    state["retry_count"] = 3
    state["max_retries"] = 3
    assert _route_after_validate(state) == "escalate"


# ── Graph build ───────────────────────────────────────────────────────────────

def test_build_graph_no_checkpointer():
    from workflows.incident_graph import build_graph
    graph = build_graph(checkpointer=None)
    assert graph is not None


# ── HITL gate — web source ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_remediation_blocked_without_approval():
    from workflows.incident_graph import _execute_remediation
    state = _make_minimal_state()
    state["approval_status"] = "pending"
    state["proposed_command"] = "restart_container:aiops-spark-worker"

    result = await _execute_remediation(state)
    assert result["remediation_status"] == "rejected"


@pytest.mark.asyncio
async def test_execute_remediation_dry_run_approved():
    with patch("workflows.incident_graph.settings") as mock_settings:
        mock_settings.dry_run = True

        with patch("workflows.incident_graph.docker_tool.restart_container",
                   return_value={"status": "skipped"}):
            from workflows.incident_graph import _execute_remediation
            state = _make_minimal_state()
            state["approval_status"] = "approved"
            state["proposed_command"] = "restart_container:aiops-spark-worker"

            result = await _execute_remediation(state)
            # dry_run returns skipped → treated as executed
            assert result["remediation_status"] == "executed"
