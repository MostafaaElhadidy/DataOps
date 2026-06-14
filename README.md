<div align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&height=250&section=header&text=Agentic%20AIOps%20Platform&fontSize=50&animation=fadeIn&fontAlignY=38&desc=Autonomous%20Data%20Pipeline%20Monitoring%20%26%20Recovery&descAlignY=55&descAlign=50" alt="" />
</div>

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-FF4F00.svg?style=for-the-badge&logo=langchain&logoColor=white)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-2496ED.svg?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org/)

## An end-to-end, multi-agent artificial intelligence operations (AIOps) platform designed to autonomously monitor, diagnose, and remediate failures in complex data pipelines.

</div>

---

## 🌟 Overview

The **Agentic AIOps Platform** is a production-grade system that brings autonomous AI agents to your data engineering infrastructure. It monitors data pipelines in real-time, detects anomalies, performs root cause analysis, and executes safe, human-in-the-loop remediations. 

Imagine having an entire site reliability engineering (SRE) team working 24/7 on your data pipelines—that's what this platform provides.

### 🎯 Key Capabilities
1. **Continuous Monitoring:** Ingests metrics from Prometheus and OpenTelemetry.
2. **Automated Triage & RCA:** Classifies incidents and analyzes logs/traces to find the root cause.
3. **Downstream Impact Analysis:** Determines the blast radius of failures (e.g., Spark → Kafka → Postgres).
4. **Intelligent Runbook Retrieval (RAG):** Uses Qdrant vector databases to fetch the correct remediation strategy.
5. **Safe Remediation:** Executes recovery actions (like restarting Docker containers) with strict human-in-the-loop approval gates.
6. **Automated Validation & Postmortem:** Confirms the fix and generates comprehensive markdown incident reports.

---

## 🤖 The Agent Team

This platform leverages **LangGraph** to orchestrate a team of specialized AI agents. They collaborate in a stateful workflow, powered by local LLMs (vLLM / Ollama).

| Agent | Responsibility |
| :--- | :--- |
| 📊 **Monitoring Agent** | Watches Prometheus metrics and detects anomalies/incidents. |
| 🗂️ **Triage Agent** | Classifies the incident by service (Spark, Kafka, Airflow, Postgres, etc.). |
| 🔍 **RCA Agent** | Analyzes logs, metrics, and traces to pinpoint the exact root cause. |
| 🕸️ **Lineage Agent** | Calculates downstream impact and blast radius. |
| 📚 **Runbook Agent** | Retrieves solutions using RAG (Qdrant) or web search (Tavily). |
| 🛠️ **Remediation Agent** | Proposes and executes CLI/API commands to fix the issue (Requires human approval). |
| ✅ **Validation Agent** | Verifies recovery through health checks and metric validation. |
| 📝 **Postmortem Agent** | Compiles a full incident report including MTTR and lessons learned. |

---

## 🏗️ Architecture & Tech Stack

### Data Pipeline Infrastructure
* **Streaming:** Apache Kafka, Apache Spark Streaming
* **Storage/Database:** PostgreSQL
* **Orchestration:** Apache Airflow

### Observability & Vector Store
* **Metrics:** Prometheus, Grafana, OpenTelemetry
* **Vector DB (RAG):** Qdrant (BGE-M3 Embeddings)

### AI & Backend
* **Agent Framework:** LangGraph
* **LLM Serving:** Lightning AI / vLLM / Ollama (Qwen2.5 / Llama-3.3 / Mistral)
* **Backend API:** FastAPI
* **Frontend UI:** React

---

## 🚦 How It Works: The Incident Graph

1. **Pipeline Running Normally** ⬇️
2. **Introduce Failure** (e.g., Spark worker dies) ⬇️
3. **Monitoring Agent Detects** the spike in consumer lag ⬇️
4. **Triage Agent Classifies** it as a Spark Infrastructure Failure ⬇️
5. **RCA Agent Finds Root Cause** in Docker logs ⬇️
6. **Runbook Agent Finds Solution** via Qdrant semantic search ⬇️
7. **Remediation Agent Fixes Issue** (e.g., `docker restart spark-worker`) after Human Approval ⬇️
8. **Validation Agent Confirms Recovery** ⬇️
9. **Postmortem Agent Generates Report** detailing the timeline and MTTR.

---

## 🚀 Getting Started

### Prerequisites
* Docker & Docker Compose
* Python 3.11+
* Local LLM endpoint configured (vLLM/Ollama)

### Installation

1. **Clone the repository:**
```bash
   git clone <repo-url>
   cd project
