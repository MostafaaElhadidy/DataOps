"""Postmortem Agent — generates a Markdown incident report with MTTR."""

import json
import os
from datetime import UTC, datetime

from core.llm import get_client, get_model
from core.observability import get_logger, make_timeline_event
from core.state import IncidentState

logger = get_logger("postmortem_agent")

REPORTS_DIR = os.getenv("REPORTS_DIR", "reports")


async def postmortem_agent(state: IncidentState) -> dict:
    incident_id = state["incident_id"]
    log = logger.bind(incident_id=incident_id)

    detected_at = state.get("detected_at", "unknown")
    resolved_at = datetime.now(UTC).isoformat()

    # MTTR
    try:
        dt_start = datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
        dt_end = datetime.fromisoformat(resolved_at)
        mttr_minutes = round((dt_end - dt_start).total_seconds() / 60, 2)
    except Exception:
        mttr_minutes = None

    timeline_json = json.dumps(state.get("timeline", []), indent=2, default=str)

    prompt = f"""Write a professional incident postmortem report in Markdown.

Incident ID       : {incident_id}
Detection Time    : {detected_at}
Resolution Time   : {resolved_at}
MTTR              : {mttr_minutes} minutes
Service           : {state.get("service")}
Severity          : {state.get("severity")}
Category          : {state.get("category")}
Root Cause        : {state.get("root_cause")}
Impact            : {state.get("impact")}
Solution Applied  : {state.get("solution")}
Solution Source   : {state.get("solution_source")}
Validation Status : {state.get("validation_status")}
Escalated         : {state.get("escalated", False)}

Confidence Score  : {state.get("confidence_score")}
Reasoning         : {state.get("reasoning", "")[:500]}

Timeline:
{timeline_json[:3000]}

Structure the report with these EXACT sections:
# Incident Report — {incident_id}
## Summary
## Timeline
## Root Cause Analysis
## Impact Assessment
## Resolution
## MTTR
## Lessons Learned
## Recommendations
"""

    client = get_client()
    resp = await client.chat.completions.create(
        model=get_model("postmortem"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    report_md = resp.choices[0].message.content

    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_path = os.path.join(REPORTS_DIR, f"{incident_id}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    event = make_timeline_event(
        "postmortem_agent",
        "report_generated",
        f"Path={report_path}, MTTR={mttr_minutes}min",
    )
    log.info("postmortem_complete", path=report_path, mttr=mttr_minutes)

    return {
        "resolved_at": resolved_at,
        "report_path": report_path,
        "timeline": [event],
    }
