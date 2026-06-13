# Agentic AIOps for Data Pipelines

## Tools, MCP Servers, and Integrations

### Project Goal

Build an Agentic AI platform capable of:

1. Detecting incidents in a data pipeline.
2. Performing automated triage.
3. Identifying root causes.
4. Calculating business impact.
5. Retrieving historical solutions.
6. Executing remediation actions.
7. Validating recovery.
8. Generating postmortem reports.

Pipeline:

```text
Data Source
    ↓
Kafka
    ↓
Spark Streaming
    ↓
PostgreSQL / Delta Lake
    ↓
Airflow
```

Monitoring Stack:

```text
Prometheus
Grafana
OpenTelemetry
```

---

# Agent Architecture

```text
Monitoring Agent
        ↓
Triage Agent
        ↓
RCA Agent
        ↓
Lineage Agent
        ↓
Runbook Agent
        ↓
Remediation Agent
        ↓
Validation Agent
        ↓
Postmortem Agent
```

---

# LLM Layer

Deployment: **Local models served on Lightning AI GPU** (via vLLM
OpenAI-compatible endpoint, or Ollama). One config-driven client; per-agent
model override in `.env`.

Recommended (open-weight, strong tool calling):

* **Heavy reasoning** (RCA, Lineage, Runbook):
  `Qwen2.5-32B-Instruct` / `Qwen3-32B`, or `Llama-3.3-70B-Instruct`
  (AWQ/GPTQ quantized if VRAM-limited).
* **Standard agents** (Monitoring, Triage, Remediation, Validation, Postmortem):
  `Qwen2.5-14B-Instruct` or `Mistral-Small-3.1-24B-Instruct`.
* **Budget single-model fallback**: `Qwen2.5-7B-Instruct`.

Avoid:

* `llama3.1:8b` and other 8B models for the reasoning agents — unreliable
  structured tool calling.

Reason these were chosen:

* Native function/tool calling + reliable JSON
* Long context
* Strong reasoning
* Runs entirely on the Lightning AI GPU (no per-token API cost)

Reliability guard:

* Enforce structured output with Pydantic schemas + retry-on-parse-failure.

---

# RAG System

Purpose:

Store:

* Runbooks
* Historical incidents
* Spark troubleshooting guides
* Kafka troubleshooting guides
* PostgreSQL troubleshooting guides
* Airflow troubleshooting guides
* Internal documentation

Recommended:

## Embedding Model

* BGE-M3

or

* bge-large-en-v1.5

## Vector Database

* Qdrant

Alternative:

* Chroma

---

# Web Search Layer

Purpose:

Allow agents to search for solutions not available in internal documentation.

Examples:

* Spark executor lost
* Kafka consumer lag
* PostgreSQL connection refused
* Airflow scheduler stuck

Recommended:

## Tavily

Best choice for Agentic AI.

Advantages:

* LLM optimized
* Structured results
* Easy integration

Alternative:

* Serper
* Brave Search API

Agent Usage:

```text
RAG Search
      ↓
No Solution Found
      ↓
Web Search
      ↓
Retrieve External Solution
      ↓
Validate
```

---

# Monitoring Agent

Responsibilities:

* Detect anomalies
* Detect failures
* Create incidents

Tools Needed:

## Prometheus Tool

Functions:

* query_prometheus()
* get_metrics()
* get_alerts()

Implementation:

Custom Tool

MCP Required:

No

---

## OpenTelemetry Tool

Functions:

* get_traces()
* get_spans()

Implementation:

Custom Tool

MCP Required:

No

---

## Health Check Tool

Functions:

* check_kafka()
* check_spark()
* check_postgres()
* check_airflow()

Implementation:

Custom Tool

MCP Required:

No

---

# Triage Agent

Responsibilities:

* Categorize incidents

Categories:

* Infrastructure
* Data Quality
* Streaming
* Database
* Orchestration

Tools:

* Prometheus Tool
* Logs Tool
* Health Check Tool

MCP Required:

No

---

# RCA Agent

Responsibilities:

* Determine root cause

Tools:

## Log Retrieval Tool

Functions:

* get_spark_logs()
* get_kafka_logs()
* get_postgres_logs()
* get_airflow_logs()

Implementation:

Custom

MCP Required:

No

---

## Docker Tool

Functions:

* docker_ps()
* docker_inspect()

Implementation:

Docker SDK

MCP Availability:

Existing MCP servers available

Optional

---

# Lineage Agent

Responsibilities:

* Determine impact

Examples:

* Which downstream jobs failed?
* Which datasets became stale?

Tools:

## OpenLineage

Recommended

Functions:

* get_upstream()
* get_downstream()
* get_dependencies()

MCP Availability:

No mature MCP

Build custom integration

Required

---

# Runbook Agent

Responsibilities:

* Retrieve solutions

Sources:

* Internal KB
* Historical incidents
* Vendor documentation
* Stack Overflow summaries
* Official docs

Tools:

## RAG Search

Functions:

* semantic_search()

Implementation:

Qdrant

MCP Required:

No

---

## Web Search

Functions:

* tavily_search()

Implementation:

Tavily API

MCP Availability:

Ready

Recommended

---

# Remediation Agent

Responsibilities:

* Propose recovery action
* Execute **only after human approval** (human-in-the-loop)

Safety (required):

* Agent proposes; LangGraph `interrupt()` pauses for human approve/reject.
* Command validated against an allowlist (restart/start/stop) **in code** before
  execution; delete/rm/drop/truncate/format hard-blocked.
* `dry_run` flag logs without executing.

Examples:

* Restart Spark Worker
* Restart Kafka Consumer
* Restart PostgreSQL
* Trigger Airflow DAG

Tools:

## Docker Tool

Functions:

* restart_container()
* stop_container()
* start_container()

Implementation:

Docker SDK

MCP Availability:

Ready

Recommended

---

## Airflow Tool

Functions:

* trigger_dag()
* pause_dag()
* unpause_dag()

Implementation:

Airflow REST API

MCP Availability:

Limited

Custom integration preferred

---

## PostgreSQL Tool

Functions:

* run_sql()
* check_connections()

Implementation:

psycopg

MCP Availability:

Ready

Optional

---

## Kafka Tool

Functions:

* list_topics()
* get_consumer_lag()
* restart_consumer()

Implementation:

confluent-kafka

MCP Availability:

Ready

Recommended

---

# Validation Agent

Responsibilities:

* Verify remediation worked

Tools:

* Prometheus Tool
* Health Check Tool
* Airflow Tool
* Kafka Tool

MCP Required:

No

---

# Postmortem Agent

Responsibilities:

Generate:

* Timeline
* Root Cause
* Impact
* Resolution
* MTTR
* Recommendations

Tools:

* Incident Database
* Logs
* Metrics
* LLM

MCP Required:

No

---

# MCP Servers We Can Use Immediately

## Kafka MCP

Status:

Ready

Purpose:

* Topic inspection
* Consumer groups
* Message monitoring

Use:

Recommended

---

## PostgreSQL MCP

Status:

Ready

Purpose:

* Query execution
* Database inspection

Use:

Recommended

---

## Filesystem MCP

Status:

Ready

Purpose:

* Read logs
* Read runbooks
* Read incident reports

Use:

Highly Recommended

---

## Docker MCP

Status:

Ready

Purpose:

* Restart services
* Inspect containers

Use:

Highly Recommended

---

## GitHub MCP

Status:

Ready

Purpose:

* Store runbooks
* Store incident history

Use:

Optional

---

# Agent Observability Layer

Purpose:

Trace and debug the multi-agent workflow (essential for a demo + report).

Tools:

* **LangSmith** (recommended) or a local trace store — captures each agent's
  input, tool calls, LLM output, and latency.
* Structured JSON logging correlated by `incident_id`.

Feeds:

* Dashboard "Agent Activity" live execution trace.
* Postmortem timeline + MTTR.

MCP Required:

No

---

# Configuration & Secrets

* `.env` + `pydantic-settings` for all endpoints, model names, API keys,
  detection thresholds.
* Commit `.env.example` only — never real secrets.

---

# Components To Build From Scratch

## Prometheus Integration

Reason:

Need custom metrics queries.

Complexity:

Low

---

## OpenTelemetry Integration

Reason:

Need trace analysis.

Complexity:

Medium

---

## Incident Detection Engine

Reason:

Core project logic.

Complexity:

Medium

---

## RCA Engine

Reason:

Core AI contribution.

Complexity:

High

---

## Lineage Analysis Engine

Reason:

Core AI contribution.

Complexity:

High

---

## Postmortem Generator

Reason:

Core AI contribution.

Complexity:

Low

---

# MVP Scope

For Graduation Project

Implement:

* Kafka
* Spark
* PostgreSQL
* Airflow
* Prometheus
* Grafana

Failure Scenarios:

1. Spark Worker Down
2. PostgreSQL Down
3. Kafka Consumer Lag
4. Schema Drift

Agent Flow:

```text
Failure
    ↓
Monitoring Agent
    ↓
Triage Agent
    ↓
RCA Agent
    ↓
Runbook Agent
    ↓
Remediation Agent
    ↓
Validation Agent
    ↓
Postmortem Agent
```

This scope is achievable while still demonstrating a complete enterprise-grade Agentic AIOps platform.
