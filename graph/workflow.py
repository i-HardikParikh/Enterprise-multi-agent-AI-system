"""
graph/workflow.py — LangGraph State Machine

Flow:
    START
      │
    memory_retrieval   ← fetch RAG context + session memory
      │
    planner            ← decompose task into sub-tasks
      │
    executor ◄─────────── loops until all sub-tasks done
      │
    validator          ← LLM-as-judge quality scoring
      │
      ├─ score ≥ 75%  ────► END  ✅
      ├─ score < 75%  ────► planner (retry, max 3x) 🔄
      └─ needs human  ────► human_review ⏸  → END
"""
import threading

import structlog
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, StateGraph
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from agents.executor import executor_node
from agents.planner import planner_node
from agents.validator import human_review_node, validator_node
from graph.state import AgentState, TaskStatus
from memory.vector_store import retrieval_node

logger = structlog.get_logger()

# ── Conditional Edge Functions ────────────────────────────────────────────────

def should_continue_executing(state: AgentState) -> str:
    """After each executor run: loop back or move to validator."""
    sub_tasks = state.get("sub_tasks", [])
    current_idx = state.get("current_task_index", 0)
    status = state.get("status")

    if status == TaskStatus.FAILED:
        return "end"
    if current_idx < len(sub_tasks):
        return "executor"    # more tasks remain → loop
    return "validator"       # all tasks done → validate


def should_retry_or_end(state: AgentState) -> str:
    """After validation: pass / retry / human / fail."""
    status = state.get("status")
    requires_human = state.get("requires_human_review", False)

    if requires_human:
        return "human_review"
    if status == TaskStatus.NEEDS_RETRY:
        logger.info("workflow.retry", retry_count=state.get("retry_count"))
        return "planner"
    return "end"


def after_human_review(state: AgentState) -> str:
    """After human review node runs."""
    if state.get("approved") is False:
        return "planner"
    return "end"

# ── Build Graph ───────────────────────────────────────────────────────────────

def build_graph(checkpointer=None):
    """
    Build and compile the LangGraph workflow.

    Args:
        checkpointer: Pass MemorySaver() for in-memory (default),
                      SqliteSaver for disk persistence.
    Returns:
        Compiled LangGraph app
    """
    builder = StateGraph(AgentState)

    # Nodes
    builder.add_node("memory_retrieval", retrieval_node)
    builder.add_node("planner",          planner_node)
    builder.add_node("executor",         executor_node)
    builder.add_node("validator",        validator_node)
    builder.add_node("human_review",     human_review_node)

    # Entry
    builder.set_entry_point("memory_retrieval")

    # Fixed edges
    builder.add_edge("memory_retrieval", "planner")
    builder.add_edge("planner", "executor")

    # Executor loop
    builder.add_conditional_edges(
        "executor",
        should_continue_executing,
        {
            "executor":  "executor",
            "validator": "validator",
            "end":       END,
        },
    )

    # Validator routing
    builder.add_conditional_edges(
        "validator",
        should_retry_or_end,
        {
            "planner":      "planner",
            "human_review": "human_review",
            "end":          END,
        },
    )

    # Human review routing
    builder.add_conditional_edges(
        "human_review",
        after_human_review,
        {
            "planner": "planner",
            "end":     END,
        },
    )

    cp = checkpointer or get_checkpointer()
    return builder.compile(
        checkpointer=cp,
        interrupt_before=["human_review"],
    )


# Singleton Checkpointer & Connection Pool
_graph_app = None
_checkpointer = None
_pool = None
_checkpointer_lock = threading.Lock()

def get_checkpointer() -> PostgresSaver:
    global _checkpointer, _pool
    if _checkpointer is None:
        with _checkpointer_lock:
            if _checkpointer is None:
                from config import get_settings
                settings = get_settings()
                logger.info("postgres.checkpointer_connecting", db_url=settings.db_url)
                _pool = ConnectionPool(
                    conninfo=settings.db_url,
                    max_size=10,
                    open=True,
                    kwargs={"autocommit": True, "row_factory": dict_row}
                )
                _checkpointer = PostgresSaver(_pool)
                _checkpointer.setup()
    return _checkpointer

def get_graph():
    global _graph_app
    if _graph_app is None:
        cp = get_checkpointer()
        _graph_app = build_graph(checkpointer=cp)
    return _graph_app

graph = get_graph()
