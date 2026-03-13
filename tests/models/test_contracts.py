"""Tests for Fase -1 shared contracts.

Validates that the contract DTOs work correctly and can be
serialized/deserialized. These contracts are the foundation
for parallel branch development.
"""

from datetime import datetime, timezone

import pytest

from sreg.inference.protocol import (
    ChatResponse,
    FinishReason,
    Message,
    MessageRole,
    ToolCall,
    ToolSpec,
    Usage,
)
from sreg.models.agent_tools import (
    DEFAULT_TOOLSET,
    PYTHON_EXEC,
    RESEARCH_ACTION,
    SUBMIT,
    AgentTool,
    AgentToolset,
)
from sreg.models.benchmark import BenchmarkComparison, BenchmarkResult, BenchmarkStatus
from sreg.models.code_exec import CodeExecConfig, CodeExecResult, ExecStatus
from sreg.models.env_protocol import EnvAction, EnvObservation, EnvStepResult


# ---------------------------------------------------------------------------
# Inference protocol
# ---------------------------------------------------------------------------


class TestMessage:
    def test_system_message(self):
        msg = Message(role=MessageRole.SYSTEM, content="You are a scientist.")
        assert msg.role == "system"
        assert msg.content == "You are a scientist."

    def test_tool_message(self):
        msg = Message(role=MessageRole.TOOL, content='{"result": 42}', tool_call_id="call_1")
        assert msg.tool_call_id == "call_1"

    def test_assistant_no_content(self):
        msg = Message(role=MessageRole.ASSISTANT)
        assert msg.content is None


class TestToolSpec:
    def test_basic(self):
        spec = ToolSpec(name="observe", description="Observe a variable")
        assert spec.name == "observe"
        assert spec.parameters == {}

    def test_with_params(self):
        spec = ToolSpec(
            name="research_action",
            parameters={"type": "object", "properties": {"action_id": {"type": "string"}}},
        )
        assert "action_id" in spec.parameters["properties"]


class TestToolCall:
    def test_basic(self):
        tc = ToolCall(id="call_1", name="research_action", arguments={"action_id": "measure_ph"})
        assert tc.name == "research_action"
        assert tc.arguments["action_id"] == "measure_ph"

    def test_raw_arguments(self):
        tc = ToolCall(
            id="call_1", name="submit", arguments={"choice": "A"}, raw_arguments='{"choice":"A"}'
        )
        assert tc.raw_arguments is not None


class TestChatResponse:
    def test_stop(self):
        resp = ChatResponse(
            message=Message(role=MessageRole.ASSISTANT, content="The answer is X."),
            finish_reason=FinishReason.STOP,
        )
        assert resp.finish_reason == "stop"
        assert resp.tool_calls == []

    def test_tool_calls(self):
        resp = ChatResponse(
            message=Message(role=MessageRole.ASSISTANT),
            tool_calls=[ToolCall(id="c1", name="research_action", arguments={"action_id": "a1"})],
            finish_reason=FinishReason.TOOL_CALLS,
            usage=Usage(input_tokens=100, output_tokens=50),
        )
        assert len(resp.tool_calls) == 1
        assert resp.usage.total_tokens is None
        assert resp.usage.input_tokens == 100

    def test_serialization_roundtrip(self):
        resp = ChatResponse(
            message=Message(role=MessageRole.ASSISTANT, content="hello"),
            finish_reason=FinishReason.STOP,
        )
        data = resp.model_dump()
        resp2 = ChatResponse.model_validate(data)
        assert resp2.message.content == "hello"


# ---------------------------------------------------------------------------
# Benchmark result
# ---------------------------------------------------------------------------


class TestBenchmarkResult:
    def test_cladder(self):
        result = BenchmarkResult(
            benchmark="cladder",
            model_name="qwen3-8b",
            eval_split="rung_2",
            metric_name="accuracy",
            metric_value=0.42,
            num_examples=3370,
            seed=42,
        )
        assert result.run_id  # auto-generated
        assert result.status == BenchmarkStatus.SUCCESS
        assert result.higher_is_better is True

    def test_kl_metric(self):
        result = BenchmarkResult(
            benchmark="sreg_internal",
            model_name="qwen3-0.5b",
            eval_split="infer_target",
            metric_name="kl_divergence",
            metric_value=1.23,
            higher_is_better=False,
            num_examples=50,
        )
        assert result.higher_is_better is False

    def test_comparison(self):
        before = BenchmarkResult(
            benchmark="cladder",
            model_name="qwen3-8b",
            eval_split="test",
            metric_name="accuracy",
            metric_value=0.35,
            num_examples=10000,
        )
        after = BenchmarkResult(
            benchmark="cladder",
            model_name="qwen3-8b",
            eval_split="test",
            metric_name="accuracy",
            metric_value=0.45,
            num_examples=10000,
        )
        comp = BenchmarkComparison(
            before=before,
            after=after,
            delta=0.10,
            relative_delta=0.10 / 0.35,
        )
        assert comp.delta == pytest.approx(0.10)
        assert comp.relative_delta == pytest.approx(0.2857, abs=0.001)


# ---------------------------------------------------------------------------
# Code execution
# ---------------------------------------------------------------------------


class TestCodeExec:
    def test_ok_result(self):
        result = CodeExecResult(
            status=ExecStatus.OK,
            stdout="correlation: 0.85\n",
            exec_time_ms=120,
        )
        assert result.status == "ok"
        assert not result.stdout_truncated

    def test_timeout(self):
        result = CodeExecResult(
            status=ExecStatus.TIMEOUT,
            stderr="Execution timed out after 5000ms",
            exec_time_ms=5000,
        )
        assert result.status == "timeout"

    def test_config_defaults(self):
        config = CodeExecConfig()
        assert config.timeout_ms == 5000
        assert "numpy" in config.allowed_imports
        assert "pandas" in config.allowed_imports
        assert config.max_memory_mb == 1024

    def test_config_custom(self):
        config = CodeExecConfig(timeout_ms=2000, max_code_chars=1000)
        assert config.timeout_ms == 2000


# ---------------------------------------------------------------------------
# Environment protocol
# ---------------------------------------------------------------------------


class TestEnvProtocol:
    def test_action(self):
        action = EnvAction(tool_name="research_action", arguments={"action_id": "measure_ph"})
        assert action.tool_name == "research_action"

    def test_observation(self):
        obs = EnvObservation(
            text="You are investigating water quality...",
            available_tools=["research_action", "python_exec", "submit"],
            budget_remaining=5,
        )
        assert len(obs.available_tools) == 3

    def test_step_result_non_terminal(self):
        result = EnvStepResult(
            observation=EnvObservation(text="pH = 7.2", step_index=1),
            reward=0.0,
            terminated=False,
        )
        assert not result.terminated
        assert result.reward == 0.0

    def test_step_result_terminal(self):
        result = EnvStepResult(
            observation=EnvObservation(text="Answer submitted.", step_index=5),
            reward=0.85,
            terminated=True,
            info={"kl_divergence": 0.15, "task_type": "infer_target"},
        )
        assert result.terminated
        assert result.reward == 0.85


# ---------------------------------------------------------------------------
# Agent toolset
# ---------------------------------------------------------------------------


class TestAgentToolset:
    def test_defaults(self):
        ts = DEFAULT_TOOLSET
        assert len(ts.tools) == 3
        names = {t.name for t in ts.tools}
        assert names == {"research_action", "python_exec", "submit"}

    def test_submit_is_terminal(self):
        assert SUBMIT.is_terminal is True
        assert RESEARCH_ACTION.is_terminal is False
        assert PYTHON_EXEC.is_terminal is False

    def test_version(self):
        assert DEFAULT_TOOLSET.version == "v1"

    def test_custom_toolset(self):
        ts = AgentToolset(
            tools=[RESEARCH_ACTION, SUBMIT],
            max_tool_calls=4,
            version="v0-no-code",
        )
        assert len(ts.tools) == 2
        assert ts.max_tool_calls == 4
