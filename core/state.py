from __future__ import annotations

import operator
from typing import Annotated, List, Optional, TypedDict


class TimelineEvent(TypedDict):
    timestamp: str
    agent: str
    action: str
    details: str


class IncidentState(TypedDict):
    # ── Identity ──────────────────────────────────────────────────────────────
    incident_id: str

    # ── Detection ─────────────────────────────────────────────────────────────
    incident_detected: bool
    detected_at: str
    resolved_at: Optional[str]

    # ── Classification ────────────────────────────────────────────────────────
    service: str
    severity: str
    category: str

    # ── Reasoning (set by Triage / RCA / Lineage / Runbook) ──────────────────
    confidence_score: float
    reasoning: str
    evidence_used: List[str]

    # ── Root cause & impact ───────────────────────────────────────────────────
    root_cause: str
    impact: str
    affected_services: List[str]

    # ── Solution ──────────────────────────────────────────────────────────────
    solution: str
    solution_source: str       # "rag" | "web"
    solution_actions: List[str]
    solution_requires_hitl: bool

    # ── Remediation ───────────────────────────────────────────────────────────
    proposed_action: str
    proposed_command: str
    approval_status: str       # "pending" | "approved" | "rejected"
    remediation_status: str    # "pending" | "executed" | "failed" | "rejected"

    # ── Control flow ──────────────────────────────────────────────────────────
    retry_count: int
    max_retries: int
    escalated: bool

    # ── Validation ────────────────────────────────────────────────────────────
    validation_status: str     # "success" | "failed" | "partial"

    # ── Output ────────────────────────────────────────────────────────────────
    # Annotated with operator.add so each agent can append without overwriting
    timeline: Annotated[List[TimelineEvent], operator.add]
    report_path: Optional[str]

    # ── LangGraph internal ────────────────────────────────────────────────────
    messages: List[dict]
