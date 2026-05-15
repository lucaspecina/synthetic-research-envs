"""Tests del wiring de `ValidatorAgent`.

Foco: parsing del output del LLM, conversor draft → `ValidatorVote`,
single retry tras error, propagación de errores deterministas. NO
valida contenido semántico (eso requiere LLM real corriendo contra el
Environment, ver `scripts/run_validator.py` cuando exista).
"""

from __future__ import annotations

import pytest

from sreg.inference.protocol import (
    ChatResponse,
    FinishReason,
    Message,
    MessageRole,
    ToolCall,
    Usage,
)
from sreg.v1_5.agents.validator import (
    ValidatorAgent,
    ValidatorError,
    _compute_delta,
)
from sreg.v1_5.contracts import (
    EvidenceArtifact,
    IntendedPhenomenon,
    ValidatorVote,
    WorldSpec,
    WorldMetadata,
    VariableSpec,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _world() -> WorldSpec:
    return WorldSpec(
        formalism="scm",
        variables=[
            VariableSpec(name="X", equation="normal(0, 1)"),
            VariableSpec(name="Y", equation="2*X + normal(0, 0.5)"),
        ],
        edges=[("X", "Y")],
        metadata=WorldMetadata(domain="generic"),
        intended_phenomena=[
            IntendedPhenomenon(
                id="ip_xy",
                kind="non_linearity",
                description="X causes Y linearly with positive sign",
                relevant_variables=["X", "Y"],
            )
        ],
    )


def _phenomenon() -> IntendedPhenomenon:
    return IntendedPhenomenon(
        id="ip_xy",
        kind="non_linearity",
        description="X causes Y linearly with positive sign",
        relevant_variables=["X", "Y"],
    )


def _stub_env():
    """Stub mínimo del SCMEnvironment para inyectar en el namespace.

    No es un SCMEnvironment real — los tests deterministas no ejecutan
    código del LLM. Sirve solo para que la firma del agente acepte el
    objeto.
    """

    class _StubEnv:
        formalism = "scm"
        variables = ["X", "Y"]
        observable_variables = ["X", "Y"]

    return _StubEnv()


def _valid_vote_args() -> dict:
    """Draft mínimo y válido emitido por el LLM."""
    return {
        "vote": "passes",
        "margin": 0.9,
        "fragility": 0.2,
        "evidence": [
            {
                "script": "df = env.observe(n=1000, seed=0); df[['X','Y']].corr()",
                "numerical_result": {"corr_xy": 0.97, "n": 1000},
                "notes": "correlación positiva fuerte como predicho",
                "tag": "smoke_corr",
            }
        ],
        "failure_reason": None,
        "diagnostics": {"seeds": 1},
    }


# ---------------------------------------------------------------------------
# Stub client compatible con ToolEnrichedClient
# ---------------------------------------------------------------------------


class _StubClient:
    """ModelClient que devuelve respuestas pre-armadas en orden."""

    def __init__(self, responses: list[ChatResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

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
        self.calls.append(
            {"messages": list(messages), "tools": list(tools) if tools else []}
        )
        return self.responses.pop(0)


def _make_response(
    *,
    args: dict | None = None,
    tool_name: str = "emit_validator_vote",
    finish: FinishReason = FinishReason.TOOL_CALLS,
    n_calls: int = 1,
    text: str | None = None,
) -> ChatResponse:
    tool_calls = [
        ToolCall(id=f"c{i}", name=tool_name, arguments=args or _valid_vote_args())
        for i in range(n_calls)
    ]
    return ChatResponse(
        message=Message(role=MessageRole.ASSISTANT, content=text),
        tool_calls=tool_calls if finish == FinishReason.TOOL_CALLS else [],
        finish_reason=finish,
        usage=Usage(input_tokens=10, output_tokens=10, total_tokens=20),
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_validate_returns_vote_on_valid_draft() -> None:
    client = _StubClient([_make_response()])
    agent = ValidatorAgent(client)
    vote = agent.validate(
        world=_world(),
        env=_stub_env(),
        phenomenon=_phenomenon(),
    )
    assert isinstance(vote, ValidatorVote)
    assert vote.vote == "passes"
    assert vote.margin == 0.9
    assert vote.fragility == 0.2
    assert vote.target_intended_id == "ip_xy"
    assert vote.iteration == 0
    assert vote.delta_from_previous is None
    assert len(vote.evidence) == 1
    assert vote.failure_reason is None
    assert vote.validator_id.startswith("validator_ip_xy_iter0")


def test_validate_passes_failure_reason_through_for_fails() -> None:
    args = _valid_vote_args()
    args["vote"] = "fails"
    args["margin"] = 0.05
    args["failure_reason"] = "diff_xy = 0.003, no signo positivo detectable"
    client = _StubClient([_make_response(args=args)])
    agent = ValidatorAgent(client)
    vote = agent.validate(
        world=_world(),
        env=_stub_env(),
        phenomenon=_phenomenon(),
    )
    assert vote.vote == "fails"
    assert vote.failure_reason is not None
    assert "diff_xy" in vote.failure_reason


def test_validate_uses_custom_validator_id_when_provided() -> None:
    client = _StubClient([_make_response()])
    agent = ValidatorAgent(client)
    vote = agent.validate(
        world=_world(),
        env=_stub_env(),
        phenomenon=_phenomenon(),
        validator_id="custom_id_42",
    )
    assert vote.validator_id == "custom_id_42"


# ---------------------------------------------------------------------------
# delta_from_previous
# ---------------------------------------------------------------------------


def test_compute_delta_returns_none_when_no_previous() -> None:
    assert _compute_delta(previous_vote=None) is None


def test_compute_delta_compares_canonical_fields() -> None:
    prev = ValidatorVote(
        validator_id="v_prev",
        target_intended_id="ip_xy",
        iteration=0,
        vote="weak_pass",
        margin=0.3,
        fragility=0.6,
        evidence=[
            EvidenceArtifact(
                script="...",
                numerical_result={"x": 1},
            )
        ],
        failure_reason="weak signal",
    )
    delta = _compute_delta(previous_vote=prev)
    assert delta == {
        "previous_vote": "weak_pass",
        "previous_margin": 0.3,
        "previous_fragility": 0.6,
    }


def test_validate_rejects_iteration_zero_with_previous_vote() -> None:
    prev = ValidatorVote(
        validator_id="v_prev",
        target_intended_id="ip_xy",
        iteration=0,
        vote="passes",
        margin=0.9,
        fragility=0.2,
        evidence=[
            EvidenceArtifact(script="...", numerical_result={"x": 1})
        ],
    )
    agent = ValidatorAgent(_StubClient([]))
    with pytest.raises(ValidatorError, match="iteration=0"):
        agent.validate(
            world=_world(),
            env=_stub_env(),
            phenomenon=_phenomenon(),
            iteration=0,
            previous_vote=prev,
        )


def test_validate_passes_delta_when_iteration_gt_zero() -> None:
    prev = ValidatorVote(
        validator_id="v_prev",
        target_intended_id="ip_xy",
        iteration=0,
        vote="weak_pass",
        margin=0.3,
        fragility=0.6,
        evidence=[
            EvidenceArtifact(script="...", numerical_result={"x": 1})
        ],
        failure_reason="weak signal",
    )
    client = _StubClient([_make_response()])
    agent = ValidatorAgent(client)
    vote = agent.validate(
        world=_world(),
        env=_stub_env(),
        phenomenon=_phenomenon(),
        iteration=1,
        previous_vote=prev,
    )
    assert vote.iteration == 1
    assert vote.delta_from_previous == {
        "previous_vote": "weak_pass",
        "previous_margin": 0.3,
        "previous_fragility": 0.6,
    }


# ---------------------------------------------------------------------------
# Single retry
# ---------------------------------------------------------------------------


def test_validate_retries_once_on_first_failure() -> None:
    # Primer intento: vote=fails sin failure_reason → falla schema.
    bad_args = _valid_vote_args()
    bad_args["vote"] = "fails"
    bad_args["failure_reason"] = None
    client = _StubClient([
        _make_response(args=bad_args),  # falla
        _make_response(),  # retry OK
    ])
    agent = ValidatorAgent(client)
    vote = agent.validate(
        world=_world(),
        env=_stub_env(),
        phenomenon=_phenomenon(),
    )
    assert vote.vote == "passes"
    assert len(client.calls) == 2


def test_validate_raises_after_retry_also_fails() -> None:
    bad_args = _valid_vote_args()
    bad_args["evidence"] = []  # min_length=1 → falla
    client = _StubClient([
        _make_response(args=bad_args),
        _make_response(args=bad_args),
    ])
    agent = ValidatorAgent(client)
    with pytest.raises(ValidatorError, match="failed twice"):
        agent.validate(
            world=_world(),
            env=_stub_env(),
            phenomenon=_phenomenon(),
        )
    assert len(client.calls) == 2


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_validate_raises_when_no_tool_call() -> None:
    text_resp = _make_response(finish=FinishReason.STOP, text="No usaré tools")
    # ToolEnrichedClient: si finish_reason != TOOL_CALLS, sale del loop
    # con esa response. ValidatorAgent debe detectarlo y rebotar.
    client = _StubClient([text_resp, text_resp])
    agent = ValidatorAgent(client)
    with pytest.raises(ValidatorError, match="failed twice"):
        agent.validate(
            world=_world(),
            env=_stub_env(),
            phenomenon=_phenomenon(),
        )


def test_validate_raises_when_wrong_tool_name() -> None:
    # Tool desconocido (no en SOLVER_TOOLS y no en custom). ToolEnrichedClient
    # lo considera terminal → retorna response. ValidatorAgent detecta nombre
    # incorrecto.
    bad = _make_response(tool_name="otro_tool")
    client = _StubClient([bad, bad])
    agent = ValidatorAgent(client)
    with pytest.raises(ValidatorError, match="tools que no son"):
        agent.validate(
            world=_world(),
            env=_stub_env(),
            phenomenon=_phenomenon(),
        )


def test_validate_raises_when_tool_called_multiple_times() -> None:
    multi = _make_response(n_calls=2)
    client = _StubClient([multi, multi])
    agent = ValidatorAgent(client)
    with pytest.raises(ValidatorError, match="veces"):
        agent.validate(
            world=_world(),
            env=_stub_env(),
            phenomenon=_phenomenon(),
        )


def test_validate_raises_when_args_invalid_against_draft_schema() -> None:
    bad = _valid_vote_args()
    bad.pop("vote")  # campo obligatorio
    client = _StubClient([
        _make_response(args=bad),
        _make_response(args=bad),
    ])
    agent = ValidatorAgent(client)
    with pytest.raises(ValidatorError):
        agent.validate(
            world=_world(),
            env=_stub_env(),
            phenomenon=_phenomenon(),
        )


# ---------------------------------------------------------------------------
# Tool spec exposure
# ---------------------------------------------------------------------------


def test_tool_spec_exposes_simplified_draft_schema() -> None:
    client = _StubClient([_make_response()])
    agent = ValidatorAgent(client)
    agent.validate(
        world=_world(),
        env=_stub_env(),
        phenomenon=_phenomenon(),
    )
    # Las tools que vio el base client: SOLVER_TOOLS (python_exec + think)
    # + custom emit_validator_vote.
    tools_seen = client.calls[0]["tools"]
    names = [t.name for t in tools_seen]
    assert "emit_validator_vote" in names
    assert "python_exec" in names  # mergeado por ToolEnrichedClient
    assert "think" in names

    emit_tool = next(t for t in tools_seen if t.name == "emit_validator_vote")
    params = emit_tool.parameters
    assert "properties" in params
    for required_field in ("vote", "margin", "fragility", "evidence"):
        assert required_field in params["properties"]
