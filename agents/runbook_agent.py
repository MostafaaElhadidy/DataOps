"""Runbook Agent — RAG-first, web-search fallback; web fixes always require HITL."""

import json

from core.llm import get_client, get_model
from core.observability import get_logger, make_timeline_event
from core.schemas import RunbookOutput
from core.state import IncidentState
from tools import rag_tool, web_search_tool

logger = get_logger("runbook_agent")

SYSTEM = """You are a senior SRE providing a step-by-step remediation plan.
Given an incident root cause and knowledge base results, produce a clear, actionable plan.

Respond ONLY as valid JSON (no markdown):
{
  "result": "<one-line solution summary>",
  "solution": "<detailed solution description>",
  "actions": ["<concrete action 1>", "<concrete action 2>", ...],
  "source": "<rag or web>",
  "requires_hitl": <true if source is 'web', always; false only for 'rag'>,
  "confidence_score": <0.0-1.0>,
  "reasoning": "<why this solution addresses the root cause>",
  "evidence_used": ["<runbook title or URL used>", ...]
}"""


async def runbook_agent(state: IncidentState) -> dict:
    incident_id = state["incident_id"]
    service = state.get("service", "unknown")
    root_cause = state.get("root_cause", "")
    log = logger.bind(incident_id=incident_id)

    query = f"{service} {root_cause} {state.get('category', '')}"

    # ── 1. Search internal RAG ─────────────────────────────────────────────
    rag_results = rag_tool.search_runbooks(query, top_k=3)
    rag_hit = rag_results and rag_results[0]["score"] >= 0.50

    if rag_hit:
        source = "rag"
        knowledge = [
            f"[RAG score={r['score']:.2f}] {r['title']}\n{r['content'][:600]}"
            for r in rag_results
        ]
        log.info("runbook_rag_hit", top_score=rag_results[0]["score"])
    else:
        # ── 2. Fallback to web search ──────────────────────────────────────
        source = "web"
        log.info("runbook_rag_miss_web_fallback")
        web = web_search_tool.search_solution(
            f"{service} {root_cause} fix remediation", max_results=5
        )
        knowledge = []
        if web.get("answer"):
            knowledge.append(f"[WEB_ANSWER] {web['answer'][:500]}")
        knowledge += [
            f"[WEB] {r.get('title','')}\n{r.get('content','')[:500]}"
            for r in web.get("results", [])[:3]
        ]

    user_msg = f"""Incident:
Service    : {service}
Root Cause : {root_cause}
Category   : {state.get("category")}
Impact     : {state.get("impact")}

Knowledge base results (source={source}):
{chr(10).join(knowledge)}
"""

    client = get_client()
    resp = await client.chat.completions.create(
        model=get_model("runbook"),
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    parsed = RunbookOutput.model_validate_json(resp.choices[0].message.content)

    # Enforce: web-sourced fixes ALWAYS require HITL, regardless of what the LLM said
    requires_hitl = True if source == "web" else parsed.requires_hitl

    event = make_timeline_event(
        "runbook_agent",
        "solution_found",
        f"Source={source}, HITL={requires_hitl}, Solution={parsed.result[:80]}",
    )
    log.info("runbook_complete", source=source, hitl=requires_hitl, confidence=parsed.confidence_score)

    return {
        "solution": parsed.solution,
        "solution_source": source,
        "solution_actions": parsed.actions,
        "solution_requires_hitl": requires_hitl,
        "confidence_score": parsed.confidence_score,
        "reasoning": parsed.reasoning,
        "evidence_used": parsed.evidence_used,
        "timeline": [event],
    }
