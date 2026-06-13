"""Airflow tool — DAG inspection and triggering via the REST API."""

import base64

import httpx

from core.config import settings
from core.observability import get_logger

logger = get_logger("airflow_tool")


def _headers() -> dict[str, str]:
    creds = base64.b64encode(
        f"{settings.airflow_user}:{settings.airflow_password}".encode()
    ).decode()
    return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}


def _base() -> str:
    return f"{settings.airflow_base_url}/api/v1"


async def list_dags() -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as c:
        resp = await c.get(f"{_base()}/dags", headers=_headers())
        resp.raise_for_status()
    return resp.json().get("dags", [])


async def dag_status(dag_id: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as c:
        resp = await c.get(f"{_base()}/dags/{dag_id}", headers=_headers())
    if resp.status_code == 404:
        return {"dag_id": dag_id, "found": False}
    resp.raise_for_status()
    dag = resp.json()

    async with httpx.AsyncClient(timeout=10.0) as c:
        runs_resp = await c.get(
            f"{_base()}/dags/{dag_id}/dagRuns",
            params={"limit": 1, "order_by": "-execution_date"},
            headers=_headers(),
        )
    runs = runs_resp.json().get("dag_runs", []) if runs_resp.is_success else []
    latest = runs[0] if runs else {}
    return {
        "dag_id": dag_id,
        "found": True,
        "is_paused": dag.get("is_paused"),
        "latest_state": latest.get("state"),
        "latest_run_id": latest.get("dag_run_id"),
    }


async def trigger_dag(dag_id: str, conf: dict | None = None) -> dict:
    payload = {"conf": conf or {}}
    async with httpx.AsyncClient(timeout=10.0) as c:
        resp = await c.post(
            f"{_base()}/dags/{dag_id}/dagRuns",
            json=payload,
            headers=_headers(),
        )
        resp.raise_for_status()
    return resp.json()


async def pause_dag(dag_id: str) -> dict:
    return await _set_paused(dag_id, paused=True)


async def unpause_dag(dag_id: str) -> dict:
    return await _set_paused(dag_id, paused=False)


async def _set_paused(dag_id: str, paused: bool) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as c:
        resp = await c.patch(
            f"{_base()}/dags/{dag_id}",
            json={"is_paused": paused},
            headers=_headers(),
        )
        resp.raise_for_status()
    return resp.json()
