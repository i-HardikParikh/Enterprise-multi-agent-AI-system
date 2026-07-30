"""
evals/eval_pipeline.py — LLM-as-Judge Evaluation Pipeline

Evaluates agent outputs on 4 dimensions:
  - Faithfulness      : grounded in retrieved context?
  - Answer Relevance  : answers the original question?
  - Completeness      : all aspects covered?
  - Clarity           : clear and well-structured?

Works with Groq, Gemini, and Ollama.
"""
import json
import re
import time

import structlog
from langchain_core.prompts import ChatPromptTemplate

from agents.llm_factory import get_llm

logger = structlog.get_logger()

# ── Prompt ────────────────────────────────────────────────────────────────────

EVAL_SYSTEM = """You are an expert AI evaluator. Assess output quality honestly and strictly.
Reserve scores above 0.9 for truly excellent outputs.

## Dimensions (0.0 to 1.0):

1. faithfulness — Every claim supported by provided context? Penalise hallucinations heavily.
2. answer_relevance — Directly addresses the user's question? Penalise off-topic content.
3. completeness — All aspects of the request covered? Note any gaps.
4. clarity — Clear, well-structured, easy to understand? Good formatting?

## IMPORTANT — Return ONLY valid JSON:
{
  "faithfulness": {"score": 0.85, "reasoning": "...", "examples": []},
  "answer_relevance": {"score": 0.90, "reasoning": "...", "examples": []},
  "completeness": {"score": 0.80, "reasoning": "...", "examples": []},
  "clarity": {"score": 0.88, "reasoning": "...", "examples": []},
  "summary": "One sentence overall assessment"
}"""

EVAL_HUMAN = """User Question: {user_input}

Retrieved Context (ground truth):
{retrieved_context}

AI Output to Evaluate:
{final_output}

Return ONLY the JSON evaluation."""

# ── JSON Parser ───────────────────────────────────────────────────────────────

def _parse_eval_json(text: str) -> dict:
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
    # Fallback scores
    return {
        "faithfulness":     {"score": 0.7, "reasoning": "Parse error", "examples": []},
        "answer_relevance": {"score": 0.7, "reasoning": "Parse error", "examples": []},
        "completeness":     {"score": 0.7, "reasoning": "Parse error", "examples": []},
        "clarity":          {"score": 0.7, "reasoning": "Parse error", "examples": []},
        "summary": "Evaluation parsing failed — scores are estimates.",
    }

# ── Main Evaluator ────────────────────────────────────────────────────────────

def run_evaluation(
    user_input: str,
    final_output: str,
    retrieved_context: str = "",
    threshold: float = 0.75,
) -> dict:
    """
    Run the full evaluation pipeline.

    Args:
        user_input:        Original user request
        final_output:      Agent's generated output
        retrieved_context: RAG context used during generation
        threshold:         Score below which output is marked failed

    Returns:
        Full evaluation result as dict
    """
    start = time.time()
    logger.info("eval.start")

    llm = get_llm(temperature=0.0)
    prompt = ChatPromptTemplate.from_messages([
        ("system", EVAL_SYSTEM),
        ("human", EVAL_HUMAN),
    ])
    chain = prompt | llm

    try:
        response = chain.invoke({
            "user_input": user_input,
            "retrieved_context": (retrieved_context or "No context provided.")[:3000],
            "final_output": final_output[:4000],
        })

        raw_text = response.content if hasattr(response, "content") else str(response)
        result = _parse_eval_json(raw_text)

        # Weighted overall score
        weights = {
            "faithfulness": 0.35,
            "answer_relevance": 0.35,
            "completeness": 0.20,
            "clarity": 0.10,
        }
        overall = sum(
            result[dim]["score"] * weight
            for dim, weight in weights.items()
            if dim in result
        )
        overall = round(overall, 3)
        elapsed_ms = int((time.time() - start) * 1000)

        final = {
            **result,
            "overall_score": overall,
            "passed": overall >= threshold,
            "latency_ms": elapsed_ms,
        }

        logger.info("eval.done", overall_score=overall, passed=final["passed"])
        return final

    except Exception as e:
        logger.error("eval.error", error=str(e))
        return {
            "error": str(e),
            "overall_score": 0.0,
            "passed": False,
            "latency_ms": int((time.time() - start) * 1000),
        }


# ── Batch Evaluator ───────────────────────────────────────────────────────────

def run_batch_evaluation(test_cases: list[dict]) -> dict:
    """
    Run evaluation on multiple test cases for regression testing.

    Args:
        test_cases: List of dicts — keys: user_input, final_output, retrieved_context

    Returns:
        Aggregated metrics + per-case results
    """
    results = []
    for i, case in enumerate(test_cases):
        logger.info("batch_eval.case", index=i, total=len(test_cases))
        result = run_evaluation(
            user_input=case["user_input"],
            final_output=case.get("final_output", ""),
            retrieved_context=case.get("retrieved_context", ""),
        )
        results.append({"case": i, **result})

    scores = [r["overall_score"] for r in results if "overall_score" in r]
    passed = sum(1 for r in results if r.get("passed", False))

    return {
        "total_cases": len(test_cases),
        "passed": passed,
        "failed": len(test_cases) - passed,
        "pass_rate": round(passed / len(test_cases), 3) if test_cases else 0,
        "avg_score": round(sum(scores) / len(scores), 3) if scores else 0,
        "min_score": round(min(scores), 3) if scores else 0,
        "max_score": round(max(scores), 3) if scores else 0,
        "results": results,
    }
