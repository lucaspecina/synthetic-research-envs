"""Tests for OpenAI adapter (mocked, no real API calls)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sreg.inference.openai_client import OpenAIClient, _message_to_dict, _parse_response
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


def _mock_openai_response(
    content: str = "Hello",
    finish_reason: str = "stop",
    tool_calls: list | None = None,
    model: str = "gpt-4o",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
):
    """Create a mock OpenAI API response object."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls

    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = finish_reason

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = prompt_tokens + completion_tokens

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    response.model = model
    response.id = "resp-123"

    return response


def _mock_tool_call(tc_id: str = "tc-1", name: str = "get_weather", args: str = '{"city": "NYC"}'):
    """Create a mock tool call object."""
    func = MagicMock()
    func.name = name
    func.arguments = args

    tc = MagicMock()
    tc.id = tc_id
    tc.function = func
    return tc


# ---------------------------------------------------------------------------
# Tests: _message_to_dict
# ---------------------------------------------------------------------------


class TestMessageToDict:
    def test_simple_user_message(self):
        msg = Message(role=MessageRole.USER, content="Hello")
        d = _message_to_dict(msg)
        assert d == {"role": "user", "content": "Hello"}

    def test_system_message(self):
        msg = Message(role=MessageRole.SYSTEM, content="You are helpful.")
        d = _message_to_dict(msg)
        assert d == {"role": "system", "content": "You are helpful."}

    def test_tool_message(self):
        msg = Message(role=MessageRole.TOOL, content="result", tool_call_id="tc-1", name="fn")
        d = _message_to_dict(msg)
        assert d == {"role": "tool", "content": "result", "tool_call_id": "tc-1", "name": "fn"}

    def test_none_content_omitted(self):
        msg = Message(role=MessageRole.ASSISTANT)
        d = _message_to_dict(msg)
        assert "content" not in d


# ---------------------------------------------------------------------------
# Tests: _parse_response
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_simple_response(self):
        raw = _mock_openai_response(content="Hello world", finish_reason="stop")
        result = _parse_response(raw)

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
        tc = _mock_tool_call("tc-1", "search", '{"q": "test"}')
        raw = _mock_openai_response(
            content=None, finish_reason="tool_calls", tool_calls=[tc]
        )
        result = _parse_response(raw)

        assert result.finish_reason == FinishReason.TOOL_CALLS
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "tc-1"
        assert result.tool_calls[0].name == "search"
        assert result.tool_calls[0].arguments == {"q": "test"}
        assert result.tool_calls[0].raw_arguments == '{"q": "test"}'

    def test_invalid_json_in_tool_args(self):
        tc = _mock_tool_call("tc-1", "fn", "not-json")
        raw = _mock_openai_response(content=None, finish_reason="tool_calls", tool_calls=[tc])
        result = _parse_response(raw)

        assert result.tool_calls[0].arguments == {}
        assert result.tool_calls[0].raw_arguments == "not-json"

    def test_length_finish_reason(self):
        raw = _mock_openai_response(finish_reason="length")
        result = _parse_response(raw)
        assert result.finish_reason == FinishReason.LENGTH

    def test_unknown_finish_reason_maps_to_error(self):
        raw = _mock_openai_response(finish_reason="content_filter")
        result = _parse_response(raw)
        assert result.finish_reason == FinishReason.ERROR


# ---------------------------------------------------------------------------
# Tests: OpenAIClient.chat (mocked)
# ---------------------------------------------------------------------------


class TestOpenAIClientChat:
    @patch("sreg.inference.openai_client.OpenAI")
    def test_chat_basic(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_resp = _mock_openai_response("Yes, that is correct.")
        mock_client.chat.completions.create.return_value = mock_resp

        client = OpenAIClient(api_key="test-key", model="test-model")
        result = client.chat(
            messages=[Message(role=MessageRole.USER, content="Is 2+2=4?")],
            temperature=0.0,
        )

        assert result.message.content == "Yes, that is correct."
        assert result.finish_reason == FinishReason.STOP

        # Verify API was called correctly
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "test-model"
        assert call_kwargs["temperature"] == 0.0
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"

    @patch("sreg.inference.openai_client.OpenAI")
    def test_chat_with_tools(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_resp = _mock_openai_response("ok")
        mock_client.chat.completions.create.return_value = mock_resp

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

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tools"][0]["type"] == "function"
        assert call_kwargs["tools"][0]["function"]["name"] == "search"

    @patch("sreg.inference.openai_client.OpenAI")
    def test_model_override(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_resp = _mock_openai_response("ok")
        mock_client.chat.completions.create.return_value = mock_resp

        client = OpenAIClient(api_key="test-key", model="default-model")
        client.chat(
            messages=[Message(role=MessageRole.USER, content="hi")],
            model="override-model",
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "override-model"
