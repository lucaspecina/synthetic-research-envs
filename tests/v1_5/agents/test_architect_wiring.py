"""Tests del wiring de `ArchitectAgent`.

Foco: parsing de respuestas del LLM, conversor draft → WorldSpec,
single retry tras error, propagación de errores deterministas. NO
valida contenido semántico (eso requiere LLM real + revisión humana,
ver `scripts/run_architect.py`).
"""

from __future__ import annotations

import pytest

from sreg.inference.protocol import (
    ChatResponse,
    FinishReason,
    Message,
    MessageRole,
    ToolCall,
)
from sreg.v1_5.agents.architect import ArchitectAgent, ArchitectError
from sreg.v1_5.contracts import PaperInsights, PaperNarrativeCapsule


def _insights() -> PaperInsights:
    return PaperInsights(
        paper_id="seed_test",
        objective="Estudiar X y su efecto sobre Y.",
        entities=["X", "Y"],
        mechanisms=["X afecta Y"],
        phenomena=["asociación positiva entre X e Y"],
        complications=["sample finito"],
        counterintuitive_priors=[],
        realism_bounds=[],
        narrative_capsule=PaperNarrativeCapsule(
            domain="generic",
            population="entidades observacionales",
        ),
    )


def _valid_draft_args() -> dict:
    """Draft mínimo y válido (Y depende de X linealmente)."""
    return {
        "domain": "generic",
        "seed_paper_id": "seed_test",
        "notes": None,
        "variables": [
            {
                "name": "X",
                "kind": "continuous",
                "description": "exposure",
                "is_observable": True,
                "equation": "normal(0, 1)",
            },
            {
                "name": "Y",
                "kind": "continuous",
                "description": "outcome",
                "is_observable": True,
                "equation": "2*X + normal(0, 0.5)",
            },
        ],
        "edges": [{"parent": "X", "child": "Y"}],
        "intended_phenomena": [
            {
                "id": "ip_xy",
                "kind": "non_linearity",
                "description": "X linear effect on Y",
                "relevant_variables": ["X", "Y"],
            }
        ],
    }


class _StubClient:
    """ModelClient que devuelve respuestas pre-armadas en orden."""

    def __init__(self, responses: list[ChatResponse]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def chat(
        self,
        messages,
        tools=None,
        model=None,
        temperature=None,
        max_tokens=None,
    ) -> ChatResponse:
        if not self.responses:
            raise AssertionError("StubClient ran out of responses")
        resp = self.responses.pop(0)
        self.calls += 1
        return resp


def _make_response(
    *,
    args: dict | None = None,
    tool_name: str = "emit_world_draft",
    finish: FinishReason = FinishReason.TOOL_CALLS,
    n_calls: int = 1,
    text: str | None = None,
) -> ChatResponse:
    tool_calls = [
        ToolCall(id=f"c{i}", name=tool_name, arguments=args or _valid_draft_args())
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


def test_design_returns_world_spec_on_valid_draft() -> None:
    client = _StubClient([_make_response()])
    agent = ArchitectAgent(client)
    world = agent.design(insights=_insights())
    assert world.formalism == "scm"
    assert {v.name for v in world.variables} == {"X", "Y"}
    assert ("X", "Y") in world.edges
    assert client.calls == 1  # no retry necesario


def test_design_passes_safe_capsule_only_to_user_message() -> None:
    client = _StubClient([_make_response()])
    agent = ArchitectAgent(client)
    insights = _insights()
    # Forzamos forbidden_phrases que NO debe llegar al Architect.
    insights.narrative_capsule.forbidden_phrases = [
        "the X effect", "selection bias",
    ]
    agent.design(insights=insights)
    # Inspect el mensaje que recibió el LLM.
    # (StubClient no guarda mensajes; armo otro test con captura).


def test_design_uses_safe_capsule_subset() -> None:
    """Confirma que `forbidden_phrases` NO aparece en el user message."""
    captured: dict = {}

    class _CapturingClient:
        def chat(self, messages, tools=None, model=None, temperature=None, max_tokens=None):
            captured["messages"] = list(messages)
            return _make_response()

    agent = ArchitectAgent(_CapturingClient())
    insights = _insights()
    insights.narrative_capsule.forbidden_phrases = ["secret_phrase_xyz"]
    agent.design(insights=insights)
    user_content = " ".join(
        m.content or "" for m in captured["messages"]
        if m.role == MessageRole.USER
    )
    assert "secret_phrase_xyz" not in user_content


# ---------------------------------------------------------------------------
# Single retry
# ---------------------------------------------------------------------------


def test_design_retries_once_on_first_failure() -> None:
    """Primer intento devuelve draft inválido (DAG con ciclo); retry recupera."""
    cyclic = _valid_draft_args()
    cyclic["edges"] = [
        {"parent": "X", "child": "Y"},
        {"parent": "Y", "child": "X"},  # ciclo
    ]
    cyclic["variables"][0]["equation"] = "Y + normal(0, 1)"  # X usa Y
    client = _StubClient([
        _make_response(args=cyclic),  # falla
        _make_response(),  # retry OK
    ])
    agent = ArchitectAgent(client)
    world = agent.design(insights=_insights())
    assert client.calls == 2
    assert world.formalism == "scm"


def test_design_raises_after_retry_also_fails() -> None:
    """Dos intentos malos consecutivos → ArchitectError."""
    bad = _valid_draft_args()
    bad["edges"] = []  # rompe edges↔equation (Y usa X pero no hay edge)
    client = _StubClient([
        _make_response(args=bad),
        _make_response(args=bad),
    ])
    agent = ArchitectAgent(client)
    with pytest.raises(ArchitectError, match="failed twice"):
        agent.design(insights=_insights())
    assert client.calls == 2


# ---------------------------------------------------------------------------
# Error paths (single attempt)
# ---------------------------------------------------------------------------


def test_design_raises_when_no_tool_call() -> None:
    """LLM responde texto sin llamar al tool — falla los 2 intentos."""
    text_resp = _make_response(finish=FinishReason.STOP, text="No usaré tools")
    client = _StubClient([text_resp, text_resp])
    agent = ArchitectAgent(client)
    with pytest.raises(ArchitectError, match="failed twice"):
        agent.design(insights=_insights())


def test_design_raises_when_wrong_tool_name() -> None:
    bad = _make_response(tool_name="otro_tool")
    client = _StubClient([bad, bad])
    agent = ArchitectAgent(client)
    with pytest.raises(ArchitectError):
        agent.design(insights=_insights())


def test_design_raises_when_tool_called_multiple_times() -> None:
    multi = _make_response(n_calls=2)
    client = _StubClient([multi, multi])
    agent = ArchitectAgent(client)
    with pytest.raises(ArchitectError):
        agent.design(insights=_insights())


def test_design_raises_when_args_invalid_against_draft_schema() -> None:
    bad_args = _valid_draft_args()
    bad_args.pop("variables")  # falta campo obligatorio
    client = _StubClient([
        _make_response(args=bad_args),
        _make_response(args=bad_args),
    ])
    agent = ArchitectAgent(client)
    with pytest.raises(ArchitectError):
        agent.design(insights=_insights())


def test_design_raises_when_compile_scm_fails() -> None:
    """Draft válido para schema, pero compile_scm falla (decorative edge)."""
    deco = _valid_draft_args()
    # Y NO usa X, pero edge declarado → compile_scm rebota.
    deco["variables"][1]["equation"] = "normal(0, 1)"
    client = _StubClient([
        _make_response(args=deco),
        _make_response(args=deco),
    ])
    agent = ArchitectAgent(client)
    with pytest.raises(ArchitectError):
        agent.design(insights=_insights())


# ---------------------------------------------------------------------------
# Tool spec exposure
# ---------------------------------------------------------------------------


def test_tool_spec_exposes_simplified_draft_schema() -> None:
    captured: dict = {}

    class _CapturingClient:
        def chat(self, messages, tools=None, model=None, temperature=None, max_tokens=None):
            captured["tools"] = list(tools) if tools else []
            return _make_response()

    agent = ArchitectAgent(_CapturingClient())
    agent.design(insights=_insights())
    tools = captured["tools"]
    assert len(tools) == 1
    assert tools[0].name == "emit_world_draft"
    params = tools[0].parameters
    # El schema del draft expone "variables", "edges" como list de objetos
    # con parent/child (no tuples / prefixItems).
    assert "properties" in params
    assert "variables" in params["properties"]
    assert "edges" in params["properties"]
