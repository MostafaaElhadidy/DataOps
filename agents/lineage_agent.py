"""Lineage Agent — calculates downstream blast radius of an incident."""

import json

from core.llm import get_client, get_model
from core.observability import get_logger, make_timeline_event
from core.schemas import LineageOutput
from core.state import IncidentState
from tools import prometheus_tool

logger = get_logger("lineage_agent")

SYSTEM = """You are a data lineage expert for a streaming data platform.

Pipeline topology (upstream → downstream):
  DataGenerator → Kafka → SparkStreaming → PostgreSQL → AirflowDAGs → Reports

Given a service failure, determine:
  1. Which downstream services are directly impacted
  2. Which datasets or tables are stale/corrupt
  3. Overall blast radius (High / Medium / Low)

Respond ONLY as valid JSON (no markdown):
{
  "result": "<one-line impact summary>",
  "impact": "<detailed description of downstream impact>",
  "affected_services": ["<service1>", ...],
  "affected_datasets": ["<table/dataset1>", ...],
  "confidence_score": <0.0-1.0>,
  "reasoning": "<how you traced the dependency chain>",
  "evidence_used": ["<signal1>", ...]
}"""


async def lineage_agent(state: IncidentState) -> dict:
    incident_id = state["incident_id"]
    service = state.get("service", "unknown")
    log = logger.bind(incident_id=incident_id)

    downstream_health: dict = {}
    for svc in ["kafka", "spark", "postgres", "airflow"]:
        try:
            downstream_health[svc] = await prometheus_tool.get_service_health(svc)
        except Exception as e:
            downstream_health[svc] = {"error": str(e)}

    user_msg = f"""Incident:
Service   : {service}
Root Cause: {state.get("root_cause")}
Severity  : {state.get("severity")}
Category  : {state.get("category")}

Downstream service health snapshots:
{json.dumps(downstream_health, indent=2)}
"""

    client = get_client()
    resp = await client.chat.completions.create(
        model=get_model("lineage"),
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    parsed = LineageOutput.model_validate_json(resp.choices[0].message.content)
    event = make_timeline_event(
        "lineage_agent",
        "impact_assessed",
        f"Impact={parsed.impact[:80]}, AffectedServices={parsed.affected_services}",
    )
    log.info(
        "lineage_complete",
        impact=parsed.impact,
        services=parsed.affected_services,
        confidence=parsed.confidence_score,
    )

    return {
        "impact": parsed.impact,
        "affected_services": parsed.affected_services,
        "evidence_used": parsed.evidence_used,
        "reasoning": parsed.reasoning,
        "confidence_score": parsed.confidence_score,
        "timeline": [event],
    }
