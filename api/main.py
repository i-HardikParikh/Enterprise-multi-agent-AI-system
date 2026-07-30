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

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Depends
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
from graph.observability import get_callbacks, log_hitl_event, safe_uuid
from auth.models import create_users_table
from auth.dependencies import require_auth
from auth.schemas import UserOut
from auth.routes import router as auth_router
import json
import redis
from config import get_settings

logger = structlog.get_logger()
_settings = get_settings()

try:
    _redis_client = redis.from_url(_settings.redis_url, decode_responses=True)
    _redis_client.ping()
    logger.info("api.redis_connected")
except Exception as e:
    _redis_client = None
    logger.warning("api.redis_unavailable — falling back to local memory dict", error=str(e))

_local_jobs: dict[str, dict] = {}
_local_threads: dict[str, dict] = {}
_local_runs: dict[str, dict] = {}

def get_job(job_id: str) -> dict | None:
    if _redis_client:
        try:
            val = _redis_client.get(f"job:{job_id}")
            if val:
                return json.loads(val)
        except Exception as e:
            logger.warning("api.redis_get_error", job_id=job_id, error=str(e))
    return _local_jobs.get(job_id)

def set_job(job_id: str, state: dict):
    ttl = _settings.redis_ttl_seconds or 86400
    if _redis_client:
        try:
            _redis_client.setex(
                f"job:{job_id}",
                ttl,
                json.dumps(dict(state), default=str)
            )
            return
        except Exception as e:
            logger.warning("api.redis_set_error", job_id=job_id, error=str(e))
    _local_jobs[job_id] = state

def get_thread(thread_id: str) -> dict | None:
    if _redis_client:
        try:
            val = _redis_client.get(f"thread:{thread_id}")
            if val:
                return json.loads(val)
        except Exception as e:
            logger.warning("api.redis_get_thread_error", thread_id=thread_id, error=str(e))
    return _local_threads.get(thread_id)

def set_thread(thread_id: str, state: dict):
    ttl = _settings.redis_ttl_seconds or 86400
    if _redis_client:
        try:
            _redis_client.setex(
                f"thread:{thread_id}",
                ttl,
                json.dumps(dict(state), default=str)
            )
            return
        except Exception as e:
            logger.warning("api.redis_set_thread_error", thread_id=thread_id, error=str(e))
    _local_threads[thread_id] = state

def get_run(run_id: str) -> dict | None:
    if _redis_client:
        try:
            val = _redis_client.get(f"run:{run_id}")
            if val:
                return json.loads(val)
        except Exception as e:
            logger.warning("api.redis_get_run_error", run_id=run_id, error=str(e))
    return _local_runs.get(run_id)

def set_run(run_id: str, state: dict):
    ttl = _settings.redis_ttl_seconds or 86400
    if _redis_client:
        try:
            _redis_client.setex(
                f"run:{run_id}",
                ttl,
                json.dumps(dict(state), default=str)
            )
            return
        except Exception as e:
            logger.warning("api.redis_set_run_error", run_id=run_id, error=str(e))
    _local_runs[run_id] = state

# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app.startup — warming up graph")
    get_graph()
    create_users_table()
    # Warm up and seed business database
    try:
        from tools.db_tool import _get_conn
        conn = _get_conn()
        conn.close()
        logger.info("api.business_db_initialized")
    except Exception as e:
        logger.error("api.business_db_initialization_failed", error=str(e))
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

app.include_router(auth_router)

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

# Standard Agent Protocol Models
class AssistantResponse(BaseModel):
    assistant_id: str
    name: str
    graph_id: str
    config: dict = {}
    created_at: str
    updated_at: str

class ThreadResponse(BaseModel):
    thread_id: str
    metadata: dict = {}
    created_at: str
    updated_at: str

class RunResponseStandard(BaseModel):
    run_id: str
    thread_id: str
    assistant_id: str
    status: str  # "pending", "running", "paused", "completed", "failed"
    final_output: str | None = None
    created_at: str
    updated_at: str

class ThreadStateResponse(BaseModel):
    values: dict
    next: list[str] = []
    metadata: dict = {}

class RunCreateRequest(BaseModel):
    assistant_id: str = "default"
    input: dict | None = None
    metadata: dict = {}

class ThreadStateUpdateRequest(BaseModel):
    values: dict
    as_node: str | None = None

class RunResumeRequest(BaseModel):
    feedback: str | None = None
    approved: bool | None = None

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
        approved=None,
        step_history=[],
        total_tokens_used=0,
    )

async def _execute_graph_run(thread_id: str, run_id: str, assistant_id: str, user_input: str | None = None):
    import datetime
    import uuid
    graph = get_graph()
    config = {
        "configurable": {
            "thread_id": thread_id,
            "trace_id": run_id
        },
        "run_id": uuid.UUID(safe_uuid(run_id)),
        "callbacks": get_callbacks(trace_id=run_id, session_id=thread_id)
    }
    
    state = graph.get_state(config)
    
    # If state.next is not empty, we are resuming from an interrupt (HITL).
    # Thus, we pass None as input to LangGraph.
    if state.next:
        initial_input = None
    else:
        if not state.values and not user_input:
            run_data = get_run(run_id)
            if run_data:
                run_data["status"] = "failed"
                run_data["final_output"] = "Error: Thread is empty and no user_input was provided."
                run_data["updated_at"] = datetime.datetime.utcnow().isoformat()
                set_run(run_id, run_data)
            return
        initial_input = {"user_input": user_input} if user_input else None

    # Update run status to running
    run_data = get_run(run_id)
    if run_data:
        run_data["status"] = "running"
        run_data["updated_at"] = datetime.datetime.utcnow().isoformat()
        set_run(run_id, run_data)

    try:
        final_state = await asyncio.to_thread(graph.invoke, initial_input, config)
        
        status = final_state.get("status", TaskStatus.COMPLETED)
        requires_human = final_state.get("requires_human_review", False)
        
        run_data = get_run(run_id)
        if run_data:
            if requires_human:
                run_data["status"] = "paused"
            elif status == TaskStatus.FAILED:
                run_data["status"] = "failed"
            else:
                run_data["status"] = "completed"
            run_data["final_output"] = final_state.get("final_output")
            run_data["updated_at"] = datetime.datetime.utcnow().isoformat()
            set_run(run_id, run_data)
            
            # Save the final state to jobs so that the status is consistent with old endpoints
            set_job(thread_id, final_state)
            
            # Clear active run lock on thread if finished or failed
            if run_data["status"] in ("completed", "failed"):
                thread_data = get_thread(thread_id)
                if thread_data and thread_data.get("metadata", {}).get("active_run_id") == run_id:
                    thread_data["metadata"]["active_run_id"] = None
                    thread_data["updated_at"] = datetime.datetime.utcnow().isoformat()
                    set_thread(thread_id, thread_data)
            
    except Exception as e:
        logger.error("runs.bg_execute_error", run_id=run_id, thread_id=thread_id, error=str(e))
        run_data = get_run(run_id)
        if run_data:
            run_data["status"] = "failed"
            run_data["final_output"] = f"Execution error: {str(e)}"
            run_data["updated_at"] = datetime.datetime.utcnow().isoformat()
            set_run(run_id, run_data)
        
        # Clear active run lock on thread on exception
        thread_data = get_thread(thread_id)
        if thread_data and thread_data.get("metadata", {}).get("active_run_id") == run_id:
            thread_data["metadata"]["active_run_id"] = None
            thread_data["updated_at"] = datetime.datetime.utcnow().isoformat()
            set_thread(thread_id, thread_data)

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


@app.post("/run", response_model=RunResponse, dependencies=[Depends(require_auth)])
async def run_agent(req: RunRequest):
    """Synchronous — runs full pipeline and returns when done."""
    if not req.user_input.strip():
        raise HTTPException(status_code=422, detail="user_input cannot be empty")

    job_id = str(uuid.uuid4())
    logger.info("run.start", job_id=job_id, input=req.user_input[:80])

    graph = get_graph()
    config = {
        "configurable": {
            "thread_id": job_id,
            "trace_id": job_id
        },
        "run_id": uuid.UUID(safe_uuid(job_id)),
        "callbacks": get_callbacks(trace_id=job_id, session_id=job_id)
    }
    initial_state = _build_initial_state(req, job_id)

    try:
        final_state = await asyncio.to_thread(graph.invoke, initial_state, config)
        set_job(job_id, final_state)
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


@app.post("/run/stream", dependencies=[Depends(require_auth)])
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
    config = {
        "configurable": {
            "thread_id": job_id,
            "trace_id": job_id
        },
        "run_id": uuid.UUID(safe_uuid(job_id)),
        "callbacks": get_callbacks(trace_id=job_id, session_id=job_id)
    }
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
            set_job(job_id, final)
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


@app.get("/status/{job_id}", response_model=RunResponse, dependencies=[Depends(require_auth)])
async def get_status(job_id: str):
    state = get_job(job_id)
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


@app.post("/upload", dependencies=[Depends(require_auth)])
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


@app.post("/human-review", dependencies=[Depends(require_auth)])
async def submit_human_review(req: HumanReviewRequest):
    """Submit human feedback for a paused HITL job."""
    graph = get_graph()
    config = {"configurable": {"thread_id": req.job_id}}

    # Log HITL resume event
    try:
        log_hitl_event(trace_id=req.job_id, event_type="resume", feedback=req.feedback, approved=req.approved)
    except Exception as e:
        logger.warning("api.submit_human_review_log_hitl_failed", error=str(e))

    state = graph.get_state(config)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found or already completed")

    if req.approved:
        state_update = {
            "human_feedback": req.feedback,
            "requires_human_review": False,
            "approved": True,
            "status": TaskStatus.COMPLETED,
            "step_history": [f"✅ Human approved: {req.feedback[:60]}"],
        }
    else:
        state_update = {
            "human_feedback": req.feedback,
            "requires_human_review": False,
            "approved": False,
            "status": TaskStatus.NEEDS_RETRY,
            "retry_count": 0,
            "step_history": [f"⚠️ Human rejected: {req.feedback[:60]}"],
        }

    graph.update_state(config, state_update, as_node="human_review")

    final_state = await asyncio.to_thread(graph.invoke, None, config)
    set_job(req.job_id, final_state)

    return {
        "message": "Human review submitted. Execution resumed.",
        "job_id": req.job_id,
        "status": str(final_state.get("status")),
    }


@app.post("/evaluate/{job_id}", dependencies=[Depends(require_auth)])
async def evaluate_output(job_id: str):
    """Run the LLM-as-judge evaluation pipeline on a completed job."""
    state = get_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await asyncio.to_thread(
        run_evaluation,
        user_input=state["user_input"],
        final_output=state.get("final_output", ""),
        retrieved_context=state.get("retrieved_context", ""),
    )
    return result


# ── Agent Protocol Standard Endpoints ──────────────────────────────────────────

@app.get("/assistants", response_model=list[AssistantResponse], dependencies=[Depends(require_auth)])
async def list_assistants():
    import datetime
    now_str = datetime.datetime.utcnow().isoformat()
    return [
        AssistantResponse(
            assistant_id="default",
            name="Enterprise AI Multi-Agent System",
            graph_id="enterprise_system",
            config={},
            created_at=now_str,
            updated_at=now_str
        )
    ]


@app.get("/assistants/{assistant_id}", response_model=AssistantResponse, dependencies=[Depends(require_auth)])
async def get_assistant(assistant_id: str):
    if assistant_id != "default":
        raise HTTPException(status_code=404, detail="Assistant not found")
    import datetime
    now_str = datetime.datetime.utcnow().isoformat()
    return AssistantResponse(
        assistant_id="default",
        name="Enterprise AI Multi-Agent System",
        graph_id="enterprise_system",
        config={},
        created_at=now_str,
        updated_at=now_str
    )


@app.post("/threads", response_model=ThreadResponse, dependencies=[Depends(require_auth)])
async def create_thread(req: RunCreateRequest = None):
    metadata = {}
    if req and req.metadata:
        metadata = req.metadata
    
    # Initialize empty lock for runs
    metadata["active_run_id"] = None
    
    thread_id = str(uuid.uuid4())
    import datetime
    now_str = datetime.datetime.utcnow().isoformat()
    thread_data = {
        "thread_id": thread_id,
        "metadata": metadata,
        "created_at": now_str,
        "updated_at": now_str
    }
    set_thread(thread_id, thread_data)
    return ThreadResponse(**thread_data)


@app.get("/threads/{thread_id}", response_model=ThreadResponse, dependencies=[Depends(require_auth)])
async def get_thread_endpoint(thread_id: str):
    thread = get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return ThreadResponse(**thread)


@app.get("/threads/{thread_id}/state", response_model=ThreadStateResponse, dependencies=[Depends(require_auth)])
async def get_thread_state(thread_id: str):
    thread = get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config)
    
    return ThreadStateResponse(
        values=state.values or {},
        next=list(state.next) if state.next else [],
        metadata=state.metadata or {}
    )


@app.post("/threads/{thread_id}/state", dependencies=[Depends(require_auth)])
async def update_thread_state(thread_id: str, req: ThreadStateUpdateRequest):
    thread = get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
        
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        graph.update_state(config, req.values, as_node=req.as_node)
        import datetime
        thread["updated_at"] = datetime.datetime.utcnow().isoformat()
        set_thread(thread_id, thread)
        return {"message": "Thread state updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/threads/{thread_id}/runs", response_model=RunResponseStandard, dependencies=[Depends(require_auth)])
async def create_run(thread_id: str, req: RunCreateRequest, background_tasks: BackgroundTasks):
    thread = get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
        
    # Concurrency guard
    active_run_id = thread.get("metadata", {}).get("active_run_id")
    if active_run_id:
        active_run = get_run(active_run_id)
        if active_run and active_run.get("status") in ("pending", "running"):
            raise HTTPException(
                status_code=409, 
                detail=f"Thread {thread_id} already has an active run ({active_run_id}) in status {active_run.get('status')}"
            )
            
    run_id = str(uuid.uuid4())
    import datetime
    now_str = datetime.datetime.utcnow().isoformat()
    
    run_data = {
        "run_id": run_id,
        "thread_id": thread_id,
        "assistant_id": req.assistant_id,
        "status": "pending",
        "final_output": None,
        "created_at": now_str,
        "updated_at": now_str
    }
    set_run(run_id, run_data)
    
    # Associate active_run_id with thread
    thread["metadata"]["active_run_id"] = run_id
    thread["updated_at"] = now_str
    set_thread(thread_id, thread)
    
    # Extract user_input from input
    user_input = None
    if req.input and isinstance(req.input, dict):
        user_input = req.input.get("user_input")
        
    background_tasks.add_task(_execute_graph_run, thread_id, run_id, req.assistant_id, user_input)
    
    return RunResponseStandard(**run_data)


@app.post("/threads/{thread_id}/runs/stream", dependencies=[Depends(require_auth)])
async def create_run_stream(thread_id: str, req: RunCreateRequest):
    thread = get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
        
    # Concurrency guard
    active_run_id = thread.get("metadata", {}).get("active_run_id")
    if active_run_id:
        active_run = get_run(active_run_id)
        if active_run and active_run.get("status") in ("pending", "running"):
            raise HTTPException(
                status_code=409, 
                detail=f"Thread {thread_id} already has an active run ({active_run_id}) in status {active_run.get('status')}"
            )

    user_input = None
    if req.input and isinstance(req.input, dict):
        user_input = req.input.get("user_input")
        
    # If state is completely empty, we need user_input
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config)
    if not state.values and not user_input:
        raise HTTPException(status_code=422, detail="Thread is empty and no user_input was provided in input")

    run_id = str(uuid.uuid4())
    import datetime
    now_str = datetime.datetime.utcnow().isoformat()
    
    run_data = {
        "run_id": run_id,
        "thread_id": thread_id,
        "assistant_id": req.assistant_id,
        "status": "running",
        "final_output": None,
        "created_at": now_str,
        "updated_at": now_str
    }
    set_run(run_id, run_data)
    
    thread["metadata"]["active_run_id"] = run_id
    thread["updated_at"] = now_str
    set_thread(thread_id, thread)

    async def event_generator() -> AsyncGenerator[dict, None]:
        import json
        import datetime
        import uuid
        graph = get_graph()
        config = {
            "configurable": {
                "thread_id": thread_id,
                "trace_id": run_id
            },
            "run_id": uuid.UUID(safe_uuid(run_id)),
            "callbacks": get_callbacks(trace_id=run_id, session_id=thread_id)
        }
        
        # Build input
        state = graph.get_state(config)
        if state.next:
            initial_input = None
        else:
            if user_input:
                req_run = RunRequest(user_input=user_input)
                initial_input = _build_initial_state(req_run, thread_id)
            else:
                initial_input = None

        try:
            yield {"event": "start", "data": json.dumps({"job_id": thread_id, "run_id": run_id})}

            async for event in graph.astream_events(initial_input, config, version="v2"):
                kind = event.get("event", "")
                name = event.get("name", "")

                TRACKED_NODES = {"planner", "executor", "validator", "memory_retrieval"}

                if kind == "on_chain_start" and name in TRACKED_NODES:
                    yield {
                        "event": "step_start",
                        "data": json.dumps({"node": name, "job_id": thread_id, "run_id": run_id}),
                    }

                elif kind == "on_chain_end" and name in TRACKED_NODES:
                    output = event.get("data", {}).get("output", {})
                    steps = output.get("step_history", [])
                    msg = steps[-1] if steps else f"Completed: {name}"
                    yield {
                        "event": "step_done",
                        "data": json.dumps({"node": name, "message": msg, "job_id": thread_id, "run_id": run_id}),
                    }

                elif kind == "on_chain_error":
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": f"Error in {name}", "job_id": thread_id, "run_id": run_id}),
                    }

            # Final state
            final = graph.get_state(config).values
            set_job(thread_id, final)
            
            status = final.get("status", TaskStatus.COMPLETED)
            requires_human = final.get("requires_human_review", False)
            
            run_data = get_run(run_id)
            if run_data:
                if requires_human:
                    run_data["status"] = "paused"
                elif status == TaskStatus.FAILED:
                    run_data["status"] = "failed"
                else:
                    run_data["status"] = "completed"
                run_data["final_output"] = final.get("final_output")
                run_data["updated_at"] = datetime.datetime.utcnow().isoformat()
                set_run(run_id, run_data)
                
            # Clear active run lock if finished or failed
            if run_data and run_data["status"] in ("completed", "failed"):
                thread_data = get_thread(thread_id)
                if thread_data and thread_data.get("metadata", {}).get("active_run_id") == run_id:
                    thread_data["metadata"]["active_run_id"] = None
                    thread_data["updated_at"] = datetime.datetime.utcnow().isoformat()
                    set_thread(thread_id, thread_data)
                    
            validation = final.get("validation_result") or {}
            payload = json.dumps({
                "job_id": thread_id,
                "run_id": run_id,
                "status": run_data["status"] if run_data else str(status),
                "final_output": (final.get("final_output") or "")[:3000],
                "validation_score": validation.get("score"),
                "step_history": final.get("step_history", []),
            })
            yield {"event": "done", "data": payload}

        except Exception as e:
            run_data = get_run(run_id)
            if run_data:
                run_data["status"] = "failed"
                run_data["final_output"] = f"Execution error: {str(e)}"
                run_data["updated_at"] = datetime.datetime.utcnow().isoformat()
                set_run(run_id, run_data)
            
            thread_data = get_thread(thread_id)
            if thread_data and thread_data.get("metadata", {}).get("active_run_id") == run_id:
                thread_data["metadata"]["active_run_id"] = None
                thread_data["updated_at"] = datetime.datetime.utcnow().isoformat()
                set_thread(thread_id, thread_data)
                
            yield {"event": "error", "data": json.dumps({"error": str(e), "job_id": thread_id, "run_id": run_id})}

    return EventSourceResponse(event_generator())


@app.get("/threads/{thread_id}/runs/{run_id}", response_model=RunResponseStandard, dependencies=[Depends(require_auth)])
async def get_run_endpoint(thread_id: str, run_id: str):
    run_data = get_run(run_id)
    if not run_data or run_data["thread_id"] != thread_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunResponseStandard(**run_data)


@app.post("/threads/{thread_id}/runs/{run_id}/resume", response_model=RunResponseStandard, dependencies=[Depends(require_auth)])
async def resume_run(
    thread_id: str,
    run_id: str,
    req: RunResumeRequest,
    background_tasks: BackgroundTasks
):
    thread = get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
        
    run_data = get_run(run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail="Run not found")
        
    if run_data["status"] != "paused":
        raise HTTPException(status_code=400, detail=f"Run {run_id} is in status {run_data['status']} and cannot be resumed")
        
    # Update state if feedback/approval is provided
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    
    if req.approved is not None:
        try:
            log_hitl_event(trace_id=run_id, event_type="resume", feedback=req.feedback, approved=req.approved)
        except Exception as e:
            logger.warning("api.resume_run_log_hitl_failed", error=str(e))
        if req.approved:
            state_update = {
                "human_feedback": req.feedback or "Approved",
                "requires_human_review": False,
                "approved": True,
                "status": TaskStatus.COMPLETED,
                "step_history": [f"✅ Human approved: {(req.feedback or '')[:60]}"],
            }
        else:
            state_update = {
                "human_feedback": req.feedback or "Rejected",
                "requires_human_review": False,
                "approved": False,
                "status": TaskStatus.NEEDS_RETRY,
                "retry_count": 0,
                "step_history": [f"⚠️ Human rejected: {(req.feedback or '')[:60]}"],
            }
        graph.update_state(config, state_update, as_node="human_review")
        
    # Update run status
    import datetime
    now_str = datetime.datetime.utcnow().isoformat()
    run_data["status"] = "running"
    run_data["updated_at"] = now_str
    set_run(run_id, run_data)
    
    # Associate active run with thread (ensure lock remains)
    thread["metadata"]["active_run_id"] = run_id
    thread["updated_at"] = now_str
    set_thread(thread_id, thread)
    
    # Trigger background execution
    background_tasks.add_task(_execute_graph_run, thread_id, run_id, run_data["assistant_id"])
    
    return RunResponseStandard(**run_data)

