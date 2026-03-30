"""Tests for OI Compiler LLM Extraction: prompt building + response parsing."""

from __future__ import annotations

import json

from sreg.models.open_investigation import ClaimCard, EvidenceRef
from sreg.tools.oi_compiler import (
    ClaimIntent,
    CompilerOutput,
    Direction,
    PatternClass,
    VariableAnchors,
    WorldSummary,
)
from sreg.tools.oi_extraction import (
    _deterministic_extract,
    _extract_json,
    build_extraction_prompt,
    compile_claim,
    compile_episode_claims,
    parse_extraction_response,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_claim(
    claim_id: str = "test_c1",
    text: str = "A has a positive causal effect on Y",
    focus: list[str] | None = None,
    tags: list[str] | None = None,
) -> ClaimCard:
    return ClaimCard(
        claim_id=claim_id,
        claim_text=text,
        focus_variables=focus or ["A", "Y"],
        confidence=0.8,
        evidence_basis=[
            EvidenceRef(artifact_id="dataset_bg", rationale="analysis"),
        ],
        pattern_tags=tags or [],
    )


def _make_summary() -> WorldSummary:
    """Minimal WorldSummary for testing."""
    def _anchors(name: str, is_obs: bool = True) -> VariableAnchors:
        return VariableAnchors(
            name=name, p10=1.0, p25=2.0, p50=5.0, p75=8.0, p90=9.0,
            mean=5.0, std=2.0, is_observable=is_obs,
        )

    return WorldSummary(
        world_id="test",
        target="Y",
        variables={
            "A": _anchors("A"),
            "B": _anchors("B"),
            "Y": _anchors("Y"),
            "M": _anchors("M"),
            "Z": _anchors("Z"),
        },
        observable_names=["A", "B", "M", "Y", "Z"],
    )


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------


class TestExtractJson:
    def test_plain_json(self):
        text = '{"pattern": "causal_effect"}'
        assert _extract_json(text) == '{"pattern": "causal_effect"}'

    def test_markdown_fenced(self):
        text = '```json\n{"pattern": "causal_effect"}\n```'
        assert _extract_json(text) == '{"pattern": "causal_effect"}'

    def test_markdown_no_lang(self):
        text = '```\n{"key": "value"}\n```'
        assert _extract_json(text) == '{"key": "value"}'

    def test_with_surrounding_text(self):
        text = 'Here is the result:\n{"pattern": "mediation"}\nDone.'
        assert _extract_json(text) == '{"pattern": "mediation"}'

    def test_no_json(self):
        assert _extract_json("no json here") is None


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


class TestBuildExtractionPrompt:
    def test_returns_messages_list(self):
        claim = _make_claim()
        messages = build_extraction_prompt(claim, ["A", "B", "Y"])

        assert isinstance(messages, list)
        assert all("role" in m and "content" in m for m in messages)

    def test_system_message_first(self):
        claim = _make_claim()
        messages = build_extraction_prompt(claim, ["A", "Y"])
        assert messages[0]["role"] == "system"

    def test_includes_exemplars(self):
        claim = _make_claim()
        messages = build_extraction_prompt(claim, ["A", "Y"], n_exemplars=3)

        # Should have: system + (3 positive * 2) + (2 abstention * 2) + 1 user
        # = 1 + 6 + 4 + 1 = 12
        assert len(messages) == 12

    def test_last_message_is_user_claim(self):
        claim = _make_claim(text="Temperature affects yield")
        messages = build_extraction_prompt(claim, ["temperature", "yield"])
        last = messages[-1]
        assert last["role"] == "user"
        assert "Temperature affects yield" in last["content"]

    def test_includes_focus_and_tags(self):
        claim = _make_claim(
            text="X causes Y to increase significantly",
            focus=["X", "Y"],
            tags=["causal_effect"],
        )
        messages = build_extraction_prompt(claim, ["X", "Y", "Z"])
        last = messages[-1]
        assert "Focus variables: X, Y" in last["content"]
        assert "Pattern hints: causal_effect" in last["content"]


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


class TestParseExtractionResponse:
    def test_parses_valid_causal_effect(self):
        response = json.dumps({
            "pattern": "causal_effect",
            "treatment": "A",
            "outcome": "Y",
            "direction": "positive",
            "evidence_type": "interventional",
        })
        result = parse_extraction_response(response, "c1")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].pattern == PatternClass.CAUSAL_EFFECT
        assert result[0].treatment == "A"

    def test_parses_mediation(self):
        response = json.dumps({
            "pattern": "mediation",
            "treatment": "A",
            "outcome": "Y",
            "direction": "positive",
            "mediator": "M",
            "evidence_type": "interventional",
        })
        result = parse_extraction_response(response, "c1")
        assert isinstance(result, list)
        assert result[0].mediator == "M"

    def test_parses_abstention(self):
        response = json.dumps({
            "abstention": True,
            "reason": "too vague",
        })
        result = parse_extraction_response(response, "c1")
        assert isinstance(result, CompilerOutput)
        assert result.status == "abstention"
        assert "too vague" in result.abstention_reason

    def test_handles_markdown_fenced(self):
        response = '```json\n{"pattern": "causal_effect", "treatment": "A", "outcome": "Y"}\n```'
        result = parse_extraction_response(response, "c1")
        assert isinstance(result, list)

    def test_handles_invalid_json(self):
        result = parse_extraction_response("not json at all", "c1")
        assert isinstance(result, CompilerOutput)
        assert result.status == "abstention"

    def test_handles_missing_fields(self):
        response = json.dumps({"pattern": "causal_effect"})  # missing treatment/outcome
        result = parse_extraction_response(response, "c1")
        assert isinstance(result, CompilerOutput)
        assert result.status == "abstention"

    def test_handles_invalid_pattern(self):
        response = json.dumps({
            "pattern": "invalid_pattern",
            "treatment": "A",
            "outcome": "Y",
        })
        result = parse_extraction_response(response, "c1")
        assert isinstance(result, CompilerOutput)
        assert result.status == "abstention"

    def test_parses_multi_unit_wrapper(self):
        """Multi-unit: {"intents": [...]} produces list of ClaimIntents."""
        response = json.dumps({
            "intents": [
                {
                    "pattern": "causal_effect",
                    "treatment": "A",
                    "outcome": "B",
                    "direction": "positive",
                },
                {
                    "pattern": "causal_effect",
                    "treatment": "B",
                    "outcome": "Y",
                    "direction": "negative",
                },
            ]
        })
        result = parse_extraction_response(response, "c1")
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].treatment == "A"
        assert result[0].outcome == "B"
        assert result[1].treatment == "B"
        assert result[1].outcome == "Y"
        assert result[1].direction == Direction.NEGATIVE
        # All intents get indexed claim_id
        assert result[0].claim_id == "c1::0"
        assert result[1].claim_id == "c1::1"

    def test_multi_unit_partial_failure(self):
        """Multi-unit with one invalid intent still returns the valid ones."""
        response = json.dumps({
            "intents": [
                {
                    "pattern": "causal_effect",
                    "treatment": "A",
                    "outcome": "Y",
                    "direction": "positive",
                },
                {
                    "pattern": "invalid_pattern",
                    "treatment": "B",
                    "outcome": "Y",
                },
            ]
        })
        result = parse_extraction_response(response, "c1")
        assert isinstance(result, list)
        assert len(result) == 1  # only the valid one

    def test_multi_unit_all_invalid_produces_abstention(self):
        """Multi-unit where all intents fail -> abstention."""
        response = json.dumps({
            "intents": [
                {"pattern": "bad1", "treatment": "A", "outcome": "Y"},
                {"pattern": "bad2", "treatment": "B", "outcome": "Y"},
            ]
        })
        result = parse_extraction_response(response, "c1")
        assert isinstance(result, CompilerOutput)
        assert result.status == "abstention"

    def test_multi_unit_empty_array_produces_abstention(self):
        response = json.dumps({"intents": []})
        result = parse_extraction_response(response, "c1")
        assert isinstance(result, CompilerOutput)
        assert result.status == "abstention"


# ---------------------------------------------------------------------------
# Deterministic fallback
# ---------------------------------------------------------------------------


class TestDeterministicExtract:
    def test_causal_effect_from_text(self):
        claim = _make_claim(
            text="A causes Y to increase",
            focus=["A", "Y"],
        )
        result = _deterministic_extract(claim, ["A", "B", "Y"])
        assert isinstance(result, ClaimIntent)
        assert result.pattern == PatternClass.CAUSAL_EFFECT
        assert result.direction == Direction.POSITIVE

    def test_mediation_from_tags(self):
        claim = _make_claim(
            text="A affects Y through M",
            focus=["A", "Y", "M"],
            tags=["mediation"],
        )
        result = _deterministic_extract(claim, ["A", "B", "M", "Y"])
        assert isinstance(result, ClaimIntent)
        assert result.pattern == PatternClass.MEDIATION
        assert result.mediator == "M"

    def test_negative_direction(self):
        claim = _make_claim(
            text="A decreases Y significantly",
            focus=["A", "Y"],
        )
        result = _deterministic_extract(claim, ["A", "Y"])
        assert isinstance(result, ClaimIntent)
        assert result.direction == Direction.NEGATIVE

    def test_near_zero_direction(self):
        claim = _make_claim(
            text="There is no significant effect of A on Y",
            focus=["A", "Y"],
        )
        result = _deterministic_extract(claim, ["A", "Y"])
        assert isinstance(result, ClaimIntent)
        assert result.direction == Direction.NEAR_ZERO

    def test_observational_from_keywords(self):
        claim = _make_claim(
            text="A and Y are positively correlated controlling for B",
            focus=["A", "Y", "B"],
        )
        result = _deterministic_extract(claim, ["A", "B", "Y"])
        assert isinstance(result, ClaimIntent)
        assert result.pattern == PatternClass.OBSERVATIONAL_ASSOCIATION
        assert result.evidence_type == "observational"

    def test_insufficient_variables_produces_abstention(self):
        claim = _make_claim(
            text="Something interesting about the overall pattern in the data",
            focus=["Q"],  # Q not in world vars, text doesn't mention W, V
        )
        result = _deterministic_extract(claim, ["W", "V"])
        assert isinstance(result, CompilerOutput)
        assert result.status == "abstention"


# ---------------------------------------------------------------------------
# Full compile_claim pipeline
# ---------------------------------------------------------------------------


class TestCompileClaim:
    def test_compile_with_deterministic_fallback(self):
        claim = _make_claim(
            text="A has a positive causal effect on Y",
            focus=["A", "Y"],
        )
        summary = _make_summary()
        result = compile_claim(claim, summary)

        assert isinstance(result, CompilerOutput)
        assert result.compiled
        assert len(result.specs) > 0

    def test_compile_with_mock_llm(self):
        claim = _make_claim(focus=["A", "Y"])
        summary = _make_summary()

        def mock_llm(messages):
            return json.dumps({
                "pattern": "causal_effect",
                "treatment": "A",
                "outcome": "Y",
                "direction": "positive",
                "evidence_type": "interventional",
            })

        result = compile_claim(claim, summary, llm_call=mock_llm)
        assert result.compiled
        assert len(result.specs) > 0

    def test_compile_with_llm_abstention(self):
        claim = _make_claim(text="Something vague")
        summary = _make_summary()

        def mock_llm(messages):
            return json.dumps({"abstention": True, "reason": "too vague"})

        result = compile_claim(claim, summary, llm_call=mock_llm)
        assert not result.compiled
        assert "too vague" in result.abstention_reason

    def test_compile_invalid_variable_produces_abstention(self):
        claim = _make_claim(
            text="X affects W strongly",
            focus=["X", "W"],  # W not in summary
        )
        summary = _make_summary()

        def mock_llm(messages):
            return json.dumps({
                "pattern": "causal_effect",
                "treatment": "X",
                "outcome": "W",
                "direction": "positive",
            })

        result = compile_claim(claim, summary, llm_call=mock_llm)
        assert not result.compiled
        assert "Validation failed" in result.abstention_reason

    def test_compile_episode_claims(self):
        claims = [
            _make_claim("c1", "A causes Y to increase significantly", ["A", "Y"]),
            _make_claim("c2", "B is positively associated with Y in the data",
                        ["B", "Y"], tags=["observational_association"]),
        ]
        summary = _make_summary()
        results = compile_episode_claims(claims, summary)
        assert len(results) == 2
        assert all(isinstance(r, CompilerOutput) for r in results)

    def test_compile_llm_exception_produces_abstention(self):
        """LLM provider errors produce abstention, not crash."""
        claim = _make_claim(focus=["A", "Y"])
        summary = _make_summary()

        def crashing_llm(messages):
            raise ConnectionError("API unreachable")

        result = compile_claim(claim, summary, llm_call=crashing_llm)
        assert not result.compiled
        assert "LLM extraction error" in result.abstention_reason

    def test_compile_llm_returns_non_string(self):
        """LLM returning non-string (e.g. structured object) is handled."""
        claim = _make_claim(focus=["A", "Y"])
        summary = _make_summary()

        def weird_llm(messages):
            return {"not": "a string"}

        result = compile_claim(claim, summary, llm_call=weird_llm)
        # Should handle gracefully (converts to str or abstains)
        assert isinstance(result, CompilerOutput)

    def test_compile_multi_unit_from_llm(self):
        """Compound claim → N intents → N CompiledUnits."""
        claim = _make_claim("c_multi", "A increases B, and B increases Y", ["A", "B", "Y"])
        summary = _make_summary()

        def mock_llm(messages):
            return json.dumps({
                "intents": [
                    {
                        "pattern": "causal_effect",
                        "treatment": "A",
                        "outcome": "B",
                        "direction": "positive",
                    },
                    {
                        "pattern": "causal_effect",
                        "treatment": "B",
                        "outcome": "Y",
                        "direction": "positive",
                    },
                ]
            })

        result = compile_claim(claim, summary, llm_call=mock_llm)
        assert result.compiled
        assert result.status == "compiled"
        assert len(result.units) == 2
        assert result.units[0].intent.treatment == "A"
        assert result.units[0].intent.outcome == "B"
        assert result.units[1].intent.treatment == "B"
        assert result.units[1].intent.outcome == "Y"
        # Flat specs includes all units' specs
        assert len(result.specs) >= 2

    def test_compile_multi_unit_partial(self):
        """One intent valid, one invalid → partial compilation."""
        claim = _make_claim("c_partial", "A increases Y, Q increases W", ["A", "Y"])
        summary = _make_summary()

        def mock_llm(messages):
            return json.dumps({
                "intents": [
                    {
                        "pattern": "causal_effect",
                        "treatment": "A",
                        "outcome": "Y",
                        "direction": "positive",
                    },
                    {
                        "pattern": "causal_effect",
                        "treatment": "Q",  # not in world
                        "outcome": "W",    # not in world
                        "direction": "positive",
                    },
                ]
            })

        result = compile_claim(claim, summary, llm_call=mock_llm)
        assert result.compiled
        assert result.status == "partial"
        assert len(result.units) == 1
        assert len(result.uncompiled_fragments) == 1

    def test_compile_multi_unit_all_fail(self):
        """All intents fail validation → abstention."""
        claim = _make_claim("c_allfail", "Q increases W, W increases X")
        summary = _make_summary()

        def mock_llm(messages):
            return json.dumps({
                "intents": [
                    {
                        "pattern": "causal_effect",
                        "treatment": "Q",
                        "outcome": "W",
                        "direction": "positive",
                    },
                    {
                        "pattern": "causal_effect",
                        "treatment": "W",
                        "outcome": "X",
                        "direction": "positive",
                    },
                ]
            })

        result = compile_claim(claim, summary, llm_call=mock_llm)
        assert not result.compiled
        assert result.status == "abstention"
        assert "2 intent(s) failed" in result.abstention_reason
