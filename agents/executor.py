"""
agents/executor.py — Executor Agent

Three executor types with specialised prompts:
  - research: web search + RAG retrieval  (deepagents-inspired todo planning, Phase 4)
  - analysis: data analysis + DB queries
  - writer:   synthesis + document generation

Uses ReAct-style prompting compatible with ALL free LLMs
(Groq, Gemini, Ollama — no OpenAI tool-use format required).
"""
import json
import re

import structlog
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from agents.llm_factory import get_llm
from graph.state import AgentState, SubTask, TaskStatus
from tools.db_tool import get_db_tool
from tools.file_tool import get_file_tool
from tools.rag_tool import get_rag_tool
from tools.search_tool import get_search_tool

logger = structlog.get_logger()

# ── ReAct Prompt (works with ALL LLMs including Groq/Gemini/Ollama) ───────────

REACT_SYSTEM = """You are a {agent_role} in an enterprise AI system.

Task: {task_description}

Context from previous agents:
{context}

Retrieved knowledge:
{retrieved_context}

You have access to the following tools:
{tools}

Use this EXACT format:

Thought: Think about what to do next
Action: tool_name
Action Input: the input to the tool
Observation: the result of the tool

Repeat Thought/Action/Action Input/Observation as needed.

When you have the final answer:
Thought: I now have enough information to complete the task
Final Answer: [your complete, detailed answer here]

Tool names available: {tool_names}

Begin!"""

# ── Agent Roles and Tool Sets ─────────────────────────────────────────────────

# ── deepagents-Inspired Planning Prompt (Phase 4, Research only) ─────────────

RESEARCH_PLANNING_SYSTEM = """You are a Research Planning Agent.
Your job is to decompose a research task into 3–5 focused, sequential steps.

For each step, choose the best tool:
  - "web_search" — for current events, statistics, real-time data
  - "rag_search"  — for internal documents, domain-specific knowledge

Return ONLY a valid JSON array. No explanation, no markdown.

Example:
[
  {{"step": 1, "query": "global chip shortage causes 2024", "tool": "web_search"}},
  {{"step": 2, "query": "semiconductor supply chain internal reports", "tool": "rag_search"}},
  {{"step": 3, "query": "TSMC production capacity forecasts 2025", "tool": "web_search"}}
]"""

RESEARCH_SYNTHESIS_SYSTEM = """You are a Research Synthesis Agent.
You have completed a series of research steps. Each step had a query and produced an observation.

Synthesize all observations into a single, coherent, well-structured answer to the original task.
Be specific. Cite findings from different steps where appropriate.
Respond in {output_format} format."""


def _parse_todo_list(text: str) -> list:
    """Extract JSON array from LLM planning response."""
    text = re.sub(r"```(?:json)?", "", text).strip().replace("```", "").strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not parse todo list from planning response: {text[:200]}")


def _run_deepagent_research_executor(
    task: SubTask,
    context: str,
    retrieved_context: str,
    output_format: str,
    config: dict | None = None,
) -> dict:
    """
    deepagents-inspired three-phase research executor (Path B, no deepagents install).

    Phase 1 — Plan (write_todos): LLM produces a structured list of 3–5 research steps.
    Phase 2 — Execute: Each step invokes web_search or rag_search directly, collecting observations.
    Phase 3 — Synthesise: LLM consolidates all observations into the final answer.

    Returns the same dict schema as _run_executor():
        {"task_id", "agent_type", "task_description", "output", "tool_calls"}
    where each tool_calls entry has exactly: {"tool": str, "input": str, "output": str}
    """
    llm = get_llm(temperature=0.0)
    search_tool = get_search_tool()
    rag_tool    = get_rag_tool()
    tool_map    = {"web_search": search_tool, "rag_search": rag_tool}

    # ── Phase 1: Plan ─────────────────────────────────────────────────────────────────
    planning_prompt = ChatPromptTemplate.from_messages([
        ("system", RESEARCH_PLANNING_SYSTEM),
        ("human", "Task: {task_description}\n\nPrior context: {context}\n\nReturn ONLY the JSON todo list."),
    ])
    planning_chain = planning_prompt | llm
    plan_response = planning_chain.invoke(
        {"task_description": task["description"], "context": context or "None"},
        config,
    )
    raw_plan = plan_response.content if hasattr(plan_response, "content") else str(plan_response)
    todos = _parse_todo_list(raw_plan)
    logger.info("deepagent_research.planned", task_id=task["id"], num_todos=len(todos))

    # ── Phase 2: Execute each todo ──────────────────────────────────────────────────
    # tool_calls schema: exactly {"tool": str, "input": str, "output": str}
    # — matches _run_executor() format (lines 117–120) character-for-character.
    tool_calls: list[dict] = []
    observations: list[str] = []

    for todo in todos:
        step_tool_name = todo.get("tool", "web_search")
        step_query     = str(todo.get("query", task["description"]))[:300]
        tool_fn        = tool_map.get(step_tool_name, search_tool)

        try:
            observation = tool_fn.invoke(step_query, config)
        except Exception as e:
            observation = f"Tool error ({step_tool_name}): {e!s}"

        tool_calls.append({
            "tool":   step_tool_name,          # str
            "input":  step_query,              # str, already truncated to 300
            "output": str(observation)[:500],  # str, truncated to 500 — same as _run_executor
        })
        observations.append(f"Step {todo.get('step', '?')} [{step_tool_name}] '{step_query}':\n{observation}")
        logger.info("deepagent_research.step_done", step=todo.get("step"), tool=step_tool_name)

    # ── Phase 3: Synthesise ────────────────────────────────────────────────────────────
    synthesis_prompt = ChatPromptTemplate.from_messages([
        ("system", RESEARCH_SYNTHESIS_SYSTEM),
        ("human", (
            "Original task: {task_description}\n\n"
            "Research observations:\n{observations}\n\n"
            "Prior context from other agents:\n{context}\n\n"
            "Retrieved knowledge:\n{retrieved_context}\n\n"
            "Provide the complete synthesised answer now."
        )),
    ])
    synthesis_chain = synthesis_prompt | llm
    synthesis_response = synthesis_chain.invoke(
        {
            "task_description":  task["description"],
            "observations":      "\n\n".join(observations),
            "context":           context or "None",
            "retrieved_context": retrieved_context or "None",
            "output_format":     output_format,
        },
        config,
    )
    final_output = (
        synthesis_response.content
        if hasattr(synthesis_response, "content")
        else str(synthesis_response)
    )
    logger.info("deepagent_research.synthesised", task_id=task["id"], output_chars=len(final_output))

    return {
        "task_id":          task["id"],
        "agent_type":       "research",
        "task_description": task["description"],
        "output":           final_output,
        "tool_calls":       tool_calls,
    }


EXECUTOR_CONFIG = {
    "research": {
        "role": "Research Executor Agent — gather accurate, relevant information",
        "tools_fn": lambda: [get_search_tool(), get_rag_tool(), *get_file_tool()],
        "temperature": 0.1,
    },
    "analysis": {
        "role": "Analysis Executor Agent — process data and derive insights",
        "tools_fn": lambda: [*get_db_tool(), *get_file_tool()],
        "temperature": 0.0,
    },
    "writer": {
        "role": "Writer Executor Agent — synthesise findings into polished documents",
        "tools_fn": lambda: [*get_file_tool()],
        "temperature": 0.3,
    },
}

# ── Core Executor ─────────────────────────────────────────────────────────────

def _run_executor(agent_type: str, task: SubTask, context: str,
                  retrieved_context: str, output_format: str, config: dict | None = None) -> dict:
    """Run one executor agent using ReAct prompting."""
    cfg = EXECUTOR_CONFIG.get(agent_type, EXECUTOR_CONFIG["research"])
    llm = get_llm(temperature=cfg["temperature"])
    tools = cfg["tools_fn"]()

    # ReAct prompt — compatible with Groq, Gemini, Ollama
    from langchain_core.prompts import PromptTemplate
    prompt = PromptTemplate.from_template(REACT_SYSTEM)

    agent = create_react_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=6,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
        early_stopping_method="generate",
    )

    tool_names = ", ".join(t.name for t in tools)
    tools_desc = "\n".join(f"- {t.name}: {t.description}" for t in tools)

    result = executor.invoke({
        "agent_role": cfg["role"],
        "task_description": task["description"],
        "context": context or "No prior context.",
        "retrieved_context": retrieved_context or "No retrieved documents.",
        "tools": tools_desc,
        "tool_names": tool_names,
        "output_format": output_format,
    }, config)

    tool_calls = []
    for action, observation in result.get("intermediate_steps", []):
        tool_calls.append({
            "tool": getattr(action, "tool", str(action)),
            "input": str(getattr(action, "tool_input", ""))[:300],
            "output": str(observation)[:500],
        })

    return {
        "task_id": task["id"],
        "agent_type": agent_type,
        "task_description": task["description"],
        "output": result.get("output", "No output generated."),
        "tool_calls": tool_calls,
    }


def _run_simple_executor(agent_type: str, task: SubTask, context: str,
                          retrieved_context: str, output_format: str, config: dict | None = None) -> dict:
    """
    Fallback: simple LLM call without tool-use.
    Used when ReAct agent fails (e.g., Ollama small models).
    """
    cfg = EXECUTOR_CONFIG.get(agent_type, EXECUTOR_CONFIG["research"])
    llm = get_llm(temperature=cfg["temperature"])

    prompt = ChatPromptTemplate.from_messages([
        ("system", f"You are a {cfg['role']}. Complete the task thoroughly and accurately."),
        ("human", """Task: {task_description}

Prior context:
{context}

Retrieved knowledge:
{retrieved_context}

Provide a detailed, well-structured response in {output_format} format."""),
    ])

    chain = prompt | llm
    response = chain.invoke({
        "task_description": task["description"],
        "context": context or "No prior context.",
        "retrieved_context": retrieved_context or "No retrieved documents.",
        "output_format": output_format,
    }, config)

    output = response.content if hasattr(response, "content") else str(response)
    return {
        "task_id": task["id"],
        "agent_type": agent_type,
        "task_description": task["description"],
        "output": output,
        "tool_calls": [],
    }

# ── LangGraph Node ────────────────────────────────────────────────────────────

def executor_node(state: AgentState, config: RunnableConfig = None) -> dict:
    """LangGraph node: Executor Agent"""
    sub_tasks = state["sub_tasks"]
    idx = state.get("current_task_index", 0)

    if idx >= len(sub_tasks):
        logger.info("executor_node.all_tasks_done")
        return {
            "status": TaskStatus.COMPLETED,
            "step_history": ["✅ All sub-tasks executed"],
        }

    task = sub_tasks[idx]
    logger.info("executor_node.start", task_id=task["id"], agent_type=task["agent_type"])

    # Build context from previous results
    prior_results = state.get("execution_results", [])
    context = "\n\n".join(
        f"[{r['agent_type'].upper()} — {r['task_description']}]\n{r['output']}"
        for r in prior_results
    )

    try:
        # deepagents-inspired planning layer for research tasks (Phase 4, Path B)
        if task["agent_type"] == "research":
            result = _run_deepagent_research_executor(
                task=task,
                context=context,
                retrieved_context=state.get("retrieved_context") or "",
                output_format=state.get("output_format", "markdown"),
                config=config,
            )
        else:
            # Try ReAct agent first (analysis / writer — unchanged)
            result = _run_executor(
                agent_type=task["agent_type"],
                task=task,
                context=context,
                retrieved_context=state.get("retrieved_context") or "",
                output_format=state.get("output_format", "markdown"),
                config=config,
            )
    except Exception as e:
        logger.warning("executor_node.react_failed_trying_simple", error=str(e))
        try:
            # Fallback to simple LLM call
            result = _run_simple_executor(
                agent_type=task["agent_type"],
                task=task,
                context=context,
                retrieved_context=state.get("retrieved_context") or "",
                output_format=state.get("output_format", "markdown"),
                config=config,
            )
        except Exception as e2:
            logger.error("executor_node.both_failed", error=str(e2))
            updated_tasks = list(sub_tasks)
            updated_tasks[idx] = {**task, "status": TaskStatus.FAILED, "error": str(e2)}
            return {
                "sub_tasks": updated_tasks,
                "current_task_index": idx + 1,
                "error_log": [f"Executor [{task['agent_type']}] failed: {e2!s}"],
                "step_history": [f"❌ Executor [{task['agent_type']}]: {str(e2)[:80]}"],
            }

    updated_tasks = list(sub_tasks)
    updated_tasks[idx] = {**task, "status": TaskStatus.COMPLETED, "result": result["output"]}

    logger.info("executor_node.done", task_id=task["id"])
    return {
        "execution_results": [result],
        "tool_calls_log": result.get("tool_calls", []),
        "sub_tasks": updated_tasks,
        "current_task_index": idx + 1,
        "step_history": [
            f"✅ Executor [{task['agent_type']}]: '{task['description'][:55]}...'"
        ],
    }
