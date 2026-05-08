"""
agents/executor.py — Executor Agent

Three executor types with specialised prompts:
  - research: web search + RAG retrieval
  - analysis: data analysis + DB queries
  - writer:   synthesis + document generation

Uses ReAct-style prompting compatible with ALL free LLMs
(Groq, Gemini, Ollama — no OpenAI tool-use format required).
"""
import structlog
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.agents import AgentExecutor, create_react_agent

from agents.llm_factory import get_llm
from graph.state import AgentState, TaskStatus, SubTask
from tools.search_tool import get_search_tool
from tools.rag_tool import get_rag_tool
from tools.db_tool import get_db_tool
from tools.file_tool import get_file_tool

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
                  retrieved_context: str, output_format: str) -> dict:
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
    })

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
                          retrieved_context: str, output_format: str) -> dict:
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
    })

    output = response.content if hasattr(response, "content") else str(response)
    return {
        "task_id": task["id"],
        "agent_type": agent_type,
        "task_description": task["description"],
        "output": output,
        "tool_calls": [],
    }

# ── LangGraph Node ────────────────────────────────────────────────────────────

def executor_node(state: AgentState) -> dict:
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
        # Try ReAct agent first
        result = _run_executor(
            agent_type=task["agent_type"],
            task=task,
            context=context,
            retrieved_context=state.get("retrieved_context") or "",
            output_format=state.get("output_format", "markdown"),
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
            )
        except Exception as e2:
            logger.error("executor_node.both_failed", error=str(e2))
            updated_tasks = list(sub_tasks)
            updated_tasks[idx] = {**task, "status": TaskStatus.FAILED, "error": str(e2)}
            return {
                "sub_tasks": updated_tasks,
                "current_task_index": idx + 1,
                "error_log": [f"Executor [{task['agent_type']}] failed: {str(e2)}"],
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
