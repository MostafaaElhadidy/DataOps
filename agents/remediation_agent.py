"""Remediation Agent — proposes an action; execution always requires approval."""

import json

from core.llm import get_client, get_model
from core.observability import get_logger, make_timeline_event
from core.state import IncidentState

logger = get_logger("remediation_agent")

SYSTEM = """You are a remediation planner. Map the proposed solution to a SINGLE executable command.

Available command forms:
  restart_container:<container_name>
  start_container:<container_name>
  stop_container:<container_name>
  trigger_dag:<dag_id>

Container names: aiops-spark-worker, aiops-spark-master, aiops-kafka,
                 aiops-postgres, aiops-airflow-scheduler, aiops-airflow-webserver,
                 aiops-data-generator, aiops-spark-pipeline

Respond ONLY as valid JSON (no markdown):
{
  "proposed_action": "<human-readable description of what will happen>",
  "command": "<exact command form, e.g. restart_container:aiops-spark-worker>"
}"""

ALLOWED_PREFIXES = (
    "restart_container:",
    "start_container:",
    "stop_container:",
    "trigger_dag:",
)


async def remediation_agent(state: IncidentState) -> dict:
    incident_id = state["incident_id"]
    solution_source = state.get("solution_source", "rag")
    log = logger.bind(incident_id=incident_id)

    user_msg = f"""Solution:
{state.get("solution")}

Recommended actions:
{json.dumps(state.get("solution_actions", []))}

Affected service: {state.get("service")}
"""

    client = get_client()
    resp = await client.chat.completions.create(
        model=get_model("remediation"),
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    data = json.loads(resp.choices[0].message.content)
    command: str = data.get("command", "")

    # Hard-enforce allowlist; fall back to restart of the affected service
    if not any(command.startswith(p) for p in ALLOWED_PREFIXES):
        service = state.get("service", "unknown")
        command = f"restart_container:aiops-{service}"
        logger.warning("command_not_in_allowlist_fallback", original=data.get("command"), fallback=command)

    event = make_timeline_event(
        "remediation_agent",
        "action_proposed",
        f"Command={command}, Source={solution_source}, AwaitingApproval=True",
    )
    log.info("remediation_proposed", command=command, source=solution_source)

    return {
        "proposed_action": data.get("proposed_action", ""),
        "proposed_command": command,
        "approval_status": "pending",
        "remediation_status": "pending",
        "timeline": [event],
    }
