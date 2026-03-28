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
    build_intent_from_structured,
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
        assert isinstance(result, ClaimIntent)
        assert result.pattern == PatternClass.CAUSAL_EFFECT
        assert result.treatment == "A"

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
        assert isinstance(result, ClaimIntent)
        assert result.mediator == "M"

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
        assert isinstance(result, ClaimIntent)

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


# ---------------------------------------------------------------------------
# Structured claims (deterministic intent building)
# ---------------------------------------------------------------------------


def _make_structured_claim(
    claim_id: str = "sc1",
    text: str = "A has a positive causal effect on Y based on regression",
    relation_type: str = "causal_effect",
    treatment: str = "A",
    outcome: str = "Y",
    direction: str = "positive",
    **kwargs,
) -> ClaimCard:
    """Create a ClaimCard with structured fields."""
    return ClaimCard(
        claim_id=claim_id,
        claim_text=text,
        focus_variables=kwargs.pop("focus", [treatment, outcome]),
        confidence=kwargs.pop("confidence", 0.8),
        evidence_basis=[
            EvidenceRef(artifact_id="dataset_bg", rationale="regression analysis"),
        ],
        relation_type=relation_type,
        treatment=treatment,
        outcome=outcome,
        direction=direction,
        **kwargs,
    )


class TestBuildIntentFromStructured:
    """Test deterministic ClaimIntent construction from structured fields."""

    def test_causal_effect(self):
        card = _make_structured_claim()
        result = build_intent_from_structured(card, ["A", "B", "Y"])
        assert isinstance(result, ClaimIntent)
        assert result.pattern == PatternClass.CAUSAL_EFFECT
        assert result.treatment == "A"
        assert result.outcome == "Y"
        assert result.direction == Direction.POSITIVE

    def test_negative_direction(self):
        card = _make_structured_claim(direction="negative")
        result = build_intent_from_structured(card, ["A", "Y"])
        assert isinstance(result, ClaimIntent)
        assert result.direction == Direction.NEGATIVE

    def test_near_zero_direction(self):
        card = _make_structured_claim(direction="near_zero")
        result = build_intent_from_structured(card, ["A", "Y"])
        assert isinstance(result, ClaimIntent)
        assert result.direction == Direction.NEAR_ZERO

    def test_mediation_with_mediator(self):
        card = _make_structured_claim(
            relation_type="mediation",
            treatment="A",
            outcome="Y",
            mediator="M",
        )
        result = build_intent_from_structured(card, ["A", "M", "Y"])
        assert isinstance(result, ClaimIntent)
        assert result.pattern == PatternClass.MEDIATION
        assert result.mediator == "M"

    def test_mediation_without_mediator_fails(self):
        card = _make_structured_claim(relation_type="mediation")
        result = build_intent_from_structured(card, ["A", "Y"])
        assert isinstance(result, str)  # Error message
        assert "mediator" in result.lower()

    def test_heterogeneity_with_modifier(self):
        card = _make_structured_claim(
            relation_type="heterogeneity",
            modifier="Z",
        )
        result = build_intent_from_structured(card, ["A", "Y", "Z"])
        assert isinstance(result, ClaimIntent)
        assert result.pattern == PatternClass.HETEROGENEITY
        assert result.modifier == "Z"

    def test_confounding_with_confounder(self):
        card = _make_structured_claim(
            relation_type="confounding",
            confounder="B",
        )
        result = build_intent_from_structured(card, ["A", "B", "Y"])
        assert isinstance(result, ClaimIntent)
        assert result.pattern == PatternClass.CONFOUNDING
        assert result.confounder == "B"

    def test_observational_association_sets_evidence_type(self):
        card = _make_structured_claim(relation_type="observational_association")
        result = build_intent_from_structured(card, ["A", "Y"])
        assert isinstance(result, ClaimIntent)
        assert result.evidence_type == "observational"

    def test_invalid_relation_type_returns_error(self):
        card = _make_structured_claim(relation_type="magic")
        result = build_intent_from_structured(card, ["A", "Y"])
        assert isinstance(result, str)
        assert "Invalid relation_type" in result

    def test_invalid_direction_returns_error(self):
        card = _make_structured_claim(direction="maybe")
        result = build_intent_from_structured(card, ["A", "Y"])
        assert isinstance(result, str)
        assert "Invalid direction" in result

    def test_invalid_variable_name_returns_error(self):
        card = _make_structured_claim(treatment="NONEXISTENT")
        result = build_intent_from_structured(card, ["A", "B", "Y"])
        assert isinstance(result, str)
        assert "NONEXISTENT" in result
        assert "not found" in result

    def test_no_world_variables_skips_validation(self):
        card = _make_structured_claim(treatment="anything")
        result = build_intent_from_structured(card)
        assert isinstance(result, ClaimIntent)

    def test_missing_structured_fields_returns_error(self):
        card = _make_claim()  # Legacy card, no structured fields
        result = build_intent_from_structured(card)
        assert isinstance(result, str)
        assert "Missing" in result


class TestCompileStructuredClaim:
    """Test that compile_claim uses structured path when fields are present."""

    def test_structured_claim_bypasses_llm(self):
        """Structured claim should compile without LLM call."""
        card = _make_structured_claim()
        summary = _make_summary()

        def should_not_be_called(messages):
            raise AssertionError("LLM should not be called for structured claims")

        result = compile_claim(card, summary, llm_call=should_not_be_called)
        assert isinstance(result, CompilerOutput)
        assert result.compiled
        assert result.intent is not None
        assert result.intent.pattern == PatternClass.CAUSAL_EFFECT

    def test_structured_claim_compiles_without_llm(self):
        """Structured claim compiles correctly with llm_call=None."""
        card = _make_structured_claim()
        summary = _make_summary()
        result = compile_claim(card, summary, llm_call=None)
        assert isinstance(result, CompilerOutput)
        assert result.compiled

    def test_structured_bad_variable_produces_abstention(self):
        """Invalid variable name produces clean abstention."""
        card = _make_structured_claim(treatment="NONEXISTENT")
        summary = _make_summary()
        result = compile_claim(card, summary)
        assert not result.compiled
        assert "Structured field error" in result.abstention_reason

    def test_legacy_claim_still_uses_deterministic_fallback(self):
        """Claims without structured fields fall through to keyword fallback."""
        card = _make_claim(text="A causes Y to increase", focus=["A", "Y"])
        summary = _make_summary()
        result = compile_claim(card, summary, llm_call=None)
        assert isinstance(result, CompilerOutput)
        assert result.compiled

    def test_mixed_batch_both_paths(self):
        """Batch with structured + legacy claims uses correct path for each."""
        structured = _make_structured_claim("c1")
        legacy = _make_claim("c2", text="B causes Y to increase", focus=["B", "Y"])
        summary = _make_summary()
        results = compile_episode_claims([structured, legacy], summary)
        assert len(results) == 2
        assert all(isinstance(r, CompilerOutput) for r in results)
        # Structured should have intent with exact fields
        assert results[0].intent is not None
        assert results[0].intent.treatment == "A"
