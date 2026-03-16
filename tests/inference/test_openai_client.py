"""Tests for OpenAI adapter using Responses API (mocked, no real API calls)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sreg.inference.openai_client import OpenAIClient, _parse_responses_api, _toolspec_to_responses
from sreg.inference.protocol import (
    ChatResponse,
    FinishReason,
    Message,
    MessageRole,
    ToolSpec,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mock_responses_api_response(
    text: str = "Hello",
    tool_calls: list | None = None,
    status: str = "completed",
    model: str = "gpt-4o",
    input_tokens: int = 10,
    output_tokens: int = 5,
):
    """Create a mock Responses API response object."""
    output = []

    if text:
        text_part = MagicMock()
        text_part.text = text

        msg_item = MagicMock()
        msg_item.type = "message"
        msg_item.content = [text_part]
        output.append(msg_item)

    if tool_calls:
        for tc in tool_calls:
            output.append(tc)

    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.total_tokens = input_tokens + output_tokens

    response = MagicMock()
    response.output = output
    response.usage = usage
    response.model = model
    response.id = "resp-123"
    response.status = status

    return response


def _mock_function_call(call_id: str = "call-1", name: str = "get_weather", args: str = '{"city": "NYC"}'):
    """Create a mock function_call output item."""
    tc = MagicMock()
    tc.type = "function_call"
    tc.call_id = call_id
    tc.name = name
    tc.arguments = args
    return tc


# ---------------------------------------------------------------------------
# Tests: _toolspec_to_responses
# ---------------------------------------------------------------------------


class TestToolspecToResponses:
    def test_converts_spec(self):
        spec = ToolSpec(
            name="search",
            description="Search the web",
            parameters={"type": "object", "properties": {"q": {"type": "string"}}},
        )
        d = _toolspec_to_responses(spec)
        assert d == {
            "type": "function",
            "name": "search",
            "description": "Search the web",
            "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
        }


# ---------------------------------------------------------------------------
# Tests: _parse_responses_api
# ---------------------------------------------------------------------------


class TestParseResponsesApi:
    def test_simple_response(self):
        raw = _mock_responses_api_response(text="Hello world", status="completed")
        result = _parse_responses_api(raw)

        assert isinstance(result, ChatResponse)
        assert result.message.role == MessageRole.ASSISTANT
        assert result.message.content == "Hello world"
        assert result.finish_reason == FinishReason.STOP
        assert result.tool_calls == []
        assert result.usage is not None
        assert result.usage.input_tokens == 10
        assert result.usage.output_tokens == 5
        assert result.provider_model == "gpt-4o"

    def test_tool_calls_parsed(self):
        tc = _mock_function_call("call-1", "search", '{"q": "test"}')
        raw = _mock_responses_api_response(text=None, tool_calls=[tc])
        result = _parse_responses_api(raw)

        assert result.finish_reason == FinishReason.TOOL_CALLS
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "call-1"
        assert result.tool_calls[0].name == "search"
        assert result.tool_calls[0].arguments == {"q": "test"}
        assert result.tool_calls[0].raw_arguments == '{"q": "test"}'

    def test_invalid_json_in_tool_args(self):
        tc = _mock_function_call("call-1", "fn", "not-json")
        raw = _mock_responses_api_response(text=None, tool_calls=[tc])
        result = _parse_responses_api(raw)

        assert result.tool_calls[0].arguments == {}
        assert result.tool_calls[0].raw_arguments == "not-json"


# ---------------------------------------------------------------------------
# Tests: OpenAIClient.chat (mocked)
# ---------------------------------------------------------------------------


class TestOpenAIClientChat:
    @patch("sreg.inference.openai_client.OpenAI")
    def test_chat_basic(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_resp = _mock_responses_api_response("Yes, that is correct.")
        mock_client.responses.create.return_value = mock_resp

        client = OpenAIClient(api_key="test-key", model="test-model")
        result = client.chat(
            messages=[Message(role=MessageRole.USER, content="Is 2+2=4?")],
            temperature=0.0,
        )

        assert result.message.content == "Yes, that is correct."
        assert result.finish_reason == FinishReason.STOP

        # Verify API was called correctly
        call_kwargs = mock_client.responses.create.call_args[1]
        assert call_kwargs["model"] == "test-model"
        assert call_kwargs["temperature"] == 0.0

    @patch("sreg.inference.openai_client.OpenAI")
    def test_chat_with_tools(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_resp = _mock_responses_api_response("ok")
        mock_client.responses.create.return_value = mock_resp

        client = OpenAIClient(api_key="test-key")
        tools = [
            ToolSpec(
                name="search",
                description="Search the web",
                parameters={"type": "object", "properties": {"q": {"type": "string"}}},
            )
        ]
        client.chat(
            messages=[Message(role=MessageRole.USER, content="find cats")],
            tools=tools,
        )

        call_kwargs = mock_client.responses.create.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tools"][0]["type"] == "function"
        assert call_kwargs["tools"][0]["name"] == "search"

    @patch("sreg.inference.openai_client.OpenAI")
    def test_model_override(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_resp = _mock_responses_api_response("ok")
        mock_client.responses.create.return_value = mock_resp

        client = OpenAIClient(api_key="test-key", model="default-model")
        client.chat(
            messages=[Message(role=MessageRole.USER, content="hi")],
            model="override-model",
        )

        call_kwargs = mock_client.responses.create.call_args[1]
        assert call_kwargs["model"] == "override-model"
