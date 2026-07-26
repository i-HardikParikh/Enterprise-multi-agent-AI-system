"""
graph/state.py — LangGraph AgentState

The single shared state object that flows through every node.
All agents read from and write to this TypedDict.
"""
from __future__ import annotations
from typing import TypedDict, Annotated, Optional
from enum import Enum
import operator


class TaskStatus(str, Enum):
    PENDING         = "pending"
    IN_PROGRESS     = "in_progress"
    COMPLETED       = "completed"
    FAILED          = "failed"
    NEEDS_RETRY     = "needs_retry"
    AWAITING_HUMAN  = "awaiting_human"


class SubTask(TypedDict):
    id:           str
    description:  str
    agent_type:   str          # "research" | "analysis" | "writer"
    status:       TaskStatus
    result:       Optional[str]
    error:        Optional[str]


class ValidationResult(TypedDict):
    passed:              bool
    score:               float   # 0.0 – 1.0 weighted
    factual_accuracy:    float
    task_completion:     float
    format_compliance:   float
    feedback:            str
    requires_retry:      bool


class AgentState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────
    user_input:          str
    session_id:          str

    # ── Planning ───────────────────────────────────────────────────────────
    plan:                Optional[str]
    sub_tasks:           list[SubTask]
    task_dependencies:   dict[str, list[str]]

    # ── Execution ──────────────────────────────────────────────────────────
    # Annotated[..., operator.add] → multiple nodes can append to these lists
    execution_results:   Annotated[list[dict], operator.add]
    current_task_index:  int
    tool_calls_log:      Annotated[list[dict], operator.add]

    # ── Memory / RAG ───────────────────────────────────────────────────────
    retrieved_context:   Optional[str]
    memory_summary:      Optional[str]

    # ── Validation ─────────────────────────────────────────────────────────
    validation_result:   Optional[ValidationResult]
    retry_count:         int

    # ── Output ─────────────────────────────────────────────────────────────
    final_output:        Optional[str]
    output_format:       str        # "markdown" | "json"

    # ── Control Flow ───────────────────────────────────────────────────────
    status:              TaskStatus
    error_log:           Annotated[list[str], operator.add]
    requires_human_review: bool
    human_feedback:      Optional[str]
    approved:            Optional[bool]

    # ── Observability ──────────────────────────────────────────────────────
    step_history:        Annotated[list[str], operator.add]
    total_tokens_used:   int
