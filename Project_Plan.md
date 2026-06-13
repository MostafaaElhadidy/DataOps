# IMPLEMENTATION_PLAN.md

# Agentic AIOps Platform for Data Pipelines

## Claude Code Implementation Guide

---

# Project Objective

Build a production-style multi-agent AIOps platform capable of:

1. Monitoring a real data pipeline.
2. Detecting incidents automatically.
3. Performing triage.
4. Determining root causes.
5. Assessing downstream impact.
6. Retrieving remediation strategies.
7. Executing recovery actions.
8. Validating recovery.
9. Generating postmortem reports.

---

# Final Demo Scenario

```text
Pipeline Running Normally
        ↓
Introduce Failure
        ↓
Monitoring Agent Detects
        ↓
Triage Agent Classifies
        ↓
RCA Agent Finds Root Cause
        ↓
Runbook Agent Finds Solution
        ↓
Remediation Agent Fixes Issue
        ↓
Validation Agent Confirms Recovery
        ↓
Postmortem Agent Generates Report
```

---

# Technology Stack

## Pipeline

* Apache Kafka
* Apache Spark Streaming
* PostgreSQL
* Apache Airflow

## Monitoring

* Prometheus
* Grafana
* OpenTelemetry

## Agent Framework

* LangGraph

## LLM (Local — served on Lightning AI GPU)

Served via **vLLM** (OpenAI-compatible endpoint — best throughput for multi-agent
calls) or **Ollama** (simpler). All agents talk to it through one config-driven
client, so models are swappable per agent via `.env`.

Tiered model selection (8B is too weak for reliable tool calling — avoid):

* **Heavy reasoning** (RCA, Lineage, Runbook): `Qwen2.5-32B-Instruct` /
  `Qwen3-32B`, or `Llama-3.3-70B-Instruct` (AWQ/GPTQ quantized if VRAM-limited).
* **Standard agents** (Monitoring, Triage, Remediation, Validation, Postmortem):
  `Qwen2.5-14B-Instruct` or `Mistral-Small-3.1-24B-Instruct`.
* **Budget single-model fallback** (one model for everything):
  `Qwen2.5-7B-Instruct` — far better tool calling than llama3.1:8b.

Hard requirement: the chosen model **must** support native function/tool calling
and reliable JSON output. Enforce structured output with Pydantic schemas +
retry-on-parse-failure.

## RAG

* Qdrant
* BGE-M3 Embeddings

## Backend

* FastAPI

## Frontend

* React

## Containerization

* Docker Compose

---

# Repository Structure

```text
project/
│
├── agents/
│   ├── monitoring_agent.py
│   ├── triage_agent.py
│   ├── rca_agent.py
│   ├── lineage_agent.py
│   ├── runbook_agent.py
│   ├── remediation_agent.py
│   ├── validation_agent.py
│   └── postmortem_agent.py
│
├── tools/
│   ├── prometheus_tool.py
│   ├── logs_tool.py
│   ├── docker_tool.py
│   ├── airflow_tool.py
│   ├── postgres_tool.py
│   ├── kafka_tool.py
│   ├── web_search_tool.py
│   └── rag_tool.py
│
├── workflows/
│   └── incident_graph.py
│
├── core/                  # cross-cutting concerns
│   ├── llm.py             # config-driven LLM client (vLLM/Ollama)
│   ├── state.py           # IncidentState TypedDict
│   ├── config.py          # settings loaded from .env (pydantic-settings)
│   ├── schemas.py         # Pydantic models for structured agent output
│   └── observability.py   # tracing / structured logging
│
├── backend/               # FastAPI app
├── frontend/              # React app
├── vector_db/             # Qdrant data + ingestion scripts
├── runbooks/              # markdown runbooks (RAG source)
├── incidents/            # incident state snapshots (JSON)
├── reports/               # generated postmortems
├── tests/                 # unit + integration tests
├── docker/                # Dockerfiles + compose
├── .env.example           # documented config template (no secrets committed)
└── requirements.txt
```

---

# Phase 0

# Project Setup & Foundations

Estimated Time:
0.5 Day

Goal:

Establish the skeleton so every later phase plugs into a consistent base.

Tasks:

* Init repo, `requirements.txt`, Python 3.11+ venv.
* `core/config.py` — load all settings/secrets from `.env`
  (pydantic-settings). Commit `.env.example` only.
* `core/llm.py` — single client factory pointing at the Lightning AI
  vLLM/Ollama endpoint; per-agent model override.
* `core/schemas.py` — Pydantic models for each agent's structured output.
* `core/observability.py` — structured logging + LangGraph/LangSmith tracing
  hook (or local trace store).
* Decide model-serving: stand up vLLM/Ollama on Lightning AI, confirm a test
  tool-call round-trips.

Success Criteria:

```text
A trivial LangGraph node calls the local LLM,
returns a validated Pydantic object,
and the call appears in the trace log.
```

---

# Phase 1

# Build Infrastructure

Estimated Time:
2-3 Days

Goal:

Create a realistic data pipeline.

---

## Task 1

Create Docker Compose stack.

Services:

* Kafka
* Zookeeper
* Spark Master
* Spark Worker
* PostgreSQL
* Airflow
* Prometheus
* Grafana

Success Criteria:

```text
docker compose up

All services healthy
```

---

## Task 2

Create sample streaming pipeline.

Flow:

```text
Data Generator
      ↓
Kafka
      ↓
Spark Streaming
      ↓
PostgreSQL
```

Success Criteria:

Data continuously appears in PostgreSQL.

---

## Task 3

Integrate monitoring.

Install:

* Prometheus
* Grafana
* OpenTelemetry

Metrics Required:

Kafka:

* consumer lag
* throughput

Spark:

* worker count
* failed jobs

PostgreSQL:

* connections
* availability

Airflow:

* DAG status

Success Criteria:

Metrics visible in Grafana.

---

# Phase 2

# Build Core Tools

Estimated Time:
2 Days

---

## Prometheus Tool

Functions:

```python
query_metric(metric_name)

get_alerts()

get_service_health()
```

---

## Logs Tool

Functions:

```python
get_spark_logs()

get_kafka_logs()

get_postgres_logs()

get_airflow_logs()
```

Implementation:

Use Docker logs.

---

## Docker Tool

Functions:

```python
restart_container()

start_container()

stop_container()

container_status()
```

---

## PostgreSQL Tool

Functions:

```python
execute_query()

health_check()
```

---

## Kafka Tool

Functions:

```python
list_topics()

consumer_lag()

health_check()
```

---

## Airflow Tool

Functions:

```python
trigger_dag()

list_dags()

dag_status()
```

---

## Web Search Tool

Use:

Tavily

Functions:

```python
search_solution()
```

Purpose:

Search external troubleshooting resources.

---

# Phase 3

# Build RAG Layer

Estimated Time:
1 Day

---

## Create Runbook Collection

Create runbooks for:

* Spark Worker Down
* Kafka Consumer Lag
* PostgreSQL Down
* Schema Drift
* Airflow DAG Failure

---

## Build Qdrant Vector Store

Store:

* runbooks
* incident reports
* troubleshooting guides

---

## RAG Tool

Functions:

```python
search_runbooks()

retrieve_similar_incidents()
```

---

# Phase 4

# Build Agent State

Estimated Time:
1 Day

Create LangGraph state.

```python
class IncidentState(TypedDict):

    incident_id: str
    incident_detected: bool
    detected_at: str          # ISO timestamp (for MTTR)
    resolved_at: str          # ISO timestamp (for MTTR)

    service: str
    severity: str
    category: str

    root_cause: str
    impact: str

    remediation_plan: str
    proposed_action: str      # what the agent wants to run
    approval_status: str      # pending | approved | rejected (human-in-the-loop)
    remediation_status: str

    validation_status: str

    retry_count: int          # loop guard for validation→runbook cycle
    max_retries: int          # escalation cap (e.g. 3)
    escalated: bool

    timeline: list            # ordered (timestamp, agent, action) events
    report_path: str
```

Note:
`retry_count` / `max_retries` drive the loop guard (Phase 13).
`approval_status` drives human-in-the-loop remediation (Phase 10).
`timeline` is appended by every agent and feeds the postmortem (Phase 12).
Persist state with a **LangGraph checkpointer** (e.g. SQLite/Postgres saver) so a
run survives the human-approval interrupt and can resume.

---

# Phase 5

# Monitoring Agent

Estimated Time:
1 Day

Responsibilities:

* Monitor metrics
* Detect incidents

Input:

Prometheus metrics

Output:

```json
{
  "incident_detected": true,
  "service": "spark",
  "severity": "high"
}
```

---

# Phase 6

# Triage Agent

Estimated Time:
1 Day

Responsibilities:

Classify incidents.

Categories:

* Spark
* Kafka
* PostgreSQL
* Airflow
* Data Quality

Output:

```json
{
  "category": "Spark Infrastructure Failure"
}
```

---

# Phase 7

# RCA Agent

Estimated Time:
2 Days

Responsibilities:

Find root cause.

Inputs:

* logs
* metrics
* traces

Examples:

```text
Worker lost
Container exited
```

Output:

```json
{
  "root_cause": "Spark worker container stopped"
}
```

---

# Phase 8

# Lineage Agent

Estimated Time:
1 Day

Responsibilities:

Calculate impact.

Example:

```text
Spark Failure

Impacts:

Kafka ingestion
PostgreSQL updates
Airflow DAGs
```

Output:

```json
{
  "impact": "High"
}
```

---

# Phase 9

# Runbook Agent

Estimated Time:
1 Day

Workflow:

```text
Search RAG
     ↓
Not Found
     ↓
Search Web
```

Output:

```json
{
  "solution":
  "restart spark worker"
}
```

---

# Phase 10

# Remediation Agent

Estimated Time:
2 Days

Responsibilities:

Execute recovery.

Examples:

```bash
docker restart spark-worker
```

```bash
docker restart postgres
```

Safety Model — Human-in-the-Loop (required):

```text
Agent proposes action
        ↓
LangGraph interrupt() pauses graph
        ↓
Human approves / rejects (dashboard button or API)
        ↓
Approved → execute    |    Rejected → escalate
```

* Agent never executes directly — it writes `proposed_action` and sets
  `approval_status = pending`, then the graph pauses on `interrupt()`.
* Execution only resumes after `approval_status = approved`.
* The checkpointer persists state across the pause so the run can resume.

Rules (enforced in code, not just prompt):

Allowed allowlist:

* restart
* start
* stop

Blocked (hard-fail before execution):

* delete
* rm
* drop / truncate
* format

* Validate the resolved command against the allowlist **before** calling Docker.
* Support a `dry_run` flag that logs the command without running it.

Output:

```json
{
  "proposed_action": "docker restart spark-worker",
  "approval_status": "approved",
  "remediation_status": "executed"
}
```

---

# Phase 11

# Validation Agent

Estimated Time:
1 Day

Responsibilities:

Verify recovery.

Checks:

* health check
* Prometheus metrics
* database connectivity

Output:

```json
{
  "validation":"success"
}
```

---

# Phase 12

# Postmortem Agent

Estimated Time:
1 Day

Generate report.

Template:

```markdown
# Incident Report

Incident ID:

Detection Time:

Root Cause:

Impact:

Resolution:

MTTR:

Lessons Learned:

Recommendations:
```

Store report in:

```text
reports/
```

---

# Phase 13

# Build LangGraph Workflow

Estimated Time:
1 Day

Graph:

```text
Monitoring
     ↓
Triage
     ↓
RCA
     ↓
Lineage
     ↓
Runbook
     ↓
Remediation
     ↓
Validation
     ↓
Postmortem
```

Conditional Routing (with loop guard):

```text
Validation Passed ──────────────→ Postmortem

Validation Failed
        ↓
retry_count < max_retries ?
   ├── yes → retry_count += 1 → Runbook Agent (try new solution)
   └── no  → escalated = true → Postmortem (logs unresolved + handoff)
```

* Remediation pauses on the human-approval `interrupt()` before each execution.
* The retry counter prevents an infinite Validation→Runbook→Remediation loop.
* On escalation, the postmortem documents what was tried and why it failed.

---

# Phase 14

# Backend API

Estimated Time:
1 Day

Endpoints:

```text
GET /incidents

GET /incident/{id}

POST /simulate_failure

GET /report/{id}
```

---

# Phase 15

# Frontend Dashboard

Estimated Time:
2 Days

Pages:

## System Health

Show:

* Kafka
* Spark
* PostgreSQL
* Airflow

Status:

Green / Yellow / Red

---

## Incidents

Show:

* Active incidents
* Severity
* Root cause

---

## Agent Activity

Show:

```text
Monitoring Agent
RCA Agent
Runbook Agent
Remediation Agent
```

Live execution trace.

---

## Reports

Show generated postmortems.

---

# Phase 16

# Failure Simulation

Estimated Time:
1 Day

Implement buttons.

Failure 1:

```bash
docker stop spark-worker
```

Failure 2:

```bash
docker stop postgres
```

Failure 3:

Kafka consumer lag

Failure 4:

Schema drift

---

# Final Demo

Scenario 1

Spark Worker Failure

Expected Flow:

```text
Stop Spark Worker
      ↓
Monitoring Detects
      ↓
Triage Classifies
      ↓
RCA Finds Cause
      ↓
Runbook Finds Fix
      ↓
Remediation Restarts Worker
      ↓
Validation Confirms Recovery
      ↓
Postmortem Generated
```

---

# Cross-Cutting Concerns

These span all phases — build them in from Phase 0, don't bolt on later.

## Configuration & Secrets

* All endpoints, model names, keys, thresholds in `.env` (never hardcoded).
* `pydantic-settings` validates config at startup. Commit `.env.example` only.

## Agent Observability

* Trace every agent step (input, tool calls, LLM output, latency) via
  LangSmith or a local trace store.
* Structured JSON logs with `incident_id` correlation across all agents.
* The dashboard's "Agent Activity" page reads from this trace stream.

## State Persistence

* LangGraph checkpointer (SQLite for dev, Postgres for the real run) so runs
  survive the human-approval interrupt and can be resumed/replayed.

## Incident Detection Threshold Config

* Detection rules (consumer-lag ceiling, worker-count floor, etc.) live in
  config — tune without code changes. Prometheus alert rules are the trigger.

## Testing Strategy

* Unit tests for every tool (mock Docker/Kafka/Postgres/Prometheus clients).
* Schema tests asserting each agent returns valid Pydantic output.
* One end-to-end integration test per failure scenario:
  inject failure → assert the graph reaches `validation = success`.

---

# MVP Definition

Project is complete when:

✓ Pipeline operational

✓ Monitoring operational

✓ RAG operational

✓ Web Search operational

✓ Multi-agent workflow operational

✓ Human-in-the-loop remediation operational (allowlist + approval gate enforced)

✓ Loop guard / escalation path operational

✓ Agent tracing + structured logs operational

✓ Dashboard operational

✓ Four failure scenarios operational

✓ Postmortem generation operational (with MTTR + timeline)

This is the minimum acceptable graduation-project deliverable.
