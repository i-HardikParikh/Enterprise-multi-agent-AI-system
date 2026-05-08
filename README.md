# 🤖 Enterprise Multi-Agent AI System

> Production-grade multi-agent AI system built with **LangGraph**.
> Features Planner → Executor → Validator pipeline with RAG, session memory,
> LLM-as-judge evaluation, SSE streaming, and Docker deployment.
> **Works 100% free** using Groq, Gemini, or Ollama.

---

## 🏗️ Architecture

```
User Input
    │
    ▼
[Memory & RAG]      ← FAISS (local) + Redis session memory
    │                 HuggingFace embeddings (free, no API key)
    ▼
[Planner Agent]     ← Decomposes task → ordered sub-tasks (JSON)
    │
    ▼
[Executor Agent] ◄──── Loops until all sub-tasks done
 ├── Research    (web search + RAG retrieval)
 ├── Analysis    (SQL DB queries + insights)
 └── Writer      (synthesis + final document)
    │
    ▼
[Validator Agent]   ← LLM-as-Judge scoring (3 axes, weighted)
    │
    ├── Score ≥ 75% ──► Final Output ✅
    ├── Score < 75% ──► Retry (max 3x) 🔄
    └── Flagged     ──► Human Review ⏸️
```

---

## 🆓 Free LLM Providers

| Provider | Speed  | Setup | Limit |
|---|---|---|---|
| **Groq** ⭐ | Fastest | 2 min | Generous free tier |
| **Gemini Flash** | Fast | 2 min | 1500 req/day |
| **Ollama** | Local | Install | Unlimited (local) |

Embeddings use **HuggingFace sentence-transformers** — completely free, runs locally.

---

## 🚀 Quick Start

### 1. Clone & install
```bash
git clone https://github.com/yourusername/enterprise-agent-system
cd enterprise-agent-system
pip install -r requirements.txt
```

### 2. Configure (pick ONE provider)

```bash
cp .env.example .env
```

**Option A — Groq (recommended)**
```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_from_console.groq.com
```

**Option B — Google Gemini**
```env
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your_key_from_aistudio.google.com
```

**Option C — Ollama (local)**
```bash
# First install Ollama: https://ollama.com
ollama pull llama3.2
```
```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
```

### 3. Run

```bash
# With Docker (includes Redis)
docker-compose up --build

# Or locally
uvicorn api.main:app --reload
```

### 4. Start the Frontend
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` in your browser.

---

## 📡 API Reference

### Health check (shows active provider)
```bash
curl http://localhost:8000/health
# {"status":"ok","llm_provider":"groq","llm_model":"llama-3.3-70b-versatile","llm_type":"cloud_free"}
```

### Run agent (sync)
```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Analyse Q1 sales and write a report", "output_format": "markdown"}'
```

### Run agent (SSE streaming)
```bash
curl -N -X POST http://localhost:8000/run/stream \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Generate a market analysis report"}'
```

### Upload document to knowledge base
```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@my_report.pdf"
```

### Get job status
```bash
curl http://localhost:8000/status/{job_id}
```

### Submit human review (HITL)
```bash
curl -X POST http://localhost:8000/human-review \
  -H "Content-Type: application/json" \
  -d '{"job_id": "xxx", "feedback": "Looks good", "approved": true}'
```

### Run evaluation on completed job
```bash
curl -X POST http://localhost:8000/evaluate/{job_id}
```

---

## 📁 Project Structure

```
enterprise-agent-system/
├── agents/
│   ├── llm_factory.py      ← Groq / Gemini / Ollama factory
│   ├── planner.py          ← Planner Agent (JSON plan output)
│   ├── executor.py         ← Executor Agent (ReAct, 3 types)
│   └── validator.py        ← Validator Agent + HITL node
├── graph/
│   ├── state.py            ← AgentState TypedDict
│   └── workflow.py         ← LangGraph state machine
├── memory/
│   └── vector_store.py     ← FAISS + Pinecone + Redis + HF embeddings
├── tools/
│   ├── search_tool.py      ← Web search (DuckDuckGo, free)
│   ├── rag_tool.py         ← Knowledge base retrieval
│   ├── db_tool.py          ← SQLite query tool
│   └── file_tool.py        ← File read/write tools
├── api/
│   └── main.py             ← FastAPI + SSE streaming endpoints
├── evals/
│   └── eval_pipeline.py    ← LLM-as-judge (4 dimensions)
├── frontend/               ← Next.js frontend application
├── tests/
│   └── test_agents.py      ← Unit + integration tests
├── .github/workflows/
│   └── ci.yml              ← GitHub Actions CI/CD
├── config.py               ← Pydantic settings
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## 🧠 Key Design Decisions

**Why LangGraph?**
State machine approach gives full control over agent flow, retry logic,
and human-in-the-loop pausing — impossible with simple chains.

**Why ReAct prompting?**
Works with ALL LLMs including Groq/Gemini/Ollama — not locked to OpenAI tool-use format.

**Why HuggingFace embeddings?**
Zero cost, no API key, runs locally, good quality for RAG.

**Why LLM-as-Judge?**
Automated quality scoring enables retry loops and regression testing
without human labelling — key for production reliability.

---

## 🧪 Tests

```bash
pytest tests/ -v
```

---

## 💼 Interview Talking Points

> *"I built a multi-agent system with LangGraph where the Planner decomposes tasks into a JSON dependency graph, multiple typed Executors run in a loop using ReAct prompting with tool-use (web search, SQL, RAG), and a Validator agent scores output quality using LLM-as-Judge on three axes. If quality drops below 75%, the system automatically retries from the planning stage. I added LangSmith observability, Human-in-the-Loop via LangGraph's interrupt mechanism, Redis session memory, HuggingFace embeddings for free RAG, SSE streaming output, Docker deployment, and a RAGAS-inspired evaluation pipeline — all running on free LLM providers."*

---

## 🛠️ Tech Stack

`Python 3.11` · `FastAPI` · `LangGraph` · `LangChain` · `Groq / Gemini / Ollama` · `FAISS` · `HuggingFace` · `Redis` · `LangSmith` · `Docker` · `GitHub Actions`
