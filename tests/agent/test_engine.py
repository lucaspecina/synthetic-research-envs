"""Tests for the shared tool-calling engine (agent/engine.py)."""

import json
from unittest.mock import MagicMock, patch

from sreg.agent.engine import (
    SOLVER_TOOLS,
    _handle_solver_tool,
    run_with_tools,
    solve_question,
)
from sreg.agent.python_exec import make_python_namespace
from sreg.agent.transformers_backend import parse_hermes_tool_calls


# --- Tool definitions ---


def test_solver_tools_has_python_exec_and_think():
    names = {t["function"]["name"] for t in SOLVER_TOOLS}
    assert names == {"python_exec", "think"}


# --- Tool handler ---


def test_handle_think():
    ns = make_python_namespace()
    result = _handle_solver_tool("think", {"reasoning": "test"}, ns)
    assert "noted" in result


def test_handle_python_exec():
    ns = make_python_namespace()
    result = _handle_solver_tool("python_exec", {"code": "2 + 3"}, ns)
    assert "5" in result


def test_handle_python_exec_with_data():
    data_assets = [{"data": [{"x": 1}, {"x": 2}], "format": "tabular"}]
    ns = make_python_namespace(data_assets=data_assets)
    result = _handle_solver_tool("python_exec", {"code": "len(df)"}, ns)
    assert "2" in result


def test_handle_unknown_tool():
    ns = make_python_namespace()
    result = _handle_solver_tool("unknown", {}, ns)
    assert "unknown" in result.lower()


# --- Hermes parsing ---


def test_parse_hermes_simple():
    raw = '<tool_call>{"name": "think", "arguments": {"reasoning": "hello"}}</tool_call>'
    text, calls = parse_hermes_tool_calls(raw)
    assert len(calls) == 1
    assert calls[0]["name"] == "think"
    args = json.loads(calls[0]["arguments"])
    assert args["reasoning"] == "hello"


def test_parse_hermes_with_text():
    raw = 'Some text before <tool_call>{"name": "think", "arguments": {}}</tool_call> after'
    text, calls = parse_hermes_tool_calls(raw)
    assert len(calls) == 1
    assert "before" in text
    assert "after" in text


def test_parse_hermes_multiple():
    raw = (
        '<tool_call>{"name": "think", "arguments": {}}</tool_call>'
        '<tool_call>{"name": "python_exec", "arguments": {"code": "1+1"}}</tool_call>'
    )
    _, calls = parse_hermes_tool_calls(raw)
    assert len(calls) == 2
    assert calls[0]["name"] == "think"
    assert calls[1]["name"] == "python_exec"


def test_parse_hermes_no_tools():
    text, calls = parse_hermes_tool_calls("Just a regular response")
    assert calls == []
    assert "regular" in text


def test_parse_hermes_malformed():
    raw = '<tool_call>not json</tool_call>'
    text, calls = parse_hermes_tool_calls(raw)
    assert calls == []
    assert "malformed" in text


def test_parse_hermes_cleans_special_tokens():
    raw = 'answer<|im_end|><|endoftext|>'
    text, calls = parse_hermes_tool_calls(raw)
    assert text == "answer"


# --- run_with_tools ---


def _mock_response(content=None, tool_calls=None):
    """Create a mock Responses API response."""
    output = []
    if content:
        text_part = MagicMock()
        text_part.text = content
        msg_item = MagicMock()
        msg_item.type = "message"
        msg_item.content = [text_part]
        output.append(msg_item)
    if tool_calls:
        output.extend(tool_calls)

    resp = MagicMock()
    resp.output = output
    resp.id = f"resp-{id(resp)}"
    resp.status = "completed"
    return resp


def test_run_with_tools_no_tools():
    client = MagicMock()
    client.responses.create.return_value = _mock_response(content="hello")

    messages = [{"role": "user", "content": "hi"}]
    result = run_with_tools(client, "gpt-4o", messages)

    assert any(m.get("content") == "hello" for m in result)


def test_run_with_tools_with_tool_call():
    # First call returns a tool call, second returns text
    tc = MagicMock()
    tc.type = "function_call"
    tc.call_id = "call_123"
    tc.name = "think"
    tc.arguments = '{"reasoning": "test"}'

    client = MagicMock()
    client.responses.create.side_effect = [
        _mock_response(content="", tool_calls=[tc]),
        _mock_response(content="final answer"),
    ]

    messages = [{"role": "user", "content": "question"}]
    handler = lambda name, args: '{"status": "noted"}'
    result = run_with_tools(client, "gpt-4o", messages, SOLVER_TOOLS, handler)

    # Should have: user, assistant (tool call), tool result, assistant (final)
    roles = [m.get("role") for m in result]
    assert "tool" in roles


# --- solve_question ---


def test_solve_question_basic():
    client = MagicMock()
    client.responses.create.return_value = _mock_response(content="42")

    answer = solve_question(
        client=client,
        model="gpt-4o",
        system_prompt="You are helpful.",
        user_prompt="What is 6*7?",
    )
    assert answer == "42"


def test_solve_question_with_data():
    client = MagicMock()
    # Model calls python_exec, then answers
    tc = MagicMock()
    tc.type = "function_call"
    tc.call_id = "call_1"
    tc.name = "python_exec"
    tc.arguments = '{"code": "df.shape[0]"}'

    client.responses.create.side_effect = [
        _mock_response(content="", tool_calls=[tc]),
        _mock_response(content="The dataset has 2 rows"),
    ]

    data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    answer = solve_question(
        client=client,
        model="gpt-4o",
        system_prompt="Analyze the data.",
        user_prompt="How many rows?",
        data=data,
    )
    assert "2" in answer
