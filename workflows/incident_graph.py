"""LangGraph incident-response workflow.

Flow:
  monitoring → triage → rca → lineage → runbook → remediation
  → [HITL interrupt_before execute_remediation]
  → execute_remediation → validate
  → success: postmortem
  → fail (retry_count < max_retries): runbook (retry loop)
  → fail (retry_count >= max_retries): escalate → postmortem

Web-sourced fixes: always pending/HITL — graph update_state with
approval_status before resuming.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Literal

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from agents.lineage_agent import lineage_agent
from agents.monitoring_agent import monitoring_agent
from agents.postmortem_agent import postmortem_agent
from agents.rca_agent import rca_agent
from agents.remediation_agent import remediation_agent
from agents.runbook_agent import runbook_agent
from agents.triage_agent import triage_agent
from agents.validation_agent import validation_agent
from core.config import settings
from core.observability import get_logger, make_timeline_event
from core.state import IncidentState
from tools import airflow_tool, docker_tool

logger = get_logger("incident_graph")

CHECKPOINTS_DB = os.path.join(settings.incidents_dir, "checkpoints.db")

# ── Node wrappers ──────────────────────────────────────────────────────────────


async def _monitor(state: IncidentState) -> dict:
    return await monitoring_agent(state)


async def _triage(state: IncidentState) -> dict:
    return await triage_agent(state)


async def _rca(state: IncidentState) -> dict:
    return await rca_agent(state)


async def _lineage(state: IncidentState) -> dict:
    return await lineage_agent(state)


async def _runbook(state: IncidentState) -> dict:
    return await runbook_agent(state)


async def _remediation(state: IncidentState) -> dict:
    """Propose action and set approval_status=pending. Graph pauses here."""
    result = await remediation_agent(state)
    # Web-sourced: always HITL regardless of anything else
    if state.get("solution_source") == "web":
        result["approval_status"] = "pending"
    return result


async def _execute_remediation(state: IncidentState) -> dict:
    """Execute the approved action. Runs only after human approves via API."""
    approval = state.get("approval_status", "pending")
    command: str = state.get("proposed_command", "")
    dry_run = settings.dry_run

    # Safety gate: if somehow reached without approval, abort
    if approval != "approved":
        logger.warning(
            "execute_remediation_blocked",
            incident_id=state["incident_id"],
            approval=approval,
        )
        event = make_timeline_event(
            "execute_remediation",
            "blocked",
            f"Execution blocked — approval_status={approval}",
        )
        return {"remediation_status": "rejected", "timeline": [event]}

    result_status = "failed"
    try:
        if command.startswith("restart_container:"):
            name = command.split(":", 1)[1]
            r = docker_tool.restart_container(name, dry_run=dry_run)
            result_status = "executed" if r["status"] in ("success", "skipped") else "failed"

        elif command.startswith("start_container:"):
            name = command.split(":", 1)[1]
            r = docker_tool.start_container(name, dry_run=dry_run)
            result_status = "executed" if r["status"] in ("success", "skipped") else "failed"

        elif command.startswith("stop_container:"):
            name = command.split(":", 1)[1]
            r = docker_tool.stop_container(name, dry_run=dry_run)
            result_status = "executed" if r["status"] in ("success", "skipped") else "failed"

        elif command.startswith("trigger_dag:"):
            dag_id = command.split(":", 1)[1]
            await airflow_tool.trigger_dag(dag_id)
            result_status = "executed"

        else:
            logger.error("unknown_command", command=command)
            result_status = "failed"

    except Exception as exc:
        logger.error("execute_remediation_error", command=command, error=str(exc))
        result_status = "failed"

    event = make_timeline_event(
        "execute_remediation",
        "executed" if result_status == "executed" else "failed",
        f"Command={command}, DryRun={dry_run}, Status={result_status}",
    )
    return {"remediation_status": result_status, "timeline": [event]}


async def _validate(state: IncidentState) -> dict:
    return await validation_agent(state)


async def _postmortem(state: IncidentState) -> dict:
    return await postmortem_agent(state)


async def _escalate(state: IncidentState) -> dict:
    logger.warning("incident_escalated", incident_id=state["incident_id"])
    event = make_timeline_event(
        "escalation",
        "escalated",
        f"Max retries ({state.get('max_retries')}) reached — manual intervention required.",
    )
    return {"escalated": True, "timeline": [event]}


async def _increment_retry(state: IncidentState) -> dict:
    new_count = state.get("retry_count", 0) + 1
    event = make_timeline_event(
        "retry_loop", "retry", f"Retry {new_count}/{state.get('max_retries')}"
    )
    return {"retry_count": new_count, "timeline": [event]}


# ── Routing functions ──────────────────────────────────────────────────────────


def _route_after_monitoring(state: IncidentState) -> Literal["triage", "__end__"]:
    return "triage" if state.get("incident_detected") else "__end__"


def _route_after_validate(
    state: IncidentState,
) -> Literal["postmortem", "increment_retry", "escalate"]:
    if state.get("validation_status") == "success":
        return "postmortem"
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", settings.max_retries)
    if retry_count < max_retries:
        return "increment_retry"
    return "escalate"


# ── Graph builder ──────────────────────────────────────────────────────────────


def build_graph(checkpointer=None):
    g = StateGraph(IncidentState)

    g.add_node("monitoring", _monitor)
    g.add_node("triage", _triage)
    g.add_node("rca", _rca)
    g.add_node("lineage", _lineage)
    g.add_node("runbook", _runbook)
    g.add_node("remediation", _remediation)
    g.add_node("execute_remediation", _execute_remediation)
    g.add_node("validate", _validate)
    g.add_node("postmortem", _postmortem)
    g.add_node("escalate", _escalate)
    g.add_node("increment_retry", _increment_retry)

    g.set_entry_point("monitoring")

    g.add_conditional_edges(
        "monitoring",
        _route_after_monitoring,
        {"triage": "triage", "__end__": END},
    )
    g.add_edge("triage", "rca")
    g.add_edge("rca", "lineage")
    g.add_edge("lineage", "runbook")
    g.add_edge("runbook", "remediation")
    g.add_edge("remediation", "execute_remediation")
    g.add_edge("execute_remediation", "validate")
    g.add_conditional_edges(
        "validate",
        _route_after_validate,
        {
            "postmortem": "postmortem",
            "increment_retry": "increment_retry",
            "escalate": "escalate",
        },
    )
    g.add_edge("increment_retry", "runbook")
    g.add_edge("escalate", "postmortem")
    g.add_edge("postmortem", END)

    return g.compile(
        checkpointer=checkpointer,
        # Graph pauses BEFORE execute_remediation — human must approve via API
        interrupt_before=["execute_remediation"],
    )


def get_compiled_graph():
    """Return a compiled graph backed by a SQLite checkpointer."""
    os.makedirs(settings.incidents_dir, exist_ok=True)
    conn = sqlite3.connect(CHECKPOINTS_DB, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    return build_graph(checkpointer=checkpointer)


def make_initial_state(incident_id: str) -> IncidentState:
    """Return a zeroed-out IncidentState for a fresh run."""
    return IncidentState(
        incident_id=incident_id,
        incident_detected=False,
        detected_at="",
        resolved_at=None,
        service="",
        severity="",
        category="",
        confidence_score=0.0,
        reasoning="",
        evidence_used=[],
        root_cause="",
        impact="",
        affected_services=[],
        solution="",
        solution_source="rag",
        solution_actions=[],
        solution_requires_hitl=True,
        proposed_action="",
        proposed_command="",
        approval_status="pending",
        remediation_status="pending",
        retry_count=0,
        max_retries=settings.max_retries,
        escalated=False,
        validation_status="",
        timeline=[],
        report_path=None,
        messages=[],
    )
