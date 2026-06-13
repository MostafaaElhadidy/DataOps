"""FastAPI backend — incident lifecycle, HITL approve/reject, SSE streaming."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, AsyncGenerator

import psycopg
import psycopg.rows
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from core.config import settings
from core.observability import get_logger
from tools import docker_tool, prometheus_tool

logger = get_logger("backend")

# ── In-memory stores ───────────────────────────────────────────────────────────
# incident_id → latest state snapshot
incidents: dict[str, dict] = {}
# incident_id → asyncio.Queue for SSE events
event_queues: dict[str, asyncio.Queue] = {}

_graph = None  # lazy-loaded to avoid import-time DB creation


def get_graph():
    global _graph
    if _graph is None:
        from workflows.incident_graph import get_compiled_graph
        _graph = get_compiled_graph()
    return _graph


# ── Failure simulation helpers ────────────────────────────────────────────────

FAILURE_ACTIONS: dict[str, dict] = {
    "spark_worker": {
        "description": "Stop the Spark worker container",
        "command": "stop_container",
        "target": "aiops-spark-worker",
    },
    "postgres": {
        "description": "Stop the PostgreSQL container",
        "command": "stop_container",
        "target": "aiops-postgres",
    },
    "kafka_lag": {
        "description": "Stop the data generator to induce consumer lag",
        "command": "stop_container",
        "target": "aiops-data-generator",
    },
    "schema_drift": {
        "description": "Add an unexpected column to the events table to simulate schema drift",
        "command": "schema_drift",
        "target": "events",
    },
}


async def _inject_failure(failure_type: str) -> None:
    action = FAILURE_ACTIONS.get(failure_type)
    if not action:
        return
    if action["command"] == "stop_container":
        docker_tool.stop_container(action["target"])
        logger.info("failure_injected", type=failure_type, target=action["target"])
    elif action["command"] == "schema_drift":
        try:
            dsn = (
                f"host={settings.postgres_host} port={settings.postgres_port} "
                f"dbname={settings.postgres_db} user={settings.postgres_user} "
                f"password={settings.postgres_password}"
            )
            async with await psycopg.AsyncConnection.connect(dsn) as conn:
                await conn.execute(
                    "ALTER TABLE events ADD COLUMN IF NOT EXISTS drift_col VARCHAR(50)"
                )
            logger.info("schema_drift_injected")
        except Exception as exc:
            logger.error("schema_drift_failed", error=str(exc))


# ── Workflow runner (runs in background task) ─────────────────────────────────


async def _publish(incident_id: str, event_type: str, data: Any) -> None:
    q = event_queues.get(incident_id)
    if q:
        await q.put({"type": event_type, "data": data})
    # Snapshot latest state
    if incident_id in incidents:
        incidents[incident_id]["last_event"] = {"type": event_type, "data": data}


async def run_incident_workflow(incident_id: str, failure_type: str | None = None) -> None:
    from workflows.incident_graph import make_initial_state

    if failure_type:
        await _inject_failure(failure_type)
        await asyncio.sleep(5)  # let Prometheus pick up the failure

    graph = get_graph()
    state = make_initial_state(incident_id)
    config = {"configurable": {"thread_id": incident_id}}

    incidents[incident_id] = {
        "incident_id": incident_id,
        "status": "running",
        "failure_type": failure_type,
        "created_at": datetime.now(UTC).isoformat(),
        "state": dict(state),
    }
    event_queues[incident_id] = asyncio.Queue()

    await _publish(incident_id, "workflow_started", {"incident_id": incident_id})

    try:
        async for chunk in graph.astream(state, config=config):
            node_name = list(chunk.keys())[0]
            node_output = chunk[node_name]
            # Merge into stored state
            incidents[incident_id]["state"].update(node_output)
            await _publish(incident_id, "node_complete", {
                "node": node_name,
                "output": {k: v for k, v in node_output.items() if k != "timeline"},
                "timestamp": datetime.now(UTC).isoformat(),
            })

        # Check if graph paused (interrupt_before execute_remediation)
        snap = graph.get_state(config)
        if snap and snap.next:
            incidents[incident_id]["status"] = "awaiting_approval"
            proposed = incidents[incident_id]["state"].get("proposed_action", "")
            command = incidents[incident_id]["state"].get("proposed_command", "")
            source = incidents[incident_id]["state"].get("solution_source", "rag")
            await _publish(incident_id, "awaiting_approval", {
                "proposed_action": proposed,
                "proposed_command": command,
                "solution_source": source,
                "message": "Human approval required before executing remediation.",
            })
        else:
            incidents[incident_id]["status"] = "completed"
            await _publish(incident_id, "workflow_complete", {
                "incident_id": incident_id,
                "report_path": incidents[incident_id]["state"].get("report_path"),
            })

    except Exception as exc:
        logger.error("workflow_error", incident_id=incident_id, error=str(exc))
        incidents[incident_id]["status"] = "error"
        incidents[incident_id]["error"] = str(exc)
        await _publish(incident_id, "error", {"message": str(exc)})


async def resume_after_approval(incident_id: str, approved: bool) -> None:
    graph = get_graph()
    config = {"configurable": {"thread_id": incident_id}}

    approval_status = "approved" if approved else "rejected"
    # Update state in the checkpointer so execute_remediation sees it
    graph.update_state(
        config,
        {"approval_status": approval_status},
        as_node="remediation",
    )

    incidents[incident_id]["state"]["approval_status"] = approval_status
    incidents[incident_id]["status"] = "running"
    await _publish(incident_id, "approval_decision", {"decision": approval_status})

    # Resume from the interrupt
    try:
        async for chunk in graph.astream(None, config=config):
            node_name = list(chunk.keys())[0]
            node_output = chunk[node_name]
            incidents[incident_id]["state"].update(node_output)
            await _publish(incident_id, "node_complete", {
                "node": node_name,
                "output": {k: v for k, v in node_output.items() if k != "timeline"},
                "timestamp": datetime.now(UTC).isoformat(),
            })

        incidents[incident_id]["status"] = "completed"
        await _publish(incident_id, "workflow_complete", {
            "incident_id": incident_id,
            "report_path": incidents[incident_id]["state"].get("report_path"),
        })
    except Exception as exc:
        logger.error("resume_error", incident_id=incident_id, error=str(exc))
        incidents[incident_id]["status"] = "error"
        await _publish(incident_id, "error", {"message": str(exc)})


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(title="AIOps Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(UTC).isoformat()}


# ── System health (service status from Prometheus) ─────────────────────────────

@app.get("/system_health")
async def system_health():
    services = ["spark", "kafka", "postgres", "airflow"]
    result = {}
    for svc in services:
        try:
            h = await prometheus_tool.get_service_health(svc)
            result[svc] = "green" if h["healthy"] else "red"
        except Exception:
            result[svc] = "unknown"
    return result


# ── Incidents ──────────────────────────────────────────────────────────────────

@app.get("/incidents")
async def list_incidents():
    return list(incidents.values())


@app.get("/incident/{incident_id}")
async def get_incident(incident_id: str):
    if incident_id not in incidents:
        raise HTTPException(404, f"Incident {incident_id!r} not found")
    return incidents[incident_id]


# ── Failure simulation ─────────────────────────────────────────────────────────

class SimulateRequest(BaseModel):
    failure_type: str  # spark_worker | postgres | kafka_lag | schema_drift


@app.post("/simulate_failure")
async def simulate_failure(req: SimulateRequest, background_tasks: BackgroundTasks):
    if req.failure_type not in FAILURE_ACTIONS:
        raise HTTPException(400, f"Unknown failure_type. Choose: {list(FAILURE_ACTIONS)}")
    incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    background_tasks.add_task(run_incident_workflow, incident_id, req.failure_type)
    return {"incident_id": incident_id, "failure_type": req.failure_type, "status": "started"}


# ── HITL approve / reject ──────────────────────────────────────────────────────

@app.post("/incident/{incident_id}/approve")
async def approve_remediation(incident_id: str, background_tasks: BackgroundTasks):
    if incident_id not in incidents:
        raise HTTPException(404, "Incident not found")
    if incidents[incident_id].get("status") != "awaiting_approval":
        raise HTTPException(400, "Incident is not awaiting approval")
    background_tasks.add_task(resume_after_approval, incident_id, True)
    return {"incident_id": incident_id, "decision": "approved"}


@app.post("/incident/{incident_id}/reject")
async def reject_remediation(incident_id: str, background_tasks: BackgroundTasks):
    if incident_id not in incidents:
        raise HTTPException(404, "Incident not found")
    if incidents[incident_id].get("status") != "awaiting_approval":
        raise HTTPException(400, "Incident is not awaiting approval")
    background_tasks.add_task(resume_after_approval, incident_id, False)
    return {"incident_id": incident_id, "decision": "rejected"}


# ── Reports ────────────────────────────────────────────────────────────────────

@app.get("/report/{incident_id}")
async def get_report(incident_id: str):
    if incident_id not in incidents:
        raise HTTPException(404, "Incident not found")
    report_path = incidents[incident_id]["state"].get("report_path")
    if not report_path or not os.path.exists(report_path):
        raise HTTPException(404, "Report not yet generated")
    with open(report_path, encoding="utf-8") as f:
        return {"incident_id": incident_id, "content": f.read(), "path": report_path}


# ── SSE event stream ───────────────────────────────────────────────────────────

@app.get("/stream/{incident_id}")
async def stream_events(incident_id: str):
    if incident_id not in event_queues:
        raise HTTPException(404, "Incident not found or stream not available")

    async def generator() -> AsyncGenerator[dict, None]:
        q = event_queues[incident_id]
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30.0)
                yield {"data": json.dumps(event)}
                if event.get("type") in ("workflow_complete", "error"):
                    break
            except asyncio.TimeoutError:
                yield {"data": json.dumps({"type": "ping"})}

    return EventSourceResponse(generator())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.backend_host, port=settings.backend_port, reload=False)
