"""
agents/validator.py — Validator Agent (LLM-as-Judge)

Scores output on 3 axes:
  1. Factual accuracy  — grounded in retrieved context?
  2. Task completion   — answers everything user asked?
  3. Format compliance — correct format/structure?

Triggers retry if score < 0.75 and retries < MAX_RETRIES.
Works with Groq, Gemini, and Ollama.
"""
import json
import re
import structlog

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from agents.llm_factory import get_llm
from graph.state import AgentState, TaskStatus, ValidationResult

logger = structlog.get_logger()

QUALITY_THRESHOLD = 0.75
MAX_RETRIES = 3

# ── Prompt ────────────────────────────────────────────────────────────────────

VALIDATOR_SYSTEM = """You are a senior Quality Assurance AI Agent.
Evaluate the AI-generated output strictly and honestly.

## Scoring Criteria (each 0.0 to 1.0):

1. factual_accuracy — Is every claim supported by the retrieved context?
   Penalise hallucinations and unsupported statistics heavily.

2. task_completion — Does output fully address the user's original request?
   Penalise missing points or off-topic content.

3. format_compliance — Is output in the requested format with good structure?
   Check: logical flow, proper headings, appropriate length.

## Score Guide:
0.9-1.0 = Excellent | 0.7-0.9 = Good | 0.5-0.7 = Needs work | <0.5 = Unacceptable

Set passed=true if average score >= 0.75

## IMPORTANT — Return ONLY valid JSON, nothing else:
{
  "factual_accuracy": 0.85,
  "task_completion": 0.90,
  "format_compliance": 0.80,
  "feedback": "Specific actionable feedback here",
  "passed": true
}"""

VALIDATOR_HUMAN = """User Request: {user_input}

Retrieved Context (ground truth):
{retrieved_context}

Output to Evaluate:
{final_output}

Requested Format: {output_format}

Return ONLY the JSON evaluation."""

# ── JSON Parser ───────────────────────────────────────────────────────────────

def _parse_validation_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text).strip().replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    # Last resort: extract numbers with regex
    def extract(key):
        m = re.search(rf'"{key}"\s*:\s*([\d.]+)', text)
        return float(m.group(1)) if m else 0.7
    passed_match = re.search(r'"passed"\s*:\s*(true|false)', text, re.IGNORECASE)
    return {
        "factual_accuracy": extract("factual_accuracy"),
        "task_completion": extract("task_completion"),
        "format_compliance": extract("format_compliance"),
        "feedback": "Could not parse detailed feedback.",
        "passed": passed_match.group(1).lower() == "true" if passed_match else True,
    }

# ── Node ──────────────────────────────────────────────────────────────────────

def validator_node(state: AgentState, config: RunnableConfig = None) -> dict:
    """LangGraph node: Validator Agent"""
    logger.info("validator_node.start", retry_count=state.get("retry_count", 0))

    results = state.get("execution_results", [])
    if not results:
        return {
            "validation_result": ValidationResult(
                passed=False, score=0.0,
                factual_accuracy=0.0, task_completion=0.0, format_compliance=0.0,
                feedback="No execution results found.", requires_retry=True,
            ),
            "status": TaskStatus.FAILED,
            "step_history": ["❌ Validator: No results to validate"],
        }

    # Use writer output if available, else last result
    writer_results = [r for r in results if r.get("agent_type") == "writer"]
    primary_output = writer_results[-1]["output"] if writer_results else results[-1]["output"]

    llm = get_llm(temperature=0.0)
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=VALIDATOR_SYSTEM),
        ("human", VALIDATOR_HUMAN),
    ])
    chain = prompt | llm

    try:
        response = chain.invoke({
            "user_input": state["user_input"],
            "retrieved_context": (state.get("retrieved_context") or "Not available")[:2000],
            "final_output": primary_output[:4000],
            "output_format": state.get("output_format", "markdown"),
        }, config)

        raw_text = response.content if hasattr(response, "content") else str(response)
        eval_result = _parse_validation_json(raw_text)

        # Weighted score
        score = round(
            eval_result["factual_accuracy"] * 0.4 +
            eval_result["task_completion"] * 0.4 +
            eval_result["format_compliance"] * 0.2,
            3
        )

        retry_count = state.get("retry_count", 0)

        # Log to Langfuse
        try:
            trace_id = None
            if config:
                trace_id = config.get("configurable", {}).get("trace_id") or config.get("configurable", {}).get("thread_id")
            if not trace_id:
                trace_id = state.get("session_id")
            
            from graph.observability import log_validation_score
            log_validation_score(
                trace_id=trace_id,
                accuracy=eval_result["factual_accuracy"],
                completion=eval_result["task_completion"],
                compliance=eval_result["format_compliance"],
                overall=score,
                passed=eval_result["passed"],
                retry_count=retry_count
            )
        except Exception as le:
            logger.warning("validator_node.langfuse_log_failed", error=str(le))

        requires_retry = not eval_result["passed"] and retry_count < MAX_RETRIES

        validation = ValidationResult(
            passed=eval_result["passed"],
            score=score,
            factual_accuracy=eval_result["factual_accuracy"],
            task_completion=eval_result["task_completion"],
            format_compliance=eval_result["format_compliance"],
            feedback=eval_result.get("feedback", ""),
            requires_retry=requires_retry,
        )

        requires_human = not eval_result["passed"] and not requires_retry

        new_status = (
            TaskStatus.COMPLETED if eval_result["passed"]
            else TaskStatus.NEEDS_RETRY if requires_retry
            else TaskStatus.AWAITING_HUMAN
        )

        score_pct = round(score * 100, 1)
        step_msg = (
            f"✅ Validator: {score_pct}% — PASSED"
            if eval_result["passed"]
            else f"⚠️ Validator: {score_pct}% — {'RETRY #'+str(retry_count+1) if requires_retry else 'AWAITING HUMAN REVIEW'}"
        )

        logger.info("validator_node.done", score=score, passed=eval_result["passed"])

        return {
            "validation_result": validation,
            "final_output": primary_output,
            "status": new_status,
            "retry_count": retry_count + (1 if requires_retry else 0),
            "requires_human_review": requires_human,
            "step_history": [step_msg],
        }

    except Exception as e:
        logger.error("validator_node.error", error=str(e))
        p_out = primary_output if "primary_output" in locals() else ""
        validation = ValidationResult(
            passed=False,
            score=0.0,
            factual_accuracy=0.0,
            task_completion=0.0,
            format_compliance=0.0,
            feedback=f"Validator crashed: {str(e)}",
            requires_retry=False,
        )
        return {
            "validation_result": validation,
            "error_log": [f"Validator error: {str(e)}"],
            "final_output": p_out,
            "status": TaskStatus.AWAITING_HUMAN,
            "requires_human_review": True,
            "step_history": [f"⚠️ Validator crashed — routing to human review: {str(e)[:60]}"],
        }


# ── Human-in-the-Loop Node ────────────────────────────────────────────────────

def human_review_node(state: AgentState) -> dict:
    """LangGraph node: pause for human feedback."""
    human_feedback = state.get("human_feedback")
    approved = state.get("approved")

    if human_feedback is not None:
        if approved is False:
            return {
                "status": TaskStatus.NEEDS_RETRY,
                "step_history": [f"⚠️ Human rejected: {human_feedback[:60]}"],
                "requires_human_review": False,
                "retry_count": 0,  # Reset retry counter for new iteration
            }
        return {
            "status": TaskStatus.COMPLETED,
            "step_history": [f"✅ Human approved: {human_feedback[:60]}"],
            "requires_human_review": False,
        }
    return {
        "status": TaskStatus.AWAITING_HUMAN,
        "requires_human_review": True,
        "step_history": ["⏸️ Awaiting human review..."],
    }
