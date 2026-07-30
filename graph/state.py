"""
graph/state.py — LangGraph AgentState

The single shared state object that flows through every node.
All agents read from and write to this TypedDict.
"""
from __future__ import annotations

import operator
from enum import Enum
from typing import Annotated, TypedDict


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
    result:       str | None
    error:        str | None


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
    plan:                str | None
    sub_tasks:           list[SubTask]
    task_dependencies:   dict[str, list[str]]

    # ── Execution ──────────────────────────────────────────────────────────
    # Annotated[..., operator.add] → multiple nodes can append to these lists
    execution_results:   Annotated[list[dict], operator.add]
    current_task_index:  int
    tool_calls_log:      Annotated[list[dict], operator.add]

    # ── Memory / RAG ───────────────────────────────────────────────────────
    retrieved_context:   str | None
    memory_summary:      str | None

    # ── Validation ─────────────────────────────────────────────────────────
    validation_result:   ValidationResult | None
    retry_count:         int

    # ── Output ─────────────────────────────────────────────────────────────
    final_output:        str | None
    output_format:       str        # "markdown" | "json"

    # ── Control Flow ───────────────────────────────────────────────────────
    status:              TaskStatus
    error_log:           Annotated[list[str], operator.add]
    requires_human_review: bool
    human_feedback:      str | None
    approved:            bool | None

    # ── Observability ──────────────────────────────────────────────────────
    step_history:        Annotated[list[str], operator.add]
    total_tokens_used:   int
