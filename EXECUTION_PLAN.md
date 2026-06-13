# EXECUTION PLAN

## Agentic AIOps Platform for Data Pipelines

A concrete, ordered build plan derived from `Project_Plan.md` and
`Project_Tools.md`. Work top-to-bottom; each milestone has deliverables and an
acceptance gate you must pass before moving on.

---

## Locked Decisions

| Area              | Decision                                                        |
| ----------------- | --------------------------------------------------------------- |
| LLM hosting       | **Local models on Lightning AI GPU** (vLLM or Ollama)           |
| Models            | Qwen2.5-32B/Qwen3-32B (reasoning) · Qwen2.5-14B (standard)       |
| Remediation       | **Human-in-the-loop** — propose → approve → execute             |
| Web-sourced fixes | **Always HITL** — any web-derived action waits for approval, regardless of confidence |
| Safety            | Code-enforced allowlist (restart/start/stop) + dry-run          |
| Reasoning output  | Triage/RCA/Lineage/Runbook return Result + Confidence + Reasoning + Evidence |
| Loop control      | `retry_count` / `max_retries` guard → escalate to postmortem    |
| State             | LangGraph checkpointer (survives approval interrupt)            |
| Config            | `.env` + pydantic-settings; `.env.example` committed            |
| Observability     | LangSmith or local trace store + JSON logs by `incident_id`     |

---

## Critical Path

```text
Foundations (M0)
      ↓
Infrastructure up (M1)  ← everything else depends on this
      ↓
Tools (M2) ──────────────┐
      ↓                   │
RAG layer (M3)            │
      ↓                   ↓
Agents + State (M4–M6) ── needs tools to act on
      ↓
Workflow graph (M7) ← wires agents + HITL + loop guard
      ↓
Backend API (M8) → Frontend (M9) → Failure sim (M10)
      ↓
End-to-end demo + hardening (M11)
```

Highest-risk items (start early, leave buffer): **M1 Docker stack health**,
**M0 LLM serving on Lightning AI**, **M7 graph + interrupt/resume**.

---

## Milestone 0 — Foundations  *(0.5 day)*

Maps to Plan Phase 0.

- [ ] Repo init, Python 3.11+ venv, `requirements.txt`.
- [ ] `core/config.py` (pydantic-settings) + `.env.example`.
- [ ] Stand up model serving on Lightning AI (vLLM OpenAI endpoint or Ollama);
      pull the chosen models.
- [ ] `core/llm.py` — client factory + per-agent model override.
- [ ] `core/schemas.py` — Pydantic output model per agent. Reasoning agents
      (Triage, RCA, Lineage, Runbook) share a base returning:
      `result`, `confidence_score` (0–1), `reasoning`, `evidence_used` (list).
- [ ] `core/observability.py` — JSON logging + trace hook.

**Gate:** a LangGraph test node calls the local LLM, returns a validated Pydantic
object, and the call shows up in the trace log.

---

## Milestone 1 — Infrastructure  *(2–3 days)*

Maps to Plan Phases 1–3.

- [ ] Docker Compose: Kafka, Zookeeper, Spark master+worker, PostgreSQL,
      Airflow, Prometheus, Grafana.
- [ ] Streaming pipeline: Data generator → Kafka → Spark Streaming → PostgreSQL.
- [ ] Prometheus scraping; Grafana dashboards for Kafka lag/throughput, Spark
      workers/failed jobs, Postgres connections, Airflow DAG status.
- [ ] Prometheus **alert rules** = incident trigger source.

**Gate:** `docker compose up` → all services healthy; rows continuously land in
Postgres; metrics + alerts visible in Grafana/Prometheus.

---

## Milestone 2 — Core Tools  *(2 days)*

Maps to Plan Phase 2. Each tool gets a unit test with a mocked client.

- [ ] `prometheus_tool` — query_metric, get_alerts, get_service_health
- [ ] `logs_tool` — spark/kafka/postgres/airflow logs (Docker logs)
- [ ] `docker_tool` — restart/start/stop/status (Docker SDK)
- [ ] `postgres_tool` — execute_query, health_check (psycopg)
- [ ] `kafka_tool` — list_topics, consumer_lag, health_check
- [ ] `airflow_tool` — trigger_dag, list_dags, dag_status (REST API)
- [ ] `web_search_tool` — Tavily search_solution

**Gate:** every tool callable in isolation; unit tests green.

---

## Milestone 3 — RAG Layer  *(1 day)*

Maps to Plan Phase 3.

- [ ] Author runbooks: Spark Worker Down, Kafka Consumer Lag, PostgreSQL Down,
      Schema Drift, Airflow DAG Failure.
- [ ] Qdrant up; ingest runbooks + troubleshooting guides with BGE-M3 embeddings.
- [ ] `rag_tool` — search_runbooks, retrieve_similar_incidents.

**Gate:** a query like "spark worker exited" returns the correct runbook.

---

## Milestone 4 — Agent State  *(0.5 day)*

Maps to Plan Phase 4.

- [ ] `core/state.py` — `IncidentState` (incl. `retry_count`, `max_retries`,
      `approval_status`, `proposed_action`, `timeline`, `detected_at`).
- [ ] Wire LangGraph checkpointer (SQLite dev / Postgres real).

**Gate:** state round-trips through the checkpointer and resumes after a pause.

---

## Milestone 5 — Detection & Triage Agents  *(2 days)*

Maps to Plan Phases 5–6.

- [ ] Monitoring Agent — reads Prometheus/alerts → emits `incident_detected`.
- [ ] Triage Agent — classifies into Infra / Data Quality / Streaming /
      Database / Orchestration. Returns the reasoning schema:
      `result` (category) + `confidence_score` + `reasoning` + `evidence_used`.

**Gate:** injected failure produces a correctly-classified incident object that
includes a confidence score and the evidence behind the classification.

---

## Milestone 6 — Diagnosis Agents  *(4 days)*

Maps to Plan Phases 7–9. All three return the reasoning schema
(`result` + `confidence_score` + `reasoning` + `evidence_used`).

- [ ] RCA Agent — correlates **logs + metrics + traces + health checks + tool
      outputs** (not logs-only) → `root_cause`. `evidence_used` records which
      signals drove the conclusion.
- [ ] Lineage Agent — computes downstream `impact`.
- [ ] Runbook Agent — RAG first, web-search fallback → `solution`. Tag each
      result with its `source` (`rag` | `web`); web-sourced fixes are flagged
      for **mandatory** human approval downstream (M7), regardless of confidence.

**Gate:** for a stopped Spark worker, RCA states the container stopped and cites
the metrics/health/log evidence used; lineage lists affected downstream; runbook
returns the restart fix with its source and confidence.

---

## Milestone 7 — Workflow Graph + Safety  *(2 days)*

Maps to Plan Phases 10–11, 13. **Highest integration risk.**

- [ ] Remediation Agent — proposes action, sets `approval_status=pending`,
      `interrupt()` pauses graph; allowlist + dry-run enforced in code.
- [ ] **Web-sourced gate:** if the chosen fix's `source == web`, force
      `approval_status=pending` and HITL — it can **never** auto-execute,
      regardless of `confidence_score`. Internal/RAG fixes follow the standard
      HITL flow.
- [ ] Validation Agent — health check + metrics + DB connectivity.
- [ ] Wire full graph; conditional routing with loop guard:
      validation fail + `retry_count < max_retries` → Runbook; else escalate.

**Gate:** end-to-end on one scenario — graph pauses for approval, executes on
approve, validates recovery, and the retry cap stops runaway loops. Verify a
web-sourced remediation cannot execute without explicit approval even at high
confidence.

---

## Milestone 8 — Backend API  *(1 day)*

Maps to Plan Phase 14.

- [ ] `GET /incidents`, `GET /incident/{id}`, `POST /simulate_failure`,
      `GET /report/{id}`.
- [ ] `POST /incident/{id}/approve` + `/reject` to resume the HITL interrupt.
- [ ] Stream agent trace events to the frontend (SSE/WebSocket).

**Gate:** full incident lifecycle drivable via API, including approve/reject.

---

## Milestone 9 — Frontend Dashboard  *(2 days)*

Maps to Plan Phase 15.

- [ ] System Health (Kafka/Spark/Postgres/Airflow — green/yellow/red).
- [ ] Incidents (active, severity, root cause).
- [ ] Agent Activity (live execution trace) + **Approve/Reject** button.
- [ ] Reports (rendered postmortems).

**Gate:** operator runs a whole incident from the UI and approves remediation.

---

## Milestone 10 — Failure Simulation + Postmortem  *(1 day)*

Maps to Plan Phases 12, 16.

- [ ] Simulation buttons: stop spark-worker, stop postgres, induce Kafka lag,
      schema drift.
- [ ] Postmortem Agent — timeline, root cause, impact, resolution, **MTTR**,
      lessons, recommendations → `reports/`.

**Gate:** each scenario produces a complete, accurate postmortem.

---

## Milestone 11 — End-to-End Demo & Hardening  *(1–2 days)*

- [ ] Rehearse the Spark Worker Failure demo flow start-to-finish.
- [ ] Integration test per failure scenario (inject → assert recovery).
- [ ] Tune detection thresholds; verify escalation path on an unfixable failure.
- [ ] README + architecture diagram + demo script for the defense.

**Gate:** all MVP Definition checkboxes in `Project_Plan.md` pass.

---

## Risk Register

| Risk                                         | Mitigation                                                  |
| -------------------------------------------- | ----------------------------------------------------------- |
| Local model unreliable tool calling          | Use ≥14B models; Pydantic + retry-on-parse; few-shot prompts |
| Lightning AI GPU/VRAM limits                  | Quantized (AWQ/GPTQ) weights; smaller model for light agents |
| Docker stack flaky on Windows                 | WSL2 backend; healthchecks + restart policies; pin versions  |
| HITL interrupt/resume complexity              | Build M4 checkpointer first; test pause/resume in isolation  |
| Infinite validation→runbook loop              | `max_retries` cap + escalation (built into M7)               |
| Agent actions hard to debug                   | Tracing from M0, not retrofitted                             |

---

## Suggested Sequencing (~3 weeks solo)

```text
Week 1: M0 → M1 → M2
Week 2: M3 → M4 → M5 → M6
Week 3: M7 → M8 → M9 → M10 → M11
```

Parallelizable if multiple people: frontend (M9) can start against mocked API
once M8 contracts are defined; runbook authoring (M3) is independent of agents.
