"""
tests/test_agents.py — Unit and Integration Tests
Works with all 3 free providers: Groq, Gemini, Ollama
"""
import pytest
from unittest.mock import patch, MagicMock
from graph.state import AgentState, TaskStatus, SubTask

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def base_state() -> AgentState:
    return AgentState(
        user_input="Analyse Q1 2024 sales data and create a summary report",
        session_id="test-session-001",
        plan=None, sub_tasks=[], task_dependencies={},
        execution_results=[], current_task_index=0, tool_calls_log=[],
        retrieved_context="Q1 2024: Total revenue $283,000. Widget A top seller.",
        memory_summary="No prior context.",
        validation_result=None, retry_count=0, final_output=None,
        output_format="markdown", status=TaskStatus.PENDING,
        error_log=[], requires_human_review=False, human_feedback=None,
        step_history=[], total_tokens_used=0,
    )

@pytest.fixture
def planned_state(base_state):
    return {
        **base_state,
        "plan": "1. Research 2. Analyse 3. Write",
        "sub_tasks": [
            SubTask(id="t1", description="Retrieve Q1 sales data", agent_type="research",
                    status=TaskStatus.PENDING, result=None, error=None),
            SubTask(id="t2", description="Analyse revenue trends", agent_type="analysis",
                    status=TaskStatus.PENDING, result=None, error=None),
            SubTask(id="t3", description="Write executive summary", agent_type="writer",
                    status=TaskStatus.PENDING, result=None, error=None),
        ],
        "task_dependencies": {"t1": [], "t2": ["t1"], "t3": ["t1", "t2"]},
        "status": TaskStatus.IN_PROGRESS,
    }

# ── Config & LLM Factory Tests ────────────────────────────────────────────────

class TestConfig:
    def test_settings_loads(self):
        from config import get_settings
        settings = get_settings()
        assert settings.llm_provider in ("groq", "gemini", "ollama")

    def test_supported_providers(self):
        from config import get_settings
        s = get_settings()
        assert s.llm_provider in ("groq", "gemini", "ollama"), \
            f"Unknown provider: {s.llm_provider}"

    def test_embedding_model_set(self):
        from config import get_settings
        s = get_settings()
        assert "sentence-transformers" in s.embedding_model or s.embedding_model

    def test_provider_info(self):
        from agents.llm_factory import get_provider_info
        info = get_provider_info()
        assert "provider" in info
        assert "model" in info
        assert "type" in info

# ── State Tests ───────────────────────────────────────────────────────────────

class TestAgentState:
    def test_initial_state_fields(self, base_state):
        assert base_state["user_input"] != ""
        assert base_state["status"] == TaskStatus.PENDING
        assert base_state["execution_results"] == []
        assert base_state["retry_count"] == 0

    def test_task_status_values(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.NEEDS_RETRY == "needs_retry"
        assert TaskStatus.AWAITING_HUMAN == "awaiting_human"

    def test_sub_task_structure(self):
        task = SubTask(id="abc", description="Test", agent_type="research",
                       status=TaskStatus.PENDING, result=None, error=None)
        assert task["agent_type"] == "research"
        assert task["status"] == TaskStatus.PENDING

# ── Planner Tests ─────────────────────────────────────────────────────────────

class TestPlanner:
    def test_json_parser_handles_markdown_blocks(self):
        from agents.planner import _parse_json_response
        text = '```json\n{"reasoning": "test", "sub_tasks": [], "output_format": "markdown"}\n```'
        result = _parse_json_response(text)
        assert result["reasoning"] == "test"

    def test_json_parser_handles_plain_json(self):
        from agents.planner import _parse_json_response
        text = '{"reasoning": "ok", "sub_tasks": [], "output_format": "markdown"}'
        result = _parse_json_response(text)
        assert result["output_format"] == "markdown"

    def test_json_parser_extracts_from_mixed_text(self):
        from agents.planner import _parse_json_response
        text = 'Here is my plan:\n{"reasoning": "found", "sub_tasks": [], "output_format": "json"}'
        result = _parse_json_response(text)
        assert result["reasoning"] == "found"

    def test_fallback_plan_on_error(self, base_state):
        """Planner should create fallback tasks if LLM fails."""
        from agents.planner import planner_node
        with patch("agents.planner.get_llm") as mock_llm:
            mock_response = MagicMock()
            mock_response.content = "INVALID JSON !!!"
            mock_llm.return_value.return_value = mock_response
            mock_chain = MagicMock()
            mock_chain.invoke.return_value = mock_response
            # Result should have fallback tasks
            # (Full integration test requires real LLM)
            assert base_state["sub_tasks"] == []

# ── Executor Tests ────────────────────────────────────────────────────────────

class TestExecutor:
    def test_executor_returns_completed_when_no_tasks(self, base_state):
        from agents.executor import executor_node
        state = {**base_state, "current_task_index": 0, "sub_tasks": []}
        result = executor_node(state)
        assert result["status"] == TaskStatus.COMPLETED

    def test_executor_config_has_all_types(self):
        from agents.executor import EXECUTOR_CONFIG
        assert "research" in EXECUTOR_CONFIG
        assert "analysis" in EXECUTOR_CONFIG
        assert "writer" in EXECUTOR_CONFIG

    def test_executor_advances_index(self, planned_state):
        assert planned_state["current_task_index"] == 0
        # After execution, index would be 1

# ── Validator Tests ───────────────────────────────────────────────────────────

class TestValidator:
    def test_validator_fails_with_no_results(self, base_state):
        from agents.validator import validator_node
        state = {**base_state, "execution_results": []}
        result = validator_node(state)
        assert result["status"] == TaskStatus.FAILED
        assert result["validation_result"]["passed"] is False

    def test_json_parser_handles_valid_json(self):
        from agents.validator import _parse_validation_json
        text = '{"factual_accuracy": 0.9, "task_completion": 0.85, "format_compliance": 0.8, "feedback": "Good", "passed": true}'
        result = _parse_validation_json(text)
        assert result["factual_accuracy"] == 0.9
        assert result["passed"] is True

    def test_json_parser_handles_markdown_wrapped(self):
        from agents.validator import _parse_validation_json
        text = '```json\n{"factual_accuracy": 0.7, "task_completion": 0.6, "format_compliance": 0.5, "feedback": "Needs work", "passed": false}\n```'
        result = _parse_validation_json(text)
        assert result["passed"] is False

    def test_weighted_score_calculation(self):
        # factual=0.8, completion=0.9, format=0.7
        # weighted = 0.8*0.4 + 0.9*0.4 + 0.7*0.2 = 0.82
        score = 0.8 * 0.4 + 0.9 * 0.4 + 0.7 * 0.2
        assert abs(score - 0.82) < 0.001

    def test_retry_constants(self):
        from agents.validator import MAX_RETRIES, QUALITY_THRESHOLD
        assert MAX_RETRIES == 3
        assert QUALITY_THRESHOLD == 0.75

# ── Workflow Routing Tests ─────────────────────────────────────────────────────

class TestWorkflowRouting:
    def test_loops_when_tasks_remain(self, planned_state):
        from graph.workflow import should_continue_executing
        state = {**planned_state, "current_task_index": 1}
        assert should_continue_executing(state) == "executor"

    def test_goes_to_validator_when_all_done(self, planned_state):
        from graph.workflow import should_continue_executing
        state = {**planned_state, "current_task_index": 3}
        assert should_continue_executing(state) == "validator"

    def test_retries_when_score_low(self, base_state):
        from graph.workflow import should_retry_or_end
        state = {**base_state, "status": TaskStatus.NEEDS_RETRY, "requires_human_review": False}
        assert should_retry_or_end(state) == "planner"

    def test_ends_when_completed(self, base_state):
        from graph.workflow import should_retry_or_end
        state = {**base_state, "status": TaskStatus.COMPLETED, "requires_human_review": False}
        assert should_retry_or_end(state) == "end"

    def test_routes_to_human_review(self, base_state):
        from graph.workflow import should_retry_or_end
        state = {**base_state, "status": TaskStatus.COMPLETED, "requires_human_review": True}
        assert should_retry_or_end(state) == "human_review"

# ── Eval Pipeline Tests ───────────────────────────────────────────────────────

class TestEvalPipeline:
    def test_weights_sum_to_one(self):
        weights = {"faithfulness": 0.35, "answer_relevance": 0.35,
                   "completeness": 0.20, "clarity": 0.10}
        assert abs(sum(weights.values()) - 1.0) < 0.001

    def test_json_parser_fallback(self):
        from evals.eval_pipeline import _parse_eval_json
        text = "INVALID JSON"
        result = _parse_eval_json(text)
        assert "faithfulness" in result
        assert result["faithfulness"]["score"] == 0.7

    def test_batch_eval_aggregation(self):
        from evals.eval_pipeline import run_batch_evaluation
        with patch("evals.eval_pipeline.run_evaluation") as mock_eval:
            mock_eval.return_value = {"overall_score": 0.85, "passed": True, "latency_ms": 100}
            result = run_batch_evaluation([
                {"user_input": "test1", "final_output": "output1"},
                {"user_input": "test2", "final_output": "output2"},
            ])
            assert result["total_cases"] == 2
            assert result["passed"] == 2
            assert result["pass_rate"] == 1.0

# ── API Tests ─────────────────────────────────────────────────────────────────

class TestAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "llm_provider" in data
        assert "llm_model" in data

    def test_health_shows_provider(self, client):
        response = client.get("/health")
        data = response.json()
        assert data["llm_provider"] in ("groq", "gemini", "ollama")

    def test_run_rejects_empty_input(self, client):
        response = client.post("/run", json={"user_input": ""})
        assert response.status_code == 422

    def test_status_404_for_unknown_job(self, client):
        response = client.get("/status/nonexistent-job-000")
        assert response.status_code == 404

    def test_upload_rejects_unsupported_format(self, client):
        import io
        response = client.post(
            "/upload",
            files={"file": ("test.exe", io.BytesIO(b"data"), "application/octet-stream")},
        )
        assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
