# 🤖 Enterprise Multi-Agent AI System

[![LangGraph](https://img.shields.io/badge/Orchestrator-LangGraph-blue?logo=langchain&style=flat-square)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white&style=flat-square)](https://fastapi.tiangolo.com)
[![Next.js 14](https://img.shields.io/badge/Frontend-Next.js%2014-000000?logo=nextdotjs&logoColor=white&style=flat-square)](https://nextjs.org)
[![Docker](https://img.shields.io/badge/Deployment-Docker-2496ED?logo=docker&logoColor=white&style=flat-square)](https://www.docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

> A production-grade, local-first multi-agent AI system designed for enterprise-scale workflow automation. Built on top of **LangGraph**, it features a robust **Planner → Executor → Validator** pipeline with integrated RAG, persistent Redis-based session memory, automated LLM-as-judge evaluation metrics, Server-Sent Events (SSE) streaming updates, and full containerization.
> 
> **Works 100% free** using Groq, Gemini, or Ollama for LLM tasks, and HuggingFace for local embeddings.

---

## 🏗️ Architecture

```
                 User Input / Query
                         │
                         ▼
     [Memory & RAG Retrieval Node] ◄─── FAISS (Local) / Pinecone (Cloud)
                         │              Redis Session Memory (History)
                         ▼
             [Planner Agent Node]  ◄─── Decomposes input into dependency
                         │              graph / sub-tasks (JSON format)
                         ▼
          ┌───► [Executor Agent Loop]
          │      Loops through all sub-tasks in dependency order:
          │        ├── 🔍 Research  (Web Search + RAG Retrieval)
          │        ├── 📊 Analysis  (SQL Database Queries + Insights)
          │        └── ✍️ Writer    (Synthesis + Markdown Formatting)
          │              │
          │              ▼
          │     [Validator Agent Node] ◄─── LLM-as-Judge validation (3 axes)
          │              │
          │              ├─► Score ≥ 75% ──► Final Output ✅ ──► END
          │              ├─► Score < 75% ──► Auto-Retry (Max 3x) 🔄 ──┐
          │              │                                           │
          │              └─► Flagged/Unsure ──► Human-in-the-Loop ⏸   │
          │                                           │              │
          │                                           ▼              │
          └─────────────────────────── Resumes with feedback ◄───────┘
```

---

## ✨ Features

- **Cyclic Agentic Workflows**: Built on **LangGraph** to govern agent state transitions, manage iterative retry loops, and implement interrupts for Human-in-the-Loop (HITL) checkpoints.
- **Sub-task Dependency Resolution**: The **Planner Agent** parses the primary user request and outputs a structured JSON DAG (Directed Acyclic Graph) of sub-tasks with mapped execution dependencies.
- **Specialized Executors**:
  - `research`: Gathers data using web searches and RAG retrieval.
  - `analysis`: Queries a structured database and provides data analysis.
  - `writer`: Synthesizes execution results into a comprehensive output document.
- **LLM-as-Judge Evaluation**: Integrated pipeline that grades generated outputs across three dimensions: *Factual Accuracy*, *Task Completion*, and *Format Compliance*. An overall weighted score determines whether the output passes, retries, or escalates for human intervention.
- **RAG & Memory Integration**:
  - **Vector Stores**: Supports local **FAISS** (zero configuration) or cloud-hosted **Pinecone**.
  - **Free Embeddings**: Uses **HuggingFace** sentence-transformers (`all-MiniLM-L6-v2`) running locally.
  - **Session Memory**: Employs **Redis** to store and summarize user session conversation context.
- **Asynchronous Execution & SSE Streaming**: Built using FastAPI to support asynchronous job state tracking, Server-Sent Events (SSE) updates for step-by-step UI visualization, and back-grounded document ingestion.
- **Modern Next.js Dashboard**: Dynamic dashboard interface displaying an animated agent pipeline visualization, live timestamped logs, structured output views (with markdown rendering and raw JSON tabs), document uploader, history search, and provider status indicators.

---

## 🆓 Free LLM Providers

This system is configured to support free LLM APIs and local inference engines:

| Provider | Model | Setup Time | Usage Limits | Description |
|---|---|---|---|---|
| **Groq** ⭐ | `llama-3.3-70b-versatile` | 2 min | Generous free tier | **Recommended** — Extremely fast inference, excellent tool use capabilities. |
| **Google Gemini** | `gemini-1.5-flash` | 2 min | 1500 req/day | High performance, very long context window. |
| **Ollama** | `llama3.2` | 5 min | Unlimited (Local) | Runs completely locally on your hardware. Great for privacy and offline usage. |

---

## 📁 Project Structure

```
Enterprise-multi-agent-AI-system/
├── agents/
│   ├── __init__.py
│   ├── executor.py         # Specialized Research, Analysis, & Writer Executors (ReAct format)
│   ├── llm_factory.py      # Configures LangChain models for Groq / Gemini / Ollama
│   ├── planner.py          # Decomposes user request into sub-tasks (JSON plan)
│   └── validator.py        # Evaluates output quality & processes Human-in-the-Loop review
├── api/
│   ├── __init__.py
│   └── main.py             # FastAPI App with SSE streaming, file upload, & job status
├── config.py               # Pydantic base settings loaded from environment
├── data/
│   ├── checkpoints.db      # Persistent SQLite db storing LangGraph workflow states
│   ├── enterprise.db       # SQLite business DB auto-seeded with sales & employee tables
│   ├── faiss_index/        # Local FAISS index files
│   ├── uploads/            # Ingested PDF, TXT, and CSV documents
│   └── outputs/            # Saved markdown/JSON agent output reports
├── docker-compose.yml      # Orchestrates FastAPI app and Redis container services
├── Dockerfile              # multi-stage python container build (pre-downloads HF model)
├── evals/
│   ├── __init__.py
│   └── eval_pipeline.py    # Offline evaluation engine measuring 4 quality dimensions
├── frontend/               # Next.js 14 frontend dashboard
├── graph/
│   ├── __init__.py
│   ├── state.py            # TypedDict defining AgentState shared variables
│   └── workflow.py         # LangGraph state machine flow definitions & transitions
├── memory/
│   ├── __init__.py
│   └── vector_store.py     # Embeddings factory, FAISS/Pinecone vectors, & Redis memory
├── requirements.txt        # Backend python dependencies list
├── tests/
│   ├── __init__.py
│   └── test_agents.py      # Unit, integration, routing, and api tests (pytest)
└── tools/
    ├── __init__.py
    ├── db_tool.py          # SQLite SELECT execution & metadata query tools
    ├── file_tool.py        # File read, directory search, & output write tools
    ├── rag_tool.py         # Local/Pinecone vector semantic query search
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
Create a `.env` file in the root directory:
```bash
# Pick your LLM Provider: groq | gemini | ollama
LLM_PROVIDER=groq

# ── Option A: Groq (Recommended - Free & Fast) ──
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# ── Option B: Google Gemini ──
GOOGLE_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash

# ── Option C: Ollama (Local) ──
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# ── Optional: Cloud RAG Upgrade (Pinecone) ──
# VECTOR_STORE=pinecone
# PINECONE_API_KEY=your_pinecone_key_here
# PINECONE_INDEX_NAME=your_index_name_here

# ── Optional: Search Engine API (SerpAPI) ──
# SERPAPI_API_KEY=your_serpapi_key_here
```

### 3. Run the Backend & Infrastructure

#### Option A: Docker (Recommended)
This launches the FastAPI application along with a Redis server container. The Dockerfile pre-downloads the HuggingFace embedding model so the first query runs instantly.
```bash
docker-compose up --build
```

#### Option B: Running Locally
Ensure you have Redis installed and running on `localhost:6379`, then start the backend:
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# Run FastAPI app
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

### 4. Run the Next.js Frontend
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser to access the dashboard.

---

## 📡 API Reference

### Health & Settings Check
* **Endpoint**: `GET /health`
* **Response**: Checks active configuration and reports database connectivity status.
```json
{
  "status": "ok",
  "version": "1.0.0",
  "llm_provider": "groq",
  "llm_model": "llama-3.3-70b-versatile",
  "llm_type": "cloud_free"
}
```

### Execute Agent Task (Synchronous)
* **Endpoint**: `POST /run`
* **Request Payload**:
```json
{
  "user_input": "Analyse Widget A sales from South region and write a summary.",
  "session_id": "session-123",
  "output_format": "markdown"
}
```
* **Response**: Returns final generated output, evaluation score, and execution steps history.

### Stream Agent Task (SSE Streaming)
* **Endpoint**: `POST /run/stream`
* **Request Payload**: Same as `/run`.
* **Description**: Returns a Server-Sent Events stream emitting updates during step execution:
  - `event: start` -> initial job context
  - `event: step_start` -> active graph node (e.g. `planner`, `executor`, etc.)
  - `event: step_done` -> completed step message
  - `event: done` -> final state output, validation metadata, and status
  - `event: error` -> exception trace context

### Upload File to Vector Store
* **Endpoint**: `POST /upload`
* **Content-Type**: `multipart/form-data`
* **Parameters**: `file` (Supported: `.txt`, `.pdf`, `.csv`, `.md`)
* **Description**: Receives document and registers chunks in background thread to the configured Vector Store.

### Submit Human Review (HITL)
* **Endpoint**: `POST /human-review`
* **Request Payload**:
```json
{
  "job_id": "a9073cde",
  "feedback": "Add more details about Widget B next quarter projections.",
  "approved": false
}
```
* **Description**: Unpauses and resumes a graph workflow currently suspended at a human verification node.

### Offline Output Evaluation (LLM-as-Judge)
* **Endpoint**: `POST /evaluate/{job_id}`
* **Description**: Evaluates job performance metrics against 4 pillars: *Faithfulness*, *Answer Relevance*, *Completeness*, and *Clarity*.

---

## 🧪 Running Tests

The test suite validates agent state parsing, JSON schemas, workflow transitions, and API response contracts.

To execute tests:
```bash
pytest tests/ -v
```

For detailed console tracebacks:
```bash
python tests/test_agents.py
```

---

## 🧠 Key Technical Highlights

1. **Robust JSON Parsing**: Local and smaller model outputs frequently suffer from loose JSON formats or markdown wrapper errors. The system utilizes a regex-supported extraction fallback in `planner.py` and `validator.py` to ensure stable graph execution.
2. **ReAct Tool Loop**: The Executor Node leverages classic ReAct (Reason-Action) patterns using `langchain-classic` templates. This enables standard tool calls without requiring OpenAI-specific function calling parameters, allowing compatibility with any open-weights LLM.
3. **Graceful Degradation**: If tool-use calls fail due to token limits or structural errors, the Executor automatically falls back to direct inference (`_run_simple_executor`), compiling answers based on retrieved context.
4. **Data Seeding**: On start, `tools/db_tool.py` automatically checks for the existence of `data/enterprise.db` and auto-seeds tables (`sales` and `employees`) to enable immediate analysis query actions.

---

## 🛠️ Tech Stack

* **Orchestration**: `LangGraph` · `LangChain`
* **Backend API**: `FastAPI` · `Uvicorn` · `SSE-Starlette`
* **Database & Storage**: `SQLite` · `FAISS` · `Pinecone (Optional)` · `Redis`
* **Frontend Dashboard**: `Next.js 14` · `React` · `Tailwind CSS` · `Lucide Icons` · `TypeScript`
* **Embeddings & Inference**: `HuggingFace sentence-transformers` · `Groq Cloud` · `Google Gemini API` · `Ollama (Local)`
* **Quality Assurance**: `Pytest` · `LLM-as-Judge`
