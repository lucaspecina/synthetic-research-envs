"""Tests for the abstention contract in oi_sq_compiler.

Scope: only the abstention contract added by P06 G.1.
- `_is_explicit_abstention` correctly classifies LLM responses
- `compile_sq_to_specs` returns abstained=True (not error) when the
  LLM returns an explicit empty array
- `SQCompileResult.repr` distinguishes abstained from error
- The contract is intentionally minimal: scoring, matching, and
  required-fallback are unchanged.
"""
from __future__ import annotations

from sreg.models.open_investigation import SQTier
from sreg.tools.oi_compiler import VariableAnchors, WorldSummary
from sreg.tools.oi_sq_compiler import (
    SQCompileResult,
    _is_explicit_abstention,
    compile_sq_to_specs,
)


# ---------------------------------------------------------------------------
# _is_explicit_abstention — pure helper
# ---------------------------------------------------------------------------


class TestIsExplicitAbstention:
    def test_plain_empty_array_is_abstention(self):
        assert _is_explicit_abstention("[]") is True

    def test_whitespace_padded_empty_array_is_abstention(self):
        assert _is_explicit_abstention("  []  ") is True

    def test_empty_array_with_inner_whitespace_is_abstention(self):
        assert _is_explicit_abstention("[ ]") is True
        assert _is_explicit_abstention("[\n]") is True
        assert _is_explicit_abstention("[\n  \n]") is True

    def test_fenced_empty_array_is_abstention(self):
        assert _is_explicit_abstention("```json\n[]\n```") is True
        assert _is_explicit_abstention("```\n[]\n```") is True

    def test_empty_response_is_not_abstention(self):
        assert _is_explicit_abstention("") is False
        assert _is_explicit_abstention("   ") is False

    def test_plain_text_is_not_abstention(self):
        assert _is_explicit_abstention("I cannot answer this question.") is False

    def test_non_empty_array_is_not_abstention(self):
        assert _is_explicit_abstention('[{"spec": {}}]') is False

    def test_object_is_not_abstention(self):
        assert _is_explicit_abstention('{"abstain": true}') is False


# ---------------------------------------------------------------------------
# SQCompileResult contract — abstained vs error vs success
# ---------------------------------------------------------------------------


class TestSQCompileResultContract:
    def test_default_state_is_error_not_success_not_abstained(self):
        r = SQCompileResult()
        assert r.success is False
        assert r.abstained is False
        assert r.errors == []

    def test_abstained_result_is_not_success_not_error(self):
        r = SQCompileResult(
            abstained=True,
            abstain_reason="model-dependent quantity",
        )
        assert r.success is False
        assert r.abstained is True
        assert r.abstain_reason == "model-dependent quantity"
        assert r.errors == []

    def test_error_result_is_not_abstained(self):
        r = SQCompileResult(errors=["LLM call failed"])
        assert r.success is False
        assert r.abstained is False
        assert r.errors == ["LLM call failed"]

    def test_repr_distinguishes_three_states(self):
        ok = SQCompileResult(errors=["dummy"])
        assert "FAIL" in repr(ok)

        abst = SQCompileResult(abstained=True, abstain_reason="why")
        assert "ABSTAINED" in repr(abst)
        assert "why" in repr(abst)


# ---------------------------------------------------------------------------
# compile_sq_to_specs — end-to-end with stub LLM
# ---------------------------------------------------------------------------


def _stub_summary() -> WorldSummary:
    """Tiny WorldSummary fixture so compile_sq_to_specs has var validation."""
    anchors = {
        var: VariableAnchors(
            name=var, p10=0.0, p25=0.25, p50=0.5, p75=0.75, p90=1.0,
            mean=0.5, std=0.3, is_observable=True,
        )
        for var in ("T", "Y", "W")
    }
    return WorldSummary(
        world_id="test_world",
        target="Y",
        variables=anchors,
        observable_names=["T", "W", "Y"],
    )


class TestCompileSQToSpecsAbstention:
    def test_explicit_empty_array_returns_abstained_not_error(self):
        """LLM returning [] is abstention, not a compile error."""
        def fake_llm(system: str, user: str) -> str:
            return "[]"

        result = compile_sq_to_specs(
            sq_id="sq_test",
            text_gloss="What is the OLS coefficient of T in lm(Y ~ T + W)?",
            focus_variables=("T", "Y"),
            tier=SQTier.HIGH,
            summary=_stub_summary(),
            llm_call=fake_llm,
        )
        assert result.success is False
        assert result.abstained is True
        assert result.abstain_reason is not None
        assert result.errors == []

    def test_fenced_empty_array_is_also_abstention(self):
        """LLM may wrap [] in markdown fences; still abstention."""
        def fake_llm(system: str, user: str) -> str:
            return "```json\n[]\n```"

        result = compile_sq_to_specs(
            sq_id="sq_test",
            text_gloss="What is the standardized beta of T?",
            focus_variables=("T",),
            tier=SQTier.HIGH,
            summary=_stub_summary(),
            llm_call=fake_llm,
        )
        assert result.abstained is True
        assert result.success is False

    def test_plain_text_is_compile_error_not_abstention(self):
        """Non-array text is still a compile error, not abstention."""
        def fake_llm(system: str, user: str) -> str:
            return "I cannot compile this."

        result = compile_sq_to_specs(
            sq_id="sq_test",
            text_gloss="Some question",
            focus_variables=(),
            tier=SQTier.HIGH,
            summary=_stub_summary(),
            llm_call=fake_llm,
        )
        assert result.abstained is False
        assert result.success is False
        assert result.errors  # has at least one error

    def test_llm_call_exception_is_error_not_abstention(self):
        """An LLM call failure is an error, never abstention."""
        def boom_llm(system: str, user: str) -> str:
            raise RuntimeError("boom")

        result = compile_sq_to_specs(
            sq_id="sq_test",
            text_gloss="Some question",
            focus_variables=(),
            tier=SQTier.HIGH,
            summary=_stub_summary(),
            llm_call=boom_llm,
        )
        assert result.abstained is False
        assert result.success is False
        assert any("LLM call failed" in e for e in result.errors)
