"""
api/main.py — FastAPI Application

Endpoints:
  GET  /health           — Health check + provider info
  POST /run              — Run agent, returns final result
  POST /run/stream       — SSE streaming with step updates
  GET  /status/{job_id}  — Get status of a job
  POST /upload           — Upload document to knowledge base
  POST /human-review     — Submit HITL feedback
  POST /evaluate/{id}    — Run eval pipeline on a completed job
"""
import uuid
import asyncio
import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import AsyncGenerator

from graph.workflow import get_graph
from graph.state import AgentState, TaskStatus
from memory.vector_store import get_vector_store
from evals.eval_pipeline import run_evaluation
from agents.llm_factory import get_provider_info

logger = structlog.get_logger()

# In-memory job store (replace with Redis in production)
_jobs: dict[str, dict] = {}

# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app.startup — warming up graph")
    get_graph()
    logger.info("app.ready")
    yield
    logger.info("app.shutdown")

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Enterprise Multi-Agent AI System",
    description="LangGraph multi-agent system — Planner → Executor → Validator",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend - Removed since frontend is now a standalone Next.js app

# ── Models ────────────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    user_input: str
    session_id: str = ""
    output_format: str = "markdown"

class RunResponse(BaseModel):
    job_id: str
    status: str
    final_output: str | None = None
    validation_score: float | None = None
    step_history: list[str] = []
    error_log: list[str] = []
    tokens_used: int = 0

class HumanReviewRequest(BaseModel):
    job_id: str
    feedback: str
    approved: bool

# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_initial_state(req: RunRequest, job_id: str) -> AgentState:
    return AgentState(
        user_input=req.user_input,
        session_id=req.session_id or job_id,
        plan=None,
        sub_tasks=[],
        task_dependencies={},
        execution_results=[],
        current_task_index=0,
        tool_calls_log=[],
        retrieved_context=None,
        memory_summary=None,
        validation_result=None,
        retry_count=0,
        final_output=None,
        output_format=req.output_format,
        status=TaskStatus.PENDING,
        error_log=[],
        requires_human_review=False,
        human_feedback=None,
        step_history=[],
        total_tokens_used=0,
    )

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    provider = get_provider_info()
    return {
        "status": "ok",
        "version": "1.0.0",
        "llm_provider": provider["provider"],
        "llm_model": provider["model"],
        "llm_type": provider["type"],
    }


@app.post("/run", response_model=RunResponse)
async def run_agent(req: RunRequest):
    """Synchronous — runs full pipeline and returns when done."""
    if not req.user_input.strip():
        raise HTTPException(status_code=422, detail="user_input cannot be empty")

    job_id = str(uuid.uuid4())
    logger.info("run.start", job_id=job_id, input=req.user_input[:80])

    graph = get_graph()
    config = {"configurable": {"thread_id": job_id}}
    initial_state = _build_initial_state(req, job_id)

    try:
        final_state = await asyncio.to_thread(graph.invoke, initial_state, config)
        _jobs[job_id] = final_state
        validation = final_state.get("validation_result")
        return RunResponse(
            job_id=job_id,
            status=str(final_state.get("status", TaskStatus.COMPLETED)),
            final_output=final_state.get("final_output"),
            validation_score=validation.get("score") if validation else None,
            step_history=final_state.get("step_history", []),
            error_log=final_state.get("error_log", []),
            tokens_used=final_state.get("total_tokens_used", 0),
        )
    except Exception as e:
        logger.error("run.error", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/run/stream")
async def run_agent_stream(req: RunRequest):
    """
    Streaming SSE endpoint — yields step updates as the graph executes.
    Open frontend/index.html to see the live UI.
    """
    if not req.user_input.strip():
        raise HTTPException(status_code=422, detail="user_input cannot be empty")

    job_id = str(uuid.uuid4())
    logger.info("stream.start", job_id=job_id)

    graph = get_graph()
    config = {"configurable": {"thread_id": job_id}}
    initial_state = _build_initial_state(req, job_id)

    async def event_generator() -> AsyncGenerator[dict, None]:
        import json
        try:
            yield {"event": "start", "data": json.dumps({"job_id": job_id})}

            async for event in graph.astream_events(initial_state, config, version="v2"):
                kind = event.get("event", "")
                name = event.get("name", "")

                TRACKED_NODES = {"planner", "executor", "validator", "memory_retrieval"}

                if kind == "on_chain_start" and name in TRACKED_NODES:
                    yield {
                        "event": "step_start",
                        "data": json.dumps({"node": name, "job_id": job_id}),
                    }

                elif kind == "on_chain_end" and name in TRACKED_NODES:
                    output = event.get("data", {}).get("output", {})
                    steps = output.get("step_history", [])
                    msg = steps[-1] if steps else f"Completed: {name}"
                    yield {
                        "event": "step_done",
                        "data": json.dumps({"node": name, "message": msg, "job_id": job_id}),
                    }

                elif kind == "on_chain_error":
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": f"Error in {name}", "job_id": job_id}),
                    }

            # Final state
            final = graph.get_state(config).values
            _jobs[job_id] = final
            validation = final.get("validation_result") or {}
            payload = json.dumps({
                "job_id": job_id,
                "status": str(final.get("status", "completed")),
                "final_output": (final.get("final_output") or "")[:3000],
                "validation_score": validation.get("score"),
                "step_history": final.get("step_history", []),
            })
            yield {"event": "done", "data": payload}

        except Exception as e:
            import json as j
            yield {"event": "error", "data": j.dumps({"error": str(e), "job_id": job_id})}

    return EventSourceResponse(event_generator())


@app.get("/status/{job_id}", response_model=RunResponse)
async def get_status(job_id: str):
    state = _jobs.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    validation = state.get("validation_result")
    return RunResponse(
        job_id=job_id,
        status=str(state.get("status", "unknown")),
        final_output=state.get("final_output"),
        validation_score=validation.get("score") if validation else None,
        step_history=state.get("step_history", []),
        error_log=state.get("error_log", []),
        tokens_used=state.get("total_tokens_used", 0),
    )


@app.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Upload a document (.txt, .pdf, .csv) to the RAG knowledge base."""
    from pathlib import Path
    import shutil

    allowed = {".txt", ".pdf", ".csv", ".md"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"File type {ext} not supported. Use: {allowed}")

    upload_dir = Path("./data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / file.filename

    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    def ingest():
        try:
            store = get_vector_store()
            n = store.add_documents(str(dest))
            logger.info("upload.ingested", file=file.filename, chunks=n)
        except Exception as e:
            logger.error("upload.ingest_error", error=str(e))

    background_tasks.add_task(ingest)
    return {"message": f"Uploaded {file.filename}. Ingesting into knowledge base in background."}


@app.post("/human-review")
async def submit_human_review(req: HumanReviewRequest):
    """Submit human feedback for a paused HITL job."""
    graph = get_graph()
    config = {"configurable": {"thread_id": req.job_id}}

    state = graph.get_state(config)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found or already completed")

    graph.update_state(
        config,
        {
            "human_feedback": req.feedback if req.approved else f"REJECTED: {req.feedback}",
            "requires_human_review": False,
        },
        as_node="human_review",
    )

    final_state = await asyncio.to_thread(graph.invoke, None, config)
    _jobs[req.job_id] = final_state

    return {
        "message": "Human review submitted. Execution resumed.",
        "job_id": req.job_id,
        "status": str(final_state.get("status")),
    }


@app.post("/evaluate/{job_id}")
async def evaluate_output(job_id: str):
    """Run the LLM-as-judge evaluation pipeline on a completed job."""
    state = _jobs.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await asyncio.to_thread(
        run_evaluation,
        user_input=state["user_input"],
        final_output=state.get("final_output", ""),
        retrieved_context=state.get("retrieved_context", ""),
    )
    return result
