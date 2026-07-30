"""
agents/planner.py — Planner Agent

Breaks user input into ordered sub-tasks with dependency mapping.
Works with Groq, Gemini, and Ollama.
"""
import uuid
import json
import re
import structlog
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from agents.llm_factory import get_llm
from graph.state import AgentState, SubTask, TaskStatus

logger = structlog.get_logger()

# ── Prompt ────────────────────────────────────────────────────────────────────

PLANNER_SYSTEM = """You are an expert AI Planner Agent in a multi-agent system.

Analyse the user's request and create a structured execution plan.

## Agent Types Available:
- research: Searches web, queries knowledge base, retrieves documents
- analysis: Processes data, runs calculations, compares info, draws insights
- writer:   Synthesises results, formats reports, writes final document

## Rules:
1. Break tasks into 3-5 focused sub-tasks
2. Identify which tasks depend on others
3. research → analysis → writer is the typical flow
4. Keep descriptions clear and specific

## IMPORTANT - Output Format:
Return ONLY a valid JSON object. No explanation, no markdown, no code block.

{
  "reasoning": "Brief explanation of your approach",
  "output_format": "markdown",
  "sub_tasks": [
    {
      "description": "What this task should do",
      "agent_type": "research",
      "depends_on": []
    },
    {
      "description": "Analyse the gathered data",
      "agent_type": "analysis",
      "depends_on": [0]
    },
    {
      "description": "Write the final report",
      "agent_type": "writer",
      "depends_on": [0, 1]
    }
  ]
}"""

PLANNER_HUMAN = """User Request: {user_input}

Prior context: {memory_summary}

Return ONLY the JSON plan, nothing else."""

# ── JSON Parser (robust, handles all LLM output formats) ─────────────────────

def _parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response — handles markdown code blocks, extra text, etc."""
    # Strip markdown code blocks if present
    text = re.sub(r"```(?:json)?", "", text).strip()
    text = text.replace("```", "").strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM response: {text[:300]}")

# ── Node ──────────────────────────────────────────────────────────────────────

def planner_node(state: AgentState, config: RunnableConfig = None) -> dict:
    """LangGraph node: Planner Agent"""
    user_input = state["user_input"]
    if state.get("human_feedback"):
        user_input += f"\n\nHuman feedback on previous attempt: {state['human_feedback']}\nPlease adjust the tasks to address this critique."

    logger.info("planner_node.start", input=user_input[:80])

    llm = get_llm(temperature=0.0)
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=PLANNER_SYSTEM),
        ("human", PLANNER_HUMAN),
    ])
    chain = prompt | llm

    try:
        response = chain.invoke({
            "user_input": user_input,
            "memory_summary": state.get("memory_summary") or "No prior context.",
        }, config)

        raw_text = response.content if hasattr(response, "content") else str(response)
        result = _parse_json_response(raw_text)

        # Build SubTask objects with UUIDs
        sub_tasks: list[SubTask] = []
        id_map: dict[str, str] = {}

        for i, raw_task in enumerate(result.get("sub_tasks", [])):
            task_id = str(uuid.uuid4())[:8]
            id_map[str(i)] = task_id
            sub_tasks.append(SubTask(
                id=task_id,
                description=raw_task["description"],
                agent_type=raw_task.get("agent_type", "research"),
                status=TaskStatus.PENDING,
                result=None,
                error=None,
            ))

        dependencies: dict[str, list[str]] = {}
        for i, raw_task in enumerate(result.get("sub_tasks", [])):
            task_id = id_map[str(i)]
            deps = [id_map[str(d)] for d in raw_task.get("depends_on", []) if str(d) in id_map]
            dependencies[task_id] = deps

        logger.info("planner_node.done", num_tasks=len(sub_tasks))

        return {
            "plan": result.get("reasoning", ""),
            "sub_tasks": sub_tasks,
            "task_dependencies": dependencies,
            "output_format": result.get("output_format", "markdown"),
            "current_task_index": 0,
            "status": TaskStatus.IN_PROGRESS,
            "step_history": [f"✅ Planner: Created {len(sub_tasks)} sub-tasks"],
        }

    except Exception as e:
        logger.error("planner_node.error", error=str(e))
        # Fallback: create a simple 3-task plan so the system doesn't crash
        fallback_tasks = [
            SubTask(id="t1", description=f"Research information about: {state['user_input'][:100]}",
                    agent_type="research", status=TaskStatus.PENDING, result=None, error=None),
            SubTask(id="t2", description="Analyse the gathered information",
                    agent_type="analysis", status=TaskStatus.PENDING, result=None, error=None),
            SubTask(id="t3", description=f"Write a structured report addressing: {state['user_input'][:100]}",
                    agent_type="writer", status=TaskStatus.PENDING, result=None, error=None),
        ]
        return {
            "plan": f"Fallback plan (planner error: {str(e)[:80]})",
            "sub_tasks": fallback_tasks,
            "task_dependencies": {"t1": [], "t2": ["t1"], "t3": ["t1", "t2"]},
            "output_format": "markdown",
            "current_task_index": 0,
            "status": TaskStatus.IN_PROGRESS,
            "error_log": [f"Planner used fallback plan: {str(e)}"],
            "step_history": [f"⚠️ Planner: Used fallback plan ({str(e)[:60]})"],
        }
