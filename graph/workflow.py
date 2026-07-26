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
import os
import sqlite3
import structlog
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from graph.state import AgentState, TaskStatus
from agents.planner import planner_node
from agents.executor import executor_node
from agents.validator import validator_node, human_review_node
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


# Singleton Checkpointer & Connection
_graph_app = None
_checkpointer = None
_conn = None

def get_checkpointer() -> SqliteSaver:
    global _checkpointer, _conn
    if _checkpointer is None:
        os.makedirs("./data", exist_ok=True)
        db_path = "./data/checkpoints.db"
        _conn = sqlite3.connect(db_path, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL;")
        _checkpointer = SqliteSaver(_conn)
        _checkpointer.setup()
    return _checkpointer

def get_graph():
    global _graph_app
    if _graph_app is None:
        cp = get_checkpointer()
        _graph_app = build_graph(checkpointer=cp)
    return _graph_app
