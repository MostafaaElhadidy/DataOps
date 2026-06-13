from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ReasoningOutput(BaseModel):
    """Base schema shared by Triage, RCA, Lineage, and Runbook agents."""

    result: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    evidence_used: List[str]


# ── Monitoring ────────────────────────────────────────────────────────────────

class IncidentDetection(BaseModel):
    incident_detected: bool
    service: str = ""
    severity: Literal["low", "medium", "high", "critical"] = "low"
    alert_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    raw_alerts: List[dict] = Field(default_factory=list)


# ── Triage ────────────────────────────────────────────────────────────────────

class TriageOutput(ReasoningOutput):
    category: Literal[
        "Infrastructure", "DataQuality", "Streaming", "Database", "Orchestration"
    ]


# ── RCA ───────────────────────────────────────────────────────────────────────

class RCAOutput(ReasoningOutput):
    root_cause: str


# ── Lineage ───────────────────────────────────────────────────────────────────

class LineageOutput(ReasoningOutput):
    impact: str
    affected_services: List[str]
    affected_datasets: List[str]


# ── Runbook ───────────────────────────────────────────────────────────────────

class RunbookOutput(ReasoningOutput):
    solution: str
    actions: List[str]
    source: Literal["rag", "web"]
    requires_hitl: bool = True

    @model_validator(mode="after")
    def enforce_web_hitl(self) -> "RunbookOutput":
        if self.source == "web":
            self.requires_hitl = True
        return self


# ── Remediation ───────────────────────────────────────────────────────────────

class RemediationProposal(BaseModel):
    proposed_action: str
    command: str
    source: Literal["rag", "web"]
    approval_status: Literal["pending", "approved", "rejected"] = "pending"
    dry_run: bool = False


# ── Validation ────────────────────────────────────────────────────────────────

class ValidationResult(BaseModel):
    validation_status: Literal["success", "failed", "partial"]
    checks_passed: List[str]
    checks_failed: List[str]
    message: str


# ── Postmortem ────────────────────────────────────────────────────────────────

class PostmortemReport(BaseModel):
    incident_id: str
    detection_time: str
    resolution_time: Optional[str] = None
    mttr_minutes: Optional[float] = None
    service: str
    severity: str
    root_cause: str
    impact: str
    resolution: str
    timeline: List[dict]
    lessons_learned: List[str]
    recommendations: List[str]
    escalated: bool = False
    report_path: str
