"""Validation Agent — verifies that remediation actually worked."""

from core.observability import get_logger, make_timeline_event
from core.state import IncidentState
from tools import docker_tool, kafka_tool, postgres_tool, prometheus_tool

logger = get_logger("validation_agent")

CONTAINER_MAP = {
    "spark": "aiops-spark-worker",
    "kafka": "aiops-kafka",
    "postgres": "aiops-postgres",
    "airflow": "aiops-airflow-scheduler",
}


async def validation_agent(state: IncidentState) -> dict:
    incident_id = state["incident_id"]
    service = state.get("service", "unknown")
    log = logger.bind(incident_id=incident_id)

    checks_passed: list[str] = []
    checks_failed: list[str] = []

    # ── 1. Prometheus health ───────────────────────────────────────────────
    try:
        h = await prometheus_tool.get_service_health(service)
        if h.get("healthy"):
            checks_passed.append(f"prometheus_up_{service}=1")
        else:
            checks_failed.append(f"prometheus_up_{service}={h.get('value')}")
    except Exception as e:
        checks_failed.append(f"prometheus_check_error: {e}")

    # ── 2. Container running ───────────────────────────────────────────────
    container = CONTAINER_MAP.get(service, f"aiops-{service}")
    status = docker_tool.container_status(container)
    if status["status"] == "running":
        checks_passed.append(f"container_{container}=running")
    else:
        checks_failed.append(f"container_{container}={status['status']}")

    # ── 3. Service-specific checks ─────────────────────────────────────────
    if service == "postgres":
        try:
            pg = await postgres_tool.health_check()
            if pg["healthy"]:
                checks_passed.append("postgres_connectivity=ok")
            else:
                checks_failed.append(f"postgres_connectivity={pg['message']}")
        except Exception as e:
            checks_failed.append(f"postgres_check_error: {e}")

    elif service == "kafka":
        k = kafka_tool.health_check()
        if k["healthy"]:
            checks_passed.append("kafka_connectivity=ok")
        else:
            checks_failed.append(f"kafka_connectivity={k.get('error')}")

    # ── 4. No firing alerts for this service ───────────────────────────────
    try:
        alerts = await prometheus_tool.get_alerts()
        service_alerts = [
            a for a in alerts
            if a.get("state") == "firing"
            and a.get("labels", {}).get("service") == service
        ]
        if not service_alerts:
            checks_passed.append("no_active_alerts_for_service")
        else:
            checks_failed.append(f"still_has_{len(service_alerts)}_firing_alerts")
    except Exception as e:
        checks_failed.append(f"alert_check_error: {e}")

    # ── Determine overall status ───────────────────────────────────────────
    total = len(checks_passed) + len(checks_failed)
    if total == 0 or not checks_passed:
        validation_status = "failed"
    elif not checks_failed:
        validation_status = "success"
    else:
        validation_status = "partial" if len(checks_passed) >= len(checks_failed) else "failed"

    event = make_timeline_event(
        "validation_agent",
        "validation_complete",
        f"Status={validation_status}, Passed={len(checks_passed)}, Failed={len(checks_failed)}",
    )
    log.info(
        "validation_complete",
        status=validation_status,
        passed=checks_passed,
        failed=checks_failed,
    )

    return {"validation_status": validation_status, "timeline": [event]}
