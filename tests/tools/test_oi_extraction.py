"""Tests for OI extraction: grammar-direct compilation contract."""

from __future__ import annotations

import json

from sreg.models.open_investigation import ClaimCard, EvidenceRef
from sreg.tools.oi_compiler import build_world_summary, CompilerOutput
from sreg.tools.oi_extraction import compile_claim, compile_claim_direct
from sreg.world.scm import SCMWorld


def _test_world() -> SCMWorld:
    return SCMWorld(
        id="ext-test",
        graph={"A": [], "Y": ["A"]},
        equations={
            "A": lambda p, rng: rng.normal(0, 1),
            "Y": lambda p, rng: 0.5 * p["A"] + rng.normal(0, 0.3),
        },
    )


def _make_claim(claim_id: str = "c1") -> ClaimCard:
    return ClaimCard(
        claim_id=claim_id,
        claim_text="A has a positive causal effect on Y",
        confidence=0.8,
        focus_variables=["A", "Y"],
        evidence_basis=[EvidenceRef(
            artifact_id="dataset_bg", description="regression",
            rationale="OLS shows positive coefficient",
        )],
    )


# Valid AtomicSpec JSON that compile_claim_direct should accept
_VALID_SPEC_JSON = json.dumps([{
    "spec_id": "s1",
    "arms": [
        {"label": "hi", "kind": "intervene", "values": {"A": 1.0}},
        {"label": "lo", "kind": "intervene", "values": {"A": -1.0}},
    ],
    "measurement": {"kind": "mean", "target": "Y"},
    "comparison": {"kind": "difference", "ref_arm": "lo"},
    "assertion": {"kind": "positive"},
}])


class TestCompileClaimContract:
    def test_no_llm_returns_abstention(self):
        """compile_claim(llm_call=None) must abstain cleanly."""
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)
        result = compile_claim(_make_claim(), summary, llm_call=None)
        assert not result.compiled
        assert result.status == "abstention"
        assert "No LLM" in result.abstention_reason

    def test_valid_json_compiles(self):
        """Mock LLM returning valid spec JSON produces compiled output."""
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)

        def mock_llm(*args, **kwargs):
            return _VALID_SPEC_JSON

        result = compile_claim(_make_claim(), summary, llm_call=mock_llm)
        assert result.compiled
        assert len(result.specs) == 1
        assert result.specs[0].spec_id == "s1"

    def test_garbage_json_returns_abstention(self):
        """Mock LLM returning garbage produces abstention."""
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)

        def mock_llm(*args, **kwargs):
            return "this is not json at all"

        result = compile_claim(_make_claim(), summary, llm_call=mock_llm)
        assert not result.compiled
        assert result.status == "abstention"

    def test_llm_exception_returns_abstention(self):
        """Mock LLM that raises produces abstention."""
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)

        def mock_llm(*args, **kwargs):
            raise RuntimeError("API timeout")

        result = compile_claim(_make_claim(), summary, llm_call=mock_llm)
        assert not result.compiled
        assert result.status == "abstention"

    def test_partial_when_some_specs_fail(self):
        """One valid + one invalid spec produces partial status."""
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)

        mixed_json = json.dumps([
            {
                "spec_id": "s1",
                "arms": [
                    {"label": "hi", "kind": "intervene", "values": {"A": 1.0}},
                    {"label": "lo", "kind": "intervene", "values": {"A": -1.0}},
                ],
                "measurement": {"kind": "mean", "target": "Y"},
                "comparison": {"kind": "difference", "ref_arm": "lo"},
                "assertion": {"kind": "positive"},
            },
            {
                "spec_id": "s2",
                "arms": [
                    {"label": "x", "kind": "intervene", "values": {"FAKE_VAR": 1.0}},
                ],
                "measurement": {"kind": "mean", "target": "Y"},
                "comparison": {"kind": "identity"},
                "assertion": {"kind": "positive"},
            },
        ])

        def mock_llm(*args, **kwargs):
            return mixed_json

        result = compile_claim(_make_claim(), summary, llm_call=mock_llm)
        assert result.compiled
        assert result.status == "partial"
        assert len(result.specs) == 1
        assert len(result.uncompiled_fragments) > 0


class TestCompileClaimDirectAbstention:
    """H0 port: Flow A must distinguish explicit abstention ([]) from fallback.

    Parallels tests/tools/test_oi_sq_compiler.py::TestCompileSQToSpecsAbstention.
    When the LLM returns `[]` per the abstention contract (model-dependent,
    temporal, study-design, power, open-ended optimization), the compiler must
    return status='abstention' with deliberate_abstention=True. Any other
    failure path (crash, parse error, garbage) is a fallback abstention with
    deliberate_abstention=False.
    """

    def test_explicit_empty_array_returns_deliberate_abstention(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)

        def mock_llm(*args, **kwargs):
            return "[]"

        result = compile_claim_direct(_make_claim(), summary, llm_call=mock_llm)
        assert isinstance(result, CompilerOutput)
        assert result.status == "abstention"
        assert result.deliberate_abstention is True
        assert result.abstained_deliberately is True
        assert result.abstained_by_fallback is False
        assert "abstention contract" in (result.abstention_reason or "")

    def test_fenced_empty_array_is_also_deliberate(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)

        def mock_llm(*args, **kwargs):
            return "```json\n[]\n```"

        result = compile_claim_direct(_make_claim(), summary, llm_call=mock_llm)
        assert isinstance(result, CompilerOutput)
        assert result.status == "abstention"
        assert result.deliberate_abstention is True

    def test_plain_text_is_fallback_not_deliberate(self):
        """Garbage text must go through None->fallback abstention path."""
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)

        def mock_llm(*args, **kwargs):
            return "I cannot answer this claim"

        # compile_claim_direct returns None for parse failures;
        # compile_claim wraps that as a fallback abstention.
        direct = compile_claim_direct(_make_claim(), summary, llm_call=mock_llm)
        assert direct is None

        wrapped = compile_claim(_make_claim(), summary, llm_call=mock_llm)
        assert wrapped.status == "abstention"
        assert wrapped.deliberate_abstention is False
        assert wrapped.abstained_by_fallback is True

    def test_llm_exception_is_fallback_not_deliberate(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)

        def mock_llm(*args, **kwargs):
            raise RuntimeError("API timeout")

        direct = compile_claim_direct(_make_claim(), summary, llm_call=mock_llm)
        assert direct is None

        wrapped = compile_claim(_make_claim(), summary, llm_call=mock_llm)
        assert wrapped.status == "abstention"
        assert wrapped.deliberate_abstention is False
        assert wrapped.abstained_by_fallback is True

    def test_no_llm_is_fallback_not_deliberate(self):
        """llm_call=None is an infra failure, not an LLM-signaled abstention."""
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)

        result = compile_claim(_make_claim(), summary, llm_call=None)
        assert result.status == "abstention"
        assert result.deliberate_abstention is False
        assert result.abstained_by_fallback is True
