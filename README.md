# 🤖 Enterprise Multi-Agent AI System

[![LangGraph](https://img.shields.io/badge/Orchestrator-LangGraph-blue?logo=langchain&style=flat-square)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white&style=flat-square)](https://fastapi.tiangolo.com)
[![Next.js 14](https://img.shields.io/badge/Frontend-Next.js%2014-000000?logo=nextdotjs&logoColor=white&style=flat-square)](https://nextjs.org)
[![Docker](https://img.shields.io/badge/Deployment-Docker-2496ED?logo=docker&logoColor=white&style=flat-square)](https://www.docker.com)
[![uv](https://img.shields.io/badge/PackageManager-uv-DE5FE9?style=flat-square)](https://docs.astral.sh/uv/)
[![Langfuse](https://img.shields.io/badge/Observability-Langfuse-FF6C37?style=flat-square)](https://langfuse.com)
[![Aegra](https://img.shields.io/badge/AgentProtocol-Aegra-7C3AED?style=flat-square)](https://aegra.dev)
[![Tests](https://img.shields.io/badge/Tests-67%20passed-brightgreen?style=flat-square)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

> A production-grade, local-first multi-agent AI system designed for enterprise-scale workflow automation. Built on **LangGraph**, it features a **Planner → Executor → Validator** pipeline with integrated **pgvector (PostgreSQL)** RAG, persistent Redis-based session memory, automated LLM-as-judge evaluation, SSE streaming, full containerization, self-hosted observability tracing, and Agent Protocol compatibility.
>
> **Works 100% free** using Groq, Gemini, or Ollama for LLM tasks, and HuggingFace for local embeddings.

---

## 🏗️ Architecture

```
                 User Input / Query
                          │
                          ▼
      [Memory & RAG Retrieval Node] ◄─── PostgreSQL (pgvector)
                          │              Redis Session Memory (History)
                          ▼
              [Planner Agent Node]  ◄─── Decomposes input into dependency
                          │              graph / sub-tasks (JSON format)
                          ▼
           ┌───► [Executor Agent Loop]
           │      Loops through all sub-tasks in dependency order:
           │        ├── 🔍 Research  (Write-Todos Planning + Web Search + pgvector RAG)
           │        ├── 📊 Analysis  (PostgreSQL Database Queries + Insights)
           │        └── ✍️ Writer    (Synthesis + Markdown Formatting)
           │              │
           │              ▼
           │     [Validator Agent Node] ◄─── LLM-as-Judge validation (3 axes)
           │              │
           │              ├─► Score ≥ 75% ──► Final Output ✅ ──► END
           │              ├─► Score < 75% ──► Auto-Retry (Max 3x) 🔄 ──┐
           │              │                                          │
           │              └─► Flagged/Unsure ──► Human-in-the-Loop ⏸   │
           │                                          │              │
           │                                          ▼              │
           └─────────────────────────── Resumes with feedback ◄───────┘
```

---

## ✨ Features

- **Cyclic Agentic Workflows**: Built on **LangGraph** to govern agent state transitions, manage iterative retry loops, and implement interrupts for Human-in-the-Loop (HITL) checkpoints.
- **Unified PostgreSQL Storage**: Relational tables (`users`, `sales`, `employees`), checkpointer states (`PostgresSaver`), and vector embeddings (`pgvector`) are consolidated into a high-performance PostgreSQL instance.
- **Sub-task Dependency Resolution**: The **Planner Agent** parses the primary user request and outputs a structured JSON DAG of sub-tasks with mapped execution dependencies.
- **Specialized Executors**:
  - `research`: Structured write-todos planning (3-phase: Plan → Execute → Synthesize) using web search and pgvector RAG retrieval.
  - `analysis`: Queries a structured PostgreSQL database (with comment-stripping guardrails) and provides data analysis.
  - `writer`: Synthesizes execution results into a comprehensive output document.
- **deepagents-Inspired Research Planning**: The research executor implements a structured multi-step planning pattern (`write_todos`), decomposing tasks into sequential JSON steps executed tool-by-tool with full observability tracing.
- **LLM-as-Judge Evaluation**: Grades outputs across three dimensions: *Factual Accuracy*, *Task Completion*, and *Format Compliance*. The overall weighted score determines whether output passes, retries, or escalates for human intervention.
- **RAG & Memory Integration**: High-dimensional vector search using `pgvector` with HNSW cosine distance indexes; **HuggingFace** sentence-transformers locally; **Redis** session memory.
- **Agent Protocol Compliance**: Full `/assistants`, `/threads`, `/runs` REST API. Concurrent run guards, Redis TTL expiry, and HITL resume via both legacy and Agent Protocol paths.
- **Self-Hosted Observability** (Langfuse v2): Full LLM trace capture across all agent nodes. Validation scores and HITL events published as structured Langfuse scores.
- **Aegra Integration**: Standalone Agent Protocol compatibility layer for LangGraph Studio. Runs fully decoupled — separate Postgres DB, separate port, separate Docker stage.
- **uv Dependency Management**: All dependencies managed via `uv` with exact version pins in `pyproject.toml` and a reproducible `uv.lock` lockfile. Cross-platform Docker builds use `uv sync --frozen`.

---

## 🆓 Free LLM Providers

| Provider | Model | Setup Time | Usage Limits | Description |
|---|---|---|---|---|
| **Groq** ⭐ | `llama-3.3-70b-versatile` | 2 min | Generous free tier | **Recommended** — Extremely fast inference, excellent tool use capabilities. |
| **Google Gemini** | `gemini-1.5-flash` | 2 min | 1500 req/day | High performance, very long context window. |
| **Ollama** | `llama3.2` | 5 min | Unlimited (Local) | Runs completely locally on your hardware. |

---

## 📁 Project Structure

```
Enterprise-multi-agent-AI-system/
├── agents/
│   ├── executor.py         # Research (write-todos planner), Analysis & Writer executors
│   ├── llm_factory.py      # Configures LangChain models for Groq / Gemini / Ollama
│   ├── planner.py          # Decomposes user request into sub-tasks (JSON plan)
│   └── validator.py        # Evaluates output quality & processes Human-in-the-Loop review
├── aegra.json              # Aegra self-hosted Agent Protocol deployment config
├── api/
│   └── main.py             # FastAPI App: SSE streaming, Agent Protocol endpoints, HITL
├── auth/
│   └── models.py           # PostgreSQL-backed JWT user credentials and migration schemas
├── config.py               # Pydantic base settings loaded from environment
├── data/
│   ├── uploads/            # Ingested PDF, TXT, and CSV documents
│   └── outputs/            # Saved markdown/JSON agent output reports
├── docker-compose.yml      # Orchestrates all 7 services (api, redis, langfuse, aegra, dbs)
├── Dockerfile              # Multi-stage build: api (py3.11) + aegra (py3.12)
├── .dockerignore           # Excludes .venv, data, frontend from Docker build context
├── evals/
│   └── eval_pipeline.py    # Offline evaluation engine measuring 4 quality dimensions
├── frontend/               # Next.js 14 frontend dashboard
├── graph/
│   ├── observability.py    # Langfuse tracing: callbacks, safe_uuid, score publishers
│   ├── state.py            # TypedDict defining AgentState shared variables
│   └── workflow.py         # LangGraph state machine flow definitions & transitions
├── memory/
│   └── vector_store.py     # Embeddings factory, pgvector databases, & Redis memory
├── pyproject.toml          # uv project config with exact version pins
├── uv.lock                 # Reproducible lockfile (189 packages)
├── tests/
│   └── test_agents.py      # 67 unit, integration, routing, API, and observability tests
└── tools/
    ├── db_tool.py          # PostgreSQL SELECT execution & metadata query tools
    ├── file_tool.py        # File read, directory search, & output write tools
    ├── rag_tool.py         # pgvector semantic query search
    └── search_tool.py      # Internet search (SerpAPI with DuckDuckGo free fallback)
```

---

## 🚀 Installation & Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/Enterprise-multi-agent-AI-system.git
cd Enterprise-multi-agent-AI-system
```

### 2. Configure Environment Variables
```bash
cp .env.example .env
# Edit .env — set your LLM API key and database settings
```

#### Minimum Required Settings:
```bash
# Pick your LLM Provider: groq | gemini | ollama
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here

# Database passwords — use secure random values
LANGFUSE_DB_PASSWORD=change_me_to_random_string
AEGRA_DB_PASSWORD=change_me_to_random_string
DB_PASSWORD=change_me_to_random_string
NEXTAUTH_SECRET=change_me_to_random_string
SALT=change_me_to_random_string

# Vector Store Selection
VECTOR_STORE=pgvector
DB_URL=postgresql://postgres:postgres@localhost:5434/enterprise_app
```

---

## 🐳 Running with Docker (Recommended)

Start all services in detached mode. Docker Compose builds and coordinates all 7 backend services:

```bash
# First-time setup — build images:
docker-compose build api
docker-compose build aegra

# Start all services:
docker-compose up -d
```

### Detached Service Architecture & Ports:

| Service | Port / URL | Engine / Image | Description |
|---|---|---|---|
| **FastAPI Backend** | `http://localhost:8000` | `enterprise-multi-agent-ai-system-api` | Primary API, JWT auth & Agent Protocol |
| **Aegra Layer** | `http://localhost:8001` | `enterprise-multi-agent-ai-system-aegra` | LangGraph Studio compatibility layer |
| **Langfuse Portal** | `http://localhost:4000` | `langfuse/langfuse:2` | Tracing & observability dashboard |
| **Application DB** | `localhost:5434` | `pgvector/pgvector:pg16` | PostgreSQL for auth, business DB & vectors |
| **Aegra DB** | `localhost:5433` | `postgres:16-alpine` | PostgreSQL isolated for Aegra states |
| **Langfuse DB** | `localhost:5432` | `postgres:16-alpine` | PostgreSQL for Langfuse tracing logs |
| **Redis Cache** | `localhost:6379` | `redis:7-alpine` | Key-value store for session memory |

```bash
# Rebuild a single service after code changes:
docker-compose up --build -d api

# Stop all services:
docker-compose down

# Stop and wipe databases (full reset):
docker-compose down -v
```

---

## 💻 Running Locally (without Docker)

If you have PostgreSQL (with `pgvector` extension) and Redis running locally on your system:

### 1. Install uv
```powershell
# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Initialize and Sync Environment
```bash
# Synchronize core dependencies
uv sync

# Synchronize dev environments (pytest + aegra-cli — requires Python >= 3.12)
uv sync --all-groups
```

### 3. Run FastAPI Backend
```bash
# Windows
.venv\Scripts\activate
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

# macOS / Linux
source .venv/bin/activate
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

---

## 🌐 Running the Frontend

Navigate to the frontend folder, install dependencies, and launch the development dashboard:

```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 🧪 Running Tests

You can run the full Pytest suite within the `uv` environment:

```bash
# Run pytest directly via uv
uv run pytest tests/ -v
```

> [!NOTE]
> All **67 tests are passing successfully** with zero errors:
> - `TestConfig` (4 tests)
> - `TestAgentState` (3 tests)
> - `TestPlanner` (4 tests)
> - `TestExecutor` (3 tests)
> - `TestValidator` (6 tests)
> - `TestWorkflowRouting` (5 tests)
> - `TestEvalPipeline` (3 tests)
> - `TestAPI` (5 tests)
> - `TestAgentProtocolAPI` (8 tests)
> - `TestLangfuseObservability` (5 tests)
> - `TestAegraIntegration` (1 test)
> - `TestDeepAgentsResearch` (4 tests)
> - `TestAuth` (9 tests)
> - `TestPostgreSQL` (7 tests)

---

## 🔐 Authentication

All API endpoints (except `GET /health` and `/auth/*`) are protected by a two-layer authentication mechanism. Callers must authenticate using **either** of the following:

### 1. Static API Key (Service-to-Service)
Set the `API_KEY` environment variable in `.env`. Programmatic clients can pass this token in the header:
```http
Authorization: Bearer <your_configured_api_key>
```

### 2. JWT Authentication (Dashboard Users)
Dashboard users must register and log in to obtain a signed JWT token:

* **Register a New User**:
  ```http
  POST /auth/register
  Content-Type: application/json

  {
    "username": "admin",
    "email": "admin@example.com",
    "password": "securepassword"
  }
  ```
* **Login to Obtain JWT**:
  ```http
  POST /auth/login
  Content-Type: application/json

  {
    "username": "admin",
    "password": "securepassword"
  }
  ```
  Returns:
  ```json
  {
    "access_token": "<signed_jwt_token>",
    "token_type": "bearer"
  }
  ```
* **Call Protected Endpoints**:
  Pass the returned JWT token as a Bearer token in the `Authorization` header:
  ```http
  Authorization: Bearer <signed_jwt_token>
  ```
