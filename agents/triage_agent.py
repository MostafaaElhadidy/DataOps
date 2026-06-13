"""Triage Agent — classifies an incident into a category with confidence."""

import json

from core.llm import get_client, get_model
from core.observability import get_logger, make_timeline_event
from core.schemas import TriageOutput
from core.state import IncidentState
from tools import logs_tool, prometheus_tool

logger = get_logger("triage_agent")

SYSTEM = """You are an expert incident triage engineer for a streaming data platform.

Given evidence about an active incident, classify it into EXACTLY ONE category:
- Infrastructure   : container / host / node failures
- DataQuality      : corrupt, missing, or schema-mismatched data
- Streaming        : Kafka consumer lag, message loss, partition issues
- Database         : PostgreSQL down, connection issues, slow queries
- Orchestration    : Airflow DAG failures, scheduler issues

Respond ONLY as valid JSON (no markdown, no extra text):
{
  "result": "<category>",
  "category": "<same category>",
  "confidence_score": <0.0-1.0>,
  "reasoning": "<one concise paragraph>",
  "evidence_used": ["<signal 1>", "<signal 2>", ...]
}"""


async def triage_agent(state: IncidentState) -> dict:
    incident_id = state["incident_id"]
    service = state.get("service", "unknown")
    log = logger.bind(incident_id=incident_id)

    logs = logs_tool.get_logs(service, tail=100)
    health = await prometheus_tool.get_service_health(service)
    alerts = await prometheus_tool.get_alerts()
    firing = [a for a in alerts if a.get("state") == "firing"]

    user_msg = f"""Incident details:
Service   : {service}
Severity  : {state.get("severity")}
Health    : {json.dumps(health)}
Active alerts ({len(firing)}): {json.dumps(firing[:5], default=str)}

Recent container logs (last 100 lines):
{logs[:3000]}
"""

    client = get_client()
    resp = await client.chat.completions.create(
        model=get_model("triage"),
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    parsed = TriageOutput.model_validate_json(resp.choices[0].message.content)
    event = make_timeline_event(
        "triage_agent",
        "classification",
        f"Category={parsed.category}, Confidence={parsed.confidence_score:.2f}",
    )
    log.info("triage_complete", category=parsed.category, confidence=parsed.confidence_score)

    return {
        "category": parsed.category,
        "confidence_score": parsed.confidence_score,
        "reasoning": parsed.reasoning,
        "evidence_used": parsed.evidence_used,
        "timeline": [event],
    }
