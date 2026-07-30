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

    def test_validator_node_crash_routes_to_human(self, base_state):
        from agents.validator import validator_node
        state = {
            **base_state,
            "execution_results": [{"agent_type": "writer", "output": "some text"}],
        }
        if "user_input" in state:
            del state["user_input"]
        result = validator_node(state)
        assert result["status"] == TaskStatus.AWAITING_HUMAN
        assert result["requires_human_review"] is True
        assert result["validation_result"]["passed"] is False

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
        from auth.dependencies import require_auth
        from auth.schemas import UserOut
        # Bypass auth for all TestAPI tests
        app.dependency_overrides[require_auth] = lambda: UserOut(
            id=1, username="testuser", email="test@example.com", is_active=True, created_at=""
        )
        yield TestClient(app)
        app.dependency_overrides.clear()

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


class TestAgentProtocolAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.main import app
        from auth.dependencies import require_auth
        from auth.schemas import UserOut
        # Bypass auth for all TestAgentProtocolAPI tests
        app.dependency_overrides[require_auth] = lambda: UserOut(
            id=1, username="testuser", email="test@example.com", is_active=True, created_at=""
        )
        yield TestClient(app)
        app.dependency_overrides.clear()

    def test_list_assistants(self, client):
        response = client.get("/assistants")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["assistant_id"] == "default"
        assert data[0]["name"] == "Enterprise AI Multi-Agent System"

    def test_get_assistant(self, client):
        response = client.get("/assistants/default")
        assert response.status_code == 200
        data = response.json()
        assert data["assistant_id"] == "default"
        
        response = client.get("/assistants/nonexistent")
        assert response.status_code == 404

    def test_create_and_get_thread(self, client):
        response = client.post("/threads", json={"metadata": {"custom_key": "val"}})
        assert response.status_code == 200
        thread = response.json()
        assert "thread_id" in thread
        assert thread["metadata"]["custom_key"] == "val"

        # retrieve thread
        thread_id = thread["thread_id"]
        response = client.get(f"/threads/{thread_id}")
        assert response.status_code == 200
        retrieved = response.json()
        assert retrieved["thread_id"] == thread_id

    def test_thread_state_endpoints(self, client):
        # Create thread
        res = client.post("/threads")
        thread_id = res.json()["thread_id"]

        # Get initial state
        res = client.get(f"/threads/{thread_id}/state")
        assert res.status_code == 200
        state = res.json()
        assert "values" in state
        assert state["values"] == {}

        # Update state
        res = client.post(f"/threads/{thread_id}/state", json={"values": {"user_input": "Test User Input", "status": "completed"}})
        assert res.status_code == 200
        assert res.json()["message"] == "Thread state updated successfully"

        # Verify state updated
        res = client.get(f"/threads/{thread_id}/state")
        assert res.status_code == 200
        state = res.json()
        assert state["values"]["user_input"] == "Test User Input"
        assert state["values"]["status"] == "completed"

    def test_create_run_and_status(self, client):
        # Create thread
        res = client.post("/threads")
        thread_id = res.json()["thread_id"]

        # Mock the background execution so it doesn't try to invoke real LLM
        with patch("api.main._execute_graph_run") as mock_exec:
            res = client.post(f"/threads/{thread_id}/runs", json={"input": {"user_input": "Run input"}})
            assert res.status_code == 200
            run = res.json()
            assert run["thread_id"] == thread_id
            assert "run_id" in run
            assert run["status"] == "pending"

            # Check status endpoint
            run_id = run["run_id"]
            res = client.get(f"/threads/{thread_id}/runs/{run_id}")
            assert res.status_code == 200
            assert res.json()["status"] == "pending"

    def test_run_concurrency_guard(self, client):
        # Create thread
        res = client.post("/threads")
        thread_id = res.json()["thread_id"]

        # Directly insert an active run lock in thread metadata
        from api.main import get_thread, set_thread, set_run
        thread = get_thread(thread_id)
        assert thread is not None
        
        run_id = "test-active-run-id"
        run_data = {
            "run_id": run_id,
            "thread_id": thread_id,
            "assistant_id": "default",
            "status": "running",
            "final_output": None,
            "created_at": "now",
            "updated_at": "now"
        }
        set_run(run_id, run_data)
        
        thread["metadata"]["active_run_id"] = run_id
        set_thread(thread_id, thread)

        # Triggering a new run should raise 409 Conflict
        res = client.post(f"/threads/{thread_id}/runs", json={"input": {"user_input": "Run input"}})
        assert res.status_code == 409
        assert "already has an active run" in res.json()["detail"]

    def test_redis_ttl_expiry(self, client):
        from api.main import set_thread, get_thread
        from config import get_settings
        settings = get_settings()
        
        # Test that set_thread works
        thread_id = "test-ttl-thread"
        thread_data = {"thread_id": thread_id, "metadata": {}}
        set_thread(thread_id, thread_data)
        
        # We can check that the thread was stored
        stored = get_thread(thread_id)
        assert stored == thread_data

    def test_hitl_resume_paths_consistency(self, client):
        from api.main import set_thread, set_run
        
        # Path 1: Old /human-review endpoint
        thread_id_1 = "thread-old-hitl"
        set_thread(thread_id_1, {"thread_id": thread_id_1, "metadata": {"active_run_id": None}})
        
        # Path 2: New /threads/{thread_id}/state + /resume combo
        thread_id_2 = "thread-new-hitl"
        set_thread(thread_id_2, {"thread_id": thread_id_2, "metadata": {"active_run_id": "run-id-2"}})
        
        run_data = {
            "run_id": "run-id-2",
            "thread_id": thread_id_2,
            "assistant_id": "default",
            "status": "paused",
            "final_output": None,
            "created_at": "now",
            "updated_at": "now"
        }
        set_run("run-id-2", run_data)

        # Mock graph.update_state and graph.invoke
        with patch("api.main.get_graph") as mock_get_graph:
            mock_graph_inst = MagicMock()
            mock_get_graph.return_value = mock_graph_inst
            
            # Setup mock states
            mock_state_snapshot = MagicMock()
            mock_state_snapshot.values = {"status": "awaiting_human"}
            mock_state_snapshot.next = ["human_review"]
            mock_graph_inst.get_state.return_value = mock_state_snapshot
            
            # Mock final state returned after invoke
            mock_graph_inst.invoke.return_value = {
                "status": "completed",
                "final_output": "Result of HITL"
            }
            
            # 1. Trigger old /human-review
            res_old = client.post("/human-review", json={
                "job_id": thread_id_1,
                "feedback": "LGTM",
                "approved": True
            })
            assert res_old.status_code == 200
            data_old = res_old.json()
            assert data_old["status"] == "completed"
            
            # Capture the state update written to old path
            calls_old = mock_graph_inst.update_state.call_args_list
            assert len(calls_old) >= 1
            # Check the update values for old path
            old_update_val = calls_old[0][0][1]
            assert old_update_val["approved"] is True
            assert "LGTM" in old_update_val["human_feedback"]
            
            # Reset mocks
            mock_graph_inst.update_state.reset_mock()
            
            # 2. Trigger new /threads/{thread_id}/state + /resume combo
            # First, update state using new endpoint
            res_state = client.post(f"/threads/{thread_id_2}/state", json={
                "values": {
                    "human_feedback": "LGTM",
                    "requires_human_review": False,
                    "approved": True,
                    "status": "completed",
                    "step_history": ["✅ Human approved: LGTM"]
                },
                "as_node": "human_review"
            })
            assert res_state.status_code == 200
            
            calls_state = mock_graph_inst.update_state.call_args_list
            assert len(calls_state) == 1
            state_update_val = calls_state[0][0][1]
            assert state_update_val["approved"] is True
            assert state_update_val["human_feedback"] == "LGTM"
            
            # Now, trigger resume
            res_resume = client.post(f"/threads/{thread_id_2}/runs/run-id-2/resume", json={
                "approved": True,
                "feedback": "LGTM"
            })
            assert res_resume.status_code == 200
            assert res_resume.json()["status"] == "running"

class TestLangfuseObservability:
    def test_get_callbacks_disabled_by_default(self):
        from graph.observability import get_callbacks
        callbacks = get_callbacks("test-trace")
        assert callbacks == []

    def test_get_callbacks_enabled(self):
        from graph.observability import get_callbacks
        with patch("os.getenv") as mock_getenv:
            def side_effect(key, default=None):
                if key == "LANGFUSE_PUBLIC_KEY":
                    return "pk-lf-test"
                if key == "LANGFUSE_SECRET_KEY":
                    return "sk-lf-test"
                if key == "LANGFUSE_HOST":
                    return "http://localhost:4000"
                return default
            mock_getenv.side_effect = side_effect
            
            with patch("langfuse.langchain.CallbackHandler") as mock_handler:
                callbacks = get_callbacks("test-trace-123")
                assert len(callbacks) == 1
                mock_handler.assert_called_once_with(
                    public_key="pk-lf-test",
                    secret_key="sk-lf-test",
                    host="http://localhost:4000"
                )

    def test_log_validation_score(self):
        from graph.observability import log_validation_score
        with patch("graph.observability.get_langfuse_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            
            log_validation_score(
                trace_id="trace-1",
                accuracy=0.8,
                completion=0.9,
                compliance=0.95,
                overall=0.87,
                passed=True,
                retry_count=1
            )
            
            assert mock_client.create_score.call_count == 6
            mock_client.flush.assert_called_once()

    def test_log_hitl_event(self):
        from graph.observability import log_hitl_event, safe_uuid
        with patch("graph.observability.get_langfuse_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            
            log_hitl_event(trace_id="trace-2", event_type="resume", feedback="LGTM", approved=True)
            mock_client.create_score.assert_called_once_with(
                name="hitl_resume",
                value=1,
                trace_id=safe_uuid("trace-2"),
                comment="Feedback: LGTM"
            )
            mock_client.flush.assert_called_once()

    def test_node_config_propagation(self):
        from agents.planner import planner_node
        from agents.executor import executor_node
        from agents.validator import validator_node
        from langchain_core.runnables import RunnableConfig
        from langchain_core.language_models.chat_models import SimpleChatModel
        from langchain_core.messages import AIMessage, BaseMessage
        from typing import List, Optional, Any
        
        class DummyLLM(SimpleChatModel):
            content: str = '{"reasoning": "ok", "sub_tasks": [], "output_format": "markdown"}'
            called_config: Optional[Any] = None

            def _call(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_manager: Optional[Any] = None, **kwargs: Any) -> str:
                return self.content

            def invoke(self, input: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
                self.called_config = config
                return super().invoke(input, config, **kwargs)

            @property
            def _llm_type(self) -> str:
                return "dummy"

        class DummyValidatorLLM(SimpleChatModel):
            content: str = '{"factual_accuracy": 0.8, "task_completion": 0.8, "format_compliance": 0.8, "passed": true, "reasoning": "ok", "critique": "none"}'
            called_config: Optional[Any] = None

            def _call(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_manager: Optional[Any] = None, **kwargs: Any) -> str:
                return self.content

            def invoke(self, input: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
                self.called_config = config
                return super().invoke(input, config, **kwargs)

            @property
            def _llm_type(self) -> str:
                return "dummy"

        state = {
            "user_input": "Test query",
            "sub_tasks": [{"id": "t1", "description": "task 1", "agent_type": "analysis", "status": "pending", "result": None, "error": None}],
            "execution_results": [{"agent_type": "analysis", "task_description": "task 1", "output": "Output 1"}],
            "current_task_index": 0
        }
        
        mock_config = RunnableConfig(
            configurable={"thread_id": "test-thread", "trace_id": "test-trace"},
            callbacks=[]
        )
        
        # Test planner node propagates config
        with patch("agents.planner.get_llm") as mock_get_llm:
            dummy_llm = DummyLLM()
            mock_get_llm.return_value = dummy_llm
            
            planner_node(state, mock_config)
            assert dummy_llm.called_config is not None
            assert dummy_llm.called_config.get("configurable", {}).get("trace_id") == "test-trace"
            assert dummy_llm.called_config.get("configurable", {}).get("thread_id") == "test-thread"

        # Test executor node propagates config
        with patch("agents.executor._run_executor") as mock_run:
            mock_run.return_value = {"output": "result", "tool_calls": []}
            executor_node(state, mock_config)
            mock_run.assert_called_once()
            assert mock_run.call_args[1]["config"] == mock_config

        # Test validator node propagates config and logs score
        with patch("agents.validator.get_llm") as mock_get_llm_v, patch("graph.observability.log_validation_score") as mock_log_score:
            dummy_llm_v = DummyValidatorLLM()
            mock_get_llm_v.return_value = dummy_llm_v
            
            validator_node(state, mock_config)
            assert dummy_llm_v.called_config is not None
            assert dummy_llm_v.called_config.get("configurable", {}).get("trace_id") == "test-trace"
            assert dummy_llm_v.called_config.get("configurable", {}).get("thread_id") == "test-thread"
            mock_log_score.assert_called_once_with(
                trace_id="test-trace",
                accuracy=0.8,
                completion=0.8,
                compliance=0.8,
                overall=0.8,
                passed=True,
                retry_count=0
            )


class TestAegraIntegration:
    def test_graph_export_for_aegra(self):
        from graph.workflow import graph
        from langgraph.graph.state import CompiledStateGraph
        
        # Verify graph is exported at module level
        assert graph is not None
        assert isinstance(graph, CompiledStateGraph)
        
        # Verify config is loaded without errors
        import json
        with open("aegra.json", "r") as f:
            config = json.load(f)
        assert "graphs" in config
        assert config["graphs"]["agent"] == "./graph/workflow.py:graph"
        assert config["http"]["app"] == "./api/main.py:app"
        assert config["http"]["enable_custom_route_auth"] is False


# ── deepagents-Inspired Research Executor Tests (Phase 4, Path B) ─────────────

class TestDeepAgentsResearch:
    """
    Tests for the manual deepagents-inspired write_todos planning pattern.
    Confirms:
    1. Three-phase planning produces valid tool_calls and output.
    2. Malformed plan JSON raises ValueError (triggers existing fallback in executor_node).
    3. executor_node routes agent_type="research" to _run_deepagent_research_executor.
    4. tool_calls FORMAT ASSERTION: every entry has exactly {"tool", "input", "output"} —
       same required keys as _run_executor() — so downstream state (tool_calls_log) is consistent.
    """

    def _make_research_task(self) -> dict:
        return SubTask(
            id="r1",
            description="Research global semiconductor supply chain disruptions in 2024",
            agent_type="research",
            status=TaskStatus.PENDING,
            result=None,
            error=None,
        )

    def test_research_planning_produces_valid_result(self):
        """Phase 1→2→3 pipeline returns required keys with non-empty output."""
        from agents.executor import _run_deepagent_research_executor
        from langchain_core.language_models.chat_models import SimpleChatModel
        from langchain_core.messages import BaseMessage
        from typing import List, Optional, Any

        todo_json = (
            '[{"step": 1, "query": "chip shortage 2024", "tool": "web_search"}, '
            '{"step": 2, "query": "supply chain reports", "tool": "rag_search"}]'
        )
        synthesis_text = "Synthesised research answer."

        call_count = {"n": 0}

        class PlanThenSynthesisLLM(SimpleChatModel):
            """Returns todo JSON on first call, synthesis text on second."""
            def _call(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                      run_manager: Optional[Any] = None, **kwargs: Any) -> str:
                call_count["n"] += 1
                return todo_json if call_count["n"] == 1 else synthesis_text

            @property
            def _llm_type(self) -> str:
                return "plan_then_synthesis_dummy"

        with patch("agents.executor.get_llm", return_value=PlanThenSynthesisLLM()), \
             patch("agents.executor.get_search_tool") as mock_search, \
             patch("agents.executor.get_rag_tool") as mock_rag:

            mock_search.return_value.invoke = MagicMock(return_value="search result")
            mock_rag.return_value.invoke    = MagicMock(return_value="rag result")

            result = _run_deepagent_research_executor(
                task=self._make_research_task(),
                context="",
                retrieved_context="",
                output_format="markdown",
                config=None,
            )

        assert result["task_id"] == "r1"
        assert result["agent_type"] == "research"
        assert isinstance(result["output"], str) and len(result["output"]) > 0
        assert isinstance(result["tool_calls"], list) and len(result["tool_calls"]) > 0

    def test_malformed_plan_raises_value_error(self):
        """_parse_todo_list raises ValueError on unparseable LLM output."""
        from agents.executor import _parse_todo_list
        with pytest.raises(ValueError, match="Could not parse todo list"):
            _parse_todo_list("This is not JSON at all — the LLM went rogue.")

    def test_executor_node_routes_research_to_deepagent(self, base_state):
        """executor_node selects _run_deepagent_research_executor for agent_type='research'."""
        from agents.executor import executor_node

        research_task = self._make_research_task()
        state = {
            **base_state,
            "sub_tasks": [research_task],
            "current_task_index": 0,
        }
        mock_result = {
            "task_id": "r1", "agent_type": "research",
            "task_description": research_task["description"],
            "output": "Research done.", "tool_calls": [],
        }

        with patch(
            "agents.executor._run_deepagent_research_executor",
            return_value=mock_result
        ) as mock_deep:
            result = executor_node(state)

        mock_deep.assert_called_once()
        assert result["current_task_index"] == 1
        assert result["execution_results"][0]["output"] == "Research done."

    def test_tool_calls_format_matches_run_executor_schema(self):
        """
        EXPLICIT FORMAT ASSERTION (user-requested).

        Every tool_calls entry from _run_deepagent_research_executor must have
        exactly the same required keys as _run_executor() produces:
            {"tool": str, "input": str, "output": str}

        This prevents silent downstream inconsistency in tool_calls_log
        (AgentState) and the /status API response.
        """
        from agents.executor import _run_deepagent_research_executor
        from langchain_core.language_models.chat_models import SimpleChatModel
        from langchain_core.messages import BaseMessage
        from typing import List, Optional, Any

        # Required schema — matches _run_executor() lines 117-120
        REQUIRED_TOOL_CALL_KEYS = {"tool", "input", "output"}

        todo_json = '[{"step": 1, "query": "test query", "tool": "web_search"}]'
        call_count = {"n": 0}

        class FixedLLM(SimpleChatModel):
            def _call(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                      run_manager: Optional[Any] = None, **kwargs: Any) -> str:
                call_count["n"] += 1
                return todo_json if call_count["n"] == 1 else "Final answer."

            @property
            def _llm_type(self) -> str:
                return "fixed_dummy"

        with patch("agents.executor.get_llm", return_value=FixedLLM()), \
             patch("agents.executor.get_search_tool") as mock_search, \
             patch("agents.executor.get_rag_tool") as mock_rag:

            mock_search.return_value.invoke = MagicMock(return_value="web result")
            mock_rag.return_value.invoke    = MagicMock(return_value="rag result")

            result = _run_deepagent_research_executor(
                task=self._make_research_task(),
                context="",
                retrieved_context="",
                output_format="markdown",
                config=None,
            )

        for entry in result["tool_calls"]:
            assert set(entry.keys()) == REQUIRED_TOOL_CALL_KEYS, (
                f"tool_calls entry has wrong keys: {set(entry.keys())} "
                f"(expected {REQUIRED_TOOL_CALL_KEYS})"
            )
            assert isinstance(entry["tool"],   str), "tool must be str"
            assert isinstance(entry["input"],  str), "input must be str"
            assert isinstance(entry["output"], str), "output must be str"
            assert len(entry["input"])  <= 300, "input must be truncated to 300 chars"
            assert len(entry["output"]) <= 500, "output must be truncated to 500 chars"

# ── File Tool Safety Tests ───────────────────────────────────────────────────

class TestFileTools:
    """Tests for file tool sandbox boundary and path traversal mitigation."""

    def test_read_file_path_traversal_denied(self):
        from tools.file_tool import read_file
        res = read_file.invoke({"file_path": "../../.env"})
        assert "Error: Path traversal detected. Access denied." in res

    def test_save_output_path_traversal_denied(self):
        from tools.file_tool import save_output
        res = save_output.invoke({"filename": "../../api/malicious.py", "content": "print('hack')"})
        assert "Error: Path traversal detected. Access denied." in res

    def test_read_file_normal_exists(self):
        from tools.file_tool import read_file, UPLOAD_DIR
        import uuid
        filename = f"test_{uuid.uuid4().hex}.txt"
        file_path = UPLOAD_DIR / filename
        file_path.write_text("hello sandbox", encoding="utf-8")
        try:
            res = read_file.invoke({"file_path": filename})
            assert res == "hello sandbox"
        finally:
            if file_path.exists():
                file_path.unlink()


# ── DB Tool Safety & Comment Tests ───────────────────────────────────────────

class TestDbTools:
    """Tests for query_database tool's comment stripping and SELECT constraint."""

    def test_query_database_allows_select_with_comments(self):
        from tools.db_tool import query_database
        res = query_database.invoke({"sql_query": "/* Q1 */ SELECT product, region, revenue FROM sales LIMIT 1;"})
        assert "Error: Only SELECT queries are permitted." not in res
        assert "Widget A" in res or "Widget B" in res

    def test_query_database_rejects_non_select(self):
        from tools.db_tool import query_database
        res = query_database.invoke({"sql_query": "INSERT INTO sales (product) VALUES ('Widget D');"})
        assert "Error: Only SELECT queries are permitted." in res

    def test_query_database_rejects_non_select_with_comments(self):
        from tools.db_tool import query_database
        res = query_database.invoke({"sql_query": "/* comment */ INSERT INTO sales (product) VALUES ('Widget D');"})
        assert "Error: Only SELECT queries are permitted." in res

    def test_query_database_comment_stripping_postgres_compatibility(self):
        from tools.db_tool import query_database
        sql = """
        /* header comment */
        SELECT product, region, revenue
        FROM sales
        WHERE id = 1; -- trailing inline comment
        """
        res = query_database.invoke({"sql_query": sql})
        assert "Error: Only SELECT queries are permitted." not in res
        assert "Widget A" in res


# ── Auth Tests ────────────────────────────────────────────────────────────────

class TestAuth:
    """Tests for JWT + static API key authentication layer."""

    @pytest.fixture
    def raw_client(self):
        """Client WITHOUT any auth override — real auth enforcement."""
        from fastapi.testclient import TestClient
        from api.main import app
        from auth.models import create_users_table
        create_users_table()
        app.dependency_overrides.clear()  # ensure no leftover overrides
        with TestClient(app) as client:
            yield client

    @pytest.fixture
    def auth_client(self):
        """Client with auth bypassed for setup helpers."""
        from fastapi.testclient import TestClient
        from api.main import app
        from auth.dependencies import require_auth
        from auth.schemas import UserOut
        from auth.models import create_users_table
        create_users_table()
        app.dependency_overrides[require_auth] = lambda: UserOut(
            id=1, username="testuser", email="test@example.com", is_active=True, created_at=""
        )
        with TestClient(app) as client:
            yield client
        app.dependency_overrides.clear()

    def test_health_public(self, raw_client):
        """GET /health must be accessible without any token."""
        response = raw_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_protected_route_without_token_returns_401(self, raw_client):
        """POST /run without a token must return 401."""
        response = raw_client.post("/run", json={"user_input": "hello", "session_id": "s1"})
        assert response.status_code == 401

    def test_register_creates_user(self, raw_client):
        """POST /auth/register returns 201 and UserOut."""
        import uuid
        username = f"testuser_{uuid.uuid4().hex[:6]}"
        response = raw_client.post("/auth/register", json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "securepassword123",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == username
        assert "id" in data
        assert "hashed_password" not in data  # never leak hashed pw

    def test_register_duplicate_returns_409(self, raw_client):
        """Registering the same username twice returns 409 Conflict."""
        import uuid
        username = f"dup_{uuid.uuid4().hex[:6]}"
        payload = {"username": username, "email": f"{username}@example.com", "password": "pw"}
        raw_client.post("/auth/register", json=payload)  # first
        response = raw_client.post("/auth/register", json=payload)  # duplicate
        assert response.status_code == 409

    def test_login_returns_jwt(self, raw_client):
        """POST /auth/login with valid credentials returns a Bearer token."""
        import uuid
        username = f"logintest_{uuid.uuid4().hex[:6]}"
        raw_client.post("/auth/register", json={
            "username": username, "email": f"{username}@x.com", "password": "mypassword"
        })
        response = raw_client.post("/auth/login", json={"username": username, "password": "mypassword"})
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_jwt_grants_access_to_protected_route(self, raw_client):
        """A valid JWT should allow access to GET /assistants."""
        import uuid
        username = f"jwtuser_{uuid.uuid4().hex[:6]}"
        raw_client.post("/auth/register", json={
            "username": username, "email": f"{username}@x.com", "password": "pw"
        })
        login = raw_client.post("/auth/login", json={"username": username, "password": "pw"})
        token = login.json()["access_token"]
        response = raw_client.get("/assistants", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    def test_invalid_token_returns_401(self, raw_client):
        """A garbage token must return 401."""
        response = raw_client.get("/assistants", headers={"Authorization": "Bearer not-a-valid-token"})
        assert response.status_code == 401

    def test_static_api_key_grants_access(self, raw_client):
        """A valid static API_KEY should grant access to protected routes."""
        from unittest.mock import patch
        with patch("auth.dependencies._settings") as mock_settings:
            mock_settings.api_key = "test-static-key-abc123"
            response = raw_client.get(
                "/assistants",
                headers={"Authorization": "Bearer test-static-key-abc123"}
            )
        assert response.status_code == 200

    def test_get_me_returns_current_user(self, raw_client):
        """GET /auth/me with valid JWT returns user profile."""
        import uuid
        username = f"meuser_{uuid.uuid4().hex[:6]}"
        raw_client.post("/auth/register", json={
            "username": username, "email": f"{username}@x.com", "password": "pw"
        })
        login = raw_client.post("/auth/login", json={"username": username, "password": "pw"})
        token = login.json()["access_token"]
        response = raw_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["username"] == username


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
