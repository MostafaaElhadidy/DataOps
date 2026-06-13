"""RCA Agent — correlates logs, metrics, traces, health checks, and tool outputs."""

import json

from core.llm import get_client, get_model
from core.observability import get_logger, make_timeline_event
from core.schemas import RCAOutput
from core.state import IncidentState
from tools import docker_tool, kafka_tool, logs_tool, postgres_tool, prometheus_tool

logger = get_logger("rca_agent")

SYSTEM = """You are a senior Site Reliability Engineer performing root cause analysis.

You will receive ALL available evidence signals:
  - Container logs
  - Prometheus metrics and active alerts
  - Service health check results
  - Container status (from Docker)
  - Service-specific tool outputs (Kafka lag, Postgres connectivity, etc.)

Analyse ALL signals to identify the single most likely root cause.
Do NOT rely on any single signal alone.

Respond ONLY as valid JSON (no markdown):
{
  "result": "<concise one-line root cause>",
  "root_cause": "<detailed root cause explanation>",
  "confidence_score": <0.0-1.0>,
  "reasoning": "<chain-of-thought: which signals led to this conclusion and why>",
  "evidence_used": ["<signal that was decisive>", ...]
}"""


async def rca_agent(state: IncidentState) -> dict:
    incident_id = state["incident_id"]
    service = state.get("service", "unknown")
    log = logger.bind(incident_id=incident_id)

    evidence: dict = {}

    # 1. Container logs
    evidence["logs"] = logs_tool.get_logs(service, tail=200)

    # 2. Prometheus: raw metric query
    try:
        evidence["metric_up"] = await prometheus_tool.query_metric(f'up{{job="{service}"}}')
    except Exception as e:
        evidence["metric_up"] = {"error": str(e)}

    # 3. Active alerts
    try:
        alerts = await prometheus_tool.get_alerts()
        evidence["active_alerts"] = [a for a in alerts if a.get("state") == "firing"]
    except Exception as e:
        evidence["active_alerts"] = {"error": str(e)}

    # 4. Service health check
    try:
        evidence["service_health"] = await prometheus_tool.get_service_health(service)
    except Exception as e:
        evidence["service_health"] = {"error": str(e)}

    # 5. Container status (Docker)
    container_map = {
        "spark": "aiops-spark-worker",
        "kafka": "aiops-kafka",
        "postgres": "aiops-postgres",
        "airflow": "aiops-airflow-scheduler",
    }
    container = container_map.get(service, f"aiops-{service}")
    evidence["container_status"] = docker_tool.container_status(container)

    # 6. Service-specific tool outputs
    if service == "postgres":
        try:
            evidence["postgres_health"] = await postgres_tool.health_check()
            evidence["postgres_connections"] = await postgres_tool.get_connection_count()
        except Exception as e:
            evidence["postgres_health"] = {"error": str(e)}
    elif service == "kafka":
        evidence["kafka_health"] = kafka_tool.health_check()
        evidence["kafka_lag"] = kafka_tool.consumer_lag()
    elif service == "spark":
        # Also fetch Spark master logs for context
        evidence["spark_master_logs"] = logs_tool.get_logs("spark-master", tail=50)

    user_msg = f"""Incident:
Service  : {service}
Category : {state.get("category")}
Severity : {state.get("severity")}

Evidence (ALL sources):
{json.dumps(evidence, indent=2, default=str)[:8000]}
"""

    client = get_client()
    resp = await client.chat.completions.create(
        model=get_model("rca"),
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    parsed = RCAOutput.model_validate_json(resp.choices[0].message.content)
    event = make_timeline_event(
        "rca_agent",
        "root_cause_identified",
        f"RootCause={parsed.root_cause[:100]}, Confidence={parsed.confidence_score:.2f}",
    )
    log.info("rca_complete", root_cause=parsed.root_cause, confidence=parsed.confidence_score)

    return {
        "root_cause": parsed.root_cause,
        "confidence_score": parsed.confidence_score,
        "reasoning": parsed.reasoning,
        "evidence_used": parsed.evidence_used,
        "timeline": [event],
    }
