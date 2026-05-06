"""Tests UNITARIOS del wiring de `PaperDigestionAgent`.

Foco: el agente parsea correctamente la respuesta del LLM, valida
contra `PaperInsights`, y maneja errores de modo coherente. NO valida
el contenido (eso requiere LLM real + revisión humana, ver
`scripts/run_paper_digestion.py`).
"""

from __future__ import annotations

import pytest

from sreg.inference.protocol import (
    ChatResponse,
    FinishReason,
    Message,
    MessageRole,
    ToolCall,
    ToolSpec,
)
from sreg.v1_5.agents.paper_digestion import (
    PaperDigestionAgent,
    PaperDigestionError,
)


class _FakeClient:
    """ModelClient mock: devuelve una respuesta pre-armada."""

    def __init__(self, response: ChatResponse) -> None:
        self.response = response
        self.last_messages: list[Message] | None = None
        self.last_tools: list[ToolSpec] | None = None

    def chat(
        self,
        messages,
        tools=None,
        model=None,
        temperature=None,
        max_tokens=None,
    ) -> ChatResponse:
        self.last_messages = list(messages)
        self.last_tools = list(tools) if tools else None
        return self.response


def _valid_args() -> dict:
    """Argumentos completos y válidos para `PaperInsights`."""
    return {
        "paper_id": "seed_test",
        "objective": "Estudiar X",
        "entities": ["A", "B"],
        "mechanisms": ["A afecta B"],
        "phenomena": ["asociación positiva"],
        "complications": ["confounder C"],
        "counterintuitive_priors": [],
        "realism_bounds": [],
        "narrative_capsule": {
            "domain": "test_domain",
            "population": "test_pop",
            "units": {},
            "measurement_conventions": [],
            "natural_question_style": [],
            "forbidden_phrases": [],
        },
    }


def _make_response(
    *,
    args: dict | None = None,
    tool_name: str = "emit_paper_insights",
    finish: FinishReason = FinishReason.TOOL_CALLS,
    n_calls: int = 1,
    text: str | None = None,
) -> ChatResponse:
    tool_calls = [
        ToolCall(id=f"c{i}", name=tool_name, arguments=args or _valid_args())
        for i in range(n_calls)
    ]
    return ChatResponse(
        message=Message(role=MessageRole.ASSISTANT, content=text),
        tool_calls=tool_calls if finish == FinishReason.TOOL_CALLS else [],
        finish_reason=finish,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_digest_returns_paper_insights_on_valid_tool_call() -> None:
    fake = _FakeClient(_make_response())
    agent = PaperDigestionAgent(fake)
    insights = agent.digest(paper_text="paper content", paper_id="seed_real")

    assert insights.paper_id == "seed_real"  # caller-provided overrides model
    assert insights.objective == "Estudiar X"
    assert insights.narrative_capsule.domain == "test_domain"


def test_digest_passes_paper_id_into_user_message() -> None:
    fake = _FakeClient(_make_response())
    agent = PaperDigestionAgent(fake)
    agent.digest(paper_text="abc def", paper_id="my_seed")
    user_msgs = [m for m in fake.last_messages if m.role == MessageRole.USER]
    assert len(user_msgs) == 1
    assert "my_seed" in (user_msgs[0].content or "")
    assert "abc def" in (user_msgs[0].content or "")


def test_digest_overrides_paper_id_from_caller_not_model() -> None:
    """Aunque el modelo invente paper_id en sus args, el caller manda."""
    args = {**_valid_args(), "paper_id": "modelo_inventado"}
    fake = _FakeClient(_make_response(args=args))
    agent = PaperDigestionAgent(fake)
    insights = agent.digest(paper_text="x", paper_id="caller_id")
    assert insights.paper_id == "caller_id"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_digest_raises_when_paper_text_empty() -> None:
    fake = _FakeClient(_make_response())
    agent = PaperDigestionAgent(fake)
    with pytest.raises(PaperDigestionError, match="vac"):
        agent.digest(paper_text="   ", paper_id="x")


def test_digest_raises_when_finish_reason_not_tool_calls() -> None:
    """Si el modelo respondió texto en vez de llamar al tool, error claro."""
    fake = _FakeClient(
        _make_response(finish=FinishReason.STOP, text="No quiero llamar tools")
    )
    agent = PaperDigestionAgent(fake)
    with pytest.raises(PaperDigestionError, match="no llamó al tool"):
        agent.digest(paper_text="x", paper_id="y")


def test_digest_raises_when_wrong_tool_name() -> None:
    fake = _FakeClient(_make_response(tool_name="otro_tool"))
    agent = PaperDigestionAgent(fake)
    with pytest.raises(PaperDigestionError, match="no coinciden"):
        agent.digest(paper_text="x", paper_id="y")


def test_digest_raises_when_tool_called_multiple_times() -> None:
    fake = _FakeClient(_make_response(n_calls=3))
    agent = PaperDigestionAgent(fake)
    with pytest.raises(PaperDigestionError, match="3 veces"):
        agent.digest(paper_text="x", paper_id="y")


def test_digest_raises_when_tool_args_invalid_for_schema() -> None:
    """Args incompletos: falta narrative_capsule (obligatorio post-Ronda 13)."""
    bad_args = {**_valid_args()}
    bad_args.pop("narrative_capsule")
    fake = _FakeClient(_make_response(args=bad_args))
    agent = PaperDigestionAgent(fake)
    with pytest.raises(PaperDigestionError, match="no validan"):
        agent.digest(paper_text="x", paper_id="y")


# ---------------------------------------------------------------------------
# ToolSpec exposure
# ---------------------------------------------------------------------------


def test_tool_spec_uses_paper_insights_schema() -> None:
    """El ToolSpec tiene `parameters` derivado de `PaperInsights.model_json_schema`."""
    fake = _FakeClient(_make_response())
    agent = PaperDigestionAgent(fake)
    agent.digest(paper_text="x", paper_id="y")
    tools = fake.last_tools or []
    assert len(tools) == 1
    assert tools[0].name == "emit_paper_insights"
    params = tools[0].parameters
    # Sanity: las claves del schema están.
    assert "properties" in params
    assert "narrative_capsule" in params["properties"]
    assert "mechanisms" in params["properties"]
