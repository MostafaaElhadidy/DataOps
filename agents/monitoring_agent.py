"""Monitoring Agent — polls Prometheus alerts and emits incident detections."""

from datetime import UTC, datetime

from core.observability import get_logger, make_timeline_event
from core.state import IncidentState
from tools import prometheus_tool

logger = get_logger("monitoring_agent")

SEVERITY_MAP = {
    "critical": "critical",
    "high": "high",
    "warning": "medium",
    "info": "low",
}


async def monitoring_agent(state: IncidentState) -> dict:
    incident_id = state["incident_id"]
    log = logger.bind(incident_id=incident_id)
    log.info("monitoring_agent_start")

    alerts = await prometheus_tool.get_alerts()
    firing = [a for a in alerts if a.get("state") == "firing"]

    if not firing:
        log.info("no_active_alerts")
        return {
            "incident_detected": False,
            "timeline": [make_timeline_event("monitoring_agent", "scan", "No active alerts found.")],
        }

    # Pick the highest-severity alert
    sev_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    top = max(
        firing,
        key=lambda a: sev_order.get(
            SEVERITY_MAP.get(a.get("labels", {}).get("severity", "info"), "low"), 0
        ),
    )
    labels = top.get("labels", {})
    service = labels.get("service") or labels.get("job", "unknown")
    severity = SEVERITY_MAP.get(labels.get("severity", "info"), "low")
    alert_name = labels.get("alertname", "")

    event = make_timeline_event(
        "monitoring_agent",
        "incident_detected",
        f"Service={service}, Severity={severity}, Alert={alert_name}, FiringCount={len(firing)}",
    )
    log.info("incident_detected", service=service, severity=severity, alert=alert_name)

    return {
        "incident_detected": True,
        "detected_at": datetime.now(UTC).isoformat(),
        "service": service,
        "severity": severity,
        "timeline": [event],
    }
