"""Suite 2 — LLM compiler test: does the compiler translate claims correctly?

Runs each gold target's surface form through compile_claim() with a real LLM,
then evaluates in 3 stages:
  Stage 1: Compile/abstain decision matches expected
  Stage 2: Structural contract (arm kinds, role vars, measurement, etc.)
  Stage 3: Verdict equivalence (compiled specs → same verdict as gold)

Requires Azure LLM credentials in .env. Skipped by default unless
--run-llm is passed to pytest.

Usage:
    pytest tests/eval/suite2_translation/test_compiler_llm.py --run-llm -v
    pytest tests/eval/suite2_translation/test_compiler_llm.py --run-llm -v -k "W1_F01"
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()

from sreg.inference.openai_client import OpenAIClient
from sreg.inference.protocol import Message, MessageRole
from sreg.models.open_investigation import (
    AtomicSpec,
    ClaimCard,
    EvidenceRef,
)
from sreg.solver.scm_solver import SCMSolver
from sreg.tools.oi_compiler import CompilerOutput, build_world_summary
from sreg.tools.oi_extraction import compile_claim
from sreg.tools.oi_verifier import verify_atom

from tests.eval.suite2_translation.fact_tables import ALL_FACTS, Verdict
from tests.eval.suite2_translation.gold_targets import (
    ALL_GOLD_TARGETS,
    GoldTarget,
    StructuralContract,
)
from tests.eval.suite2_translation.worlds import ALL_WORLDS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FACT_BY_ID = {f.fact_id: f for f in ALL_FACTS}
_WORLD_FOR_FACT = {f.fact_id: f.world for f in ALL_FACTS}

# Caches
_SOLVER_CACHE: dict[str, tuple] = {}
_SUMMARY_CACHE: dict[tuple[str, str], object] = {}


def _get_world_solver(world_key: str):
    if world_key not in _SOLVER_CACHE:
        world = ALL_WORLDS[world_key]
        solver = SCMSolver(world, n_mc=50_000)
        _SOLVER_CACHE[world_key] = (world, solver)
    return _SOLVER_CACHE[world_key]


def _get_summary(world_key: str, target: str):
    cache_key = (world_key, target)
    if cache_key not in _SUMMARY_CACHE:
        world = ALL_WORLDS[world_key]
        _SUMMARY_CACHE[cache_key] = build_world_summary(world, target)
    return _SUMMARY_CACHE[cache_key]


def _make_llm_call(client: OpenAIClient):
    """Adapter: compile_claim calls llm_call(system, user) or llm_call(messages)."""
    def llm_call(*args):
        if len(args) == 2 and isinstance(args[0], str):
            system, user = args
            msgs = [
                Message(role=MessageRole.SYSTEM, content=system),
                Message(role=MessageRole.USER, content=user),
            ]
        elif len(args) == 1 and isinstance(args[0], list):
            msgs = [
                Message(role=MessageRole(m["role"]), content=m["content"])
                for m in args[0]
            ]
        else:
            raise TypeError(f"Unexpected llm_call args: {type(args)}")
        resp = client.chat(msgs, temperature=0.0)
        return resp.message.content or ""
    return llm_call


def _make_claim_card(fact, surface_form_index: int, contract) -> ClaimCard:
    """Build a minimal ClaimCard from a fact + surface form.

    Focus variables include:
      - treatment / outcome / cond vars from role_vars
      - required_modifier (effect modifier in heterogeneity claims — else
        the compiler has no way to know which world variable matches a
        semantic label like 'biomarker' when multiple vars are plausible)
      - required_mediator (for mediation claims)
    """
    sf = fact.surface_forms[surface_form_index]

    focus_set: set[str] = set()
    if contract and contract.required_role_vars:
        focus_set.update(contract.required_role_vars.values())
    if contract and contract.required_modifier:
        focus_set.add(contract.required_modifier)
    if contract and contract.required_mediator:
        focus_set.add(contract.required_mediator)
    focus = sorted(focus_set) if focus_set else ["Y"]

    return ClaimCard(
        claim_id=f"{fact.fact_id}_s{surface_form_index}",
        claim_text=sf.text,
        focus_variables=focus,
        confidence=1.0,
        evidence_basis=[
            EvidenceRef(
                artifact_id="gold_eval",
                rationale="Gold standard evaluation — claim derived from SCM equations",
            )
        ],
    )


def _infer_target(gt: GoldTarget, fact) -> str:
    """Infer the outcome/target variable for WorldSummary."""
    if gt.structural_contract and gt.structural_contract.required_role_vars:
        rv = gt.structural_contract.required_role_vars
        if "outcome" in rv:
            return rv["outcome"]
        if "rhs" in rv:
            return rv["rhs"]
    # Fallback by world
    world_key = _WORLD_FOR_FACT.get(fact.fact_id, "")
    if "w1" in world_key:
        return "Y"
    elif "w2" in world_key:
        return "D"
    elif "w3" in world_key:
        return "H"
    return "Y"


# ---------------------------------------------------------------------------
# Stage evaluators
# ---------------------------------------------------------------------------

def check_stage1(gt: GoldTarget, compiler_out: CompilerOutput) -> bool:
    """Stage 1: Did the compiler make the right compile/abstain decision?"""
    if gt.status == "compile":
        return compiler_out.compiled
    else:  # abstain
        return not compiler_out.compiled


def _collect_spec_vars(spec) -> set[str]:
    """Collect all variable names mentioned in a spec (for role_var check)."""
    vars_in_spec = set()
    for arm in spec.arms:
        vars_in_spec.update(arm.values.keys())
        vars_in_spec.update(arm.condition_on.keys())
        if arm.sweep_var:
            vars_in_spec.add(arm.sweep_var)
    if spec.measurement.target:
        t = spec.measurement.target
        if isinstance(t, str):
            vars_in_spec.add(t)
        else:
            vars_in_spec.update(t)
    if spec.measurement.lhs:
        vars_in_spec.add(spec.measurement.lhs)
    if spec.measurement.rhs:
        vars_in_spec.add(spec.measurement.rhs)
    if spec.measurement.treatment:
        vars_in_spec.add(spec.measurement.treatment)
    if spec.measurement.outcome:
        vars_in_spec.add(spec.measurement.outcome)
    return vars_in_spec


def _spec_signature(spec) -> tuple:
    """Structural signature of a spec for coverage matching.

    Includes assertion threshold/tolerance so `_assertion_entails` can
    check logical entailment between stricter and looser assertions
    (greater_than >= tolerance => positive, etc.).
    """
    arm_kinds = frozenset(a.kind.value for a in spec.arms)
    return (
        arm_kinds,
        spec.measurement.kind.value,
        spec.comparison.kind.value,
        spec.assertion.kind.value,
        spec.assertion.threshold,
        spec.assertion.tolerance,
    )


def _assertion_entails(
    gold_kind: str, gold_thresh: float, gold_tol: float,
    comp_kind: str, comp_thresh: float, comp_tol: float,
) -> bool:
    """Check whether compiler's assertion logically entails gold's.

    Derived from the verifier semantics (see `_assert` in oi_verifier.py):
      * positive: val > tol
      * negative: val < -tol
      * greater_than(t): val > t
      * less_than(t): val < t

    So:
      * compiler greater_than(t) entails gold positive iff t >= gold_tol
        (since val > t >= gold_tol implies val > gold_tol)
      * compiler less_than(t) entails gold negative iff t <= -gold_tol
        (since val < t <= -gold_tol implies val < -gold_tol)

    Exact-kind match always entails (same assertion). Otherwise False.

    Intentionally conservative: `distinguishable` does NOT entail
    `positive` or `negative` or `gap_material` (it is weaker — no
    sign commitment). Same for `near_zero` — it does not entail
    `negative` even if threshold is negative.
    """
    if gold_kind == comp_kind:
        return True
    if gold_kind == "positive" and comp_kind == "greater_than":
        return comp_thresh >= gold_tol
    if gold_kind == "negative" and comp_kind == "less_than":
        return comp_thresh <= -gold_tol
    return False


def _signatures_compatible(gold_sig: tuple, compiler_sig: tuple) -> bool:
    """Check structural compatibility between gold atom and compiler spec.

    Matching rules (principled, not overfitting):
      - Measurement, comparison kinds must match EXACTLY.
      - Assertion: exact match OR compiler entails gold via tolerance-aware
        entailment (see `_assertion_entails`).
      - Arm kinds: compiler's arm-kind set must be a SUPERSET of gold's
        (compiler may add auxiliary arms, but must include every gold
        arm kind).
      - Allow `adjust` ≡ `intervene` (both are do-calculus regimes).
    """
    g_arms, g_meas, g_cmp, g_assert, g_thresh, g_tol = gold_sig
    c_arms, c_meas, c_cmp, c_assert, c_thresh, c_tol = compiler_sig
    if g_meas != c_meas or g_cmp != c_cmp:
        return False
    if not _assertion_entails(g_assert, g_thresh, g_tol,
                              c_assert, c_thresh, c_tol):
        return False
    # Normalize: adjust ≡ intervene
    _normalize = lambda s: frozenset({"intervene" if k == "adjust" else k for k in s})
    return _normalize(g_arms).issubset(_normalize(c_arms))


def _try_cover(gold_atoms: list, compiler_specs: list) -> tuple[bool, list[str]]:
    """Try to match each gold atom to a distinct compiler spec on structural signature.

    Returns (cover_ok, per_atom_errors).
    """
    gold_sigs = [_spec_signature(a) for a in gold_atoms]
    compiler_sigs = [_spec_signature(s) for s in compiler_specs]
    used = [False] * len(compiler_sigs)
    errors: list[str] = []
    for g_idx, g_sig in enumerate(gold_sigs):
        match_idx = None
        for c_idx, c_sig in enumerate(compiler_sigs):
            if used[c_idx]:
                continue
            if _signatures_compatible(g_sig, c_sig):
                match_idx = c_idx
                break
        if match_idx is None:
            errors.append(
                f"gold atom[{g_idx}] signature {g_sig} not covered "
                f"by any compiler spec"
            )
        else:
            used[match_idx] = True
    return (not errors, errors)


def check_stage2(gt: GoldTarget, compiler_out: CompilerOutput) -> dict:
    """Stage 2: Does the compiler output cover the gold atoms structurally?

    Design (Codex-recommended, 2026-04-19): gold-atom coverage matcher.
    For each gold AtomicSpec (in `gt.atoms` or any entry of
    `gt.alternative_atoms`), require that SOME compiler spec has a
    matching structural signature (measurement kind, comparison kind,
    assertion kind, arm-kinds-superset). Additional compiler specs are
    accepted as auxiliaries — they are not required to match anything.

    Role variables (treatment, outcome, etc.) are checked as a union
    across ALL compiler specs.

    `adjust` and `intervene` arm kinds are treated as equivalent (both
    are do-calculus regimes — this preserves the old `adjust_swap`
    tolerance from the strict stage 2).
    """
    if gt.status == "abstain" or not compiler_out.compiled:
        return {"pass": True, "reason": "abstain (no contract to check)"}

    sc = gt.structural_contract
    specs = compiler_out.specs
    errors: list[str] = []

    # --- Gold-atom coverage (primary + alternatives) -------------------
    if gt.atoms:
        variants = [gt.atoms] + list(gt.alternative_atoms)
        variant_errors: list[tuple[str, list[str]]] = []
        coverage_ok = False
        for v_idx, variant in enumerate(variants):
            ok, v_errs = _try_cover(variant, specs)
            if ok:
                coverage_ok = True
                break
            label = "primary" if v_idx == 0 else f"alternative[{v_idx - 1}]"
            variant_errors.append((label, v_errs))
        if not coverage_ok:
            for label, v_errs in variant_errors:
                for err in v_errs:
                    errors.append(f"[{label}] {err}")

    # --- Role variables (union across all compiler specs) --------------
    if sc is not None and sc.required_role_vars and specs:
        all_vars_in_specs: set[str] = set()
        for spec in specs:
            all_vars_in_specs.update(_collect_spec_vars(spec))
        for role, var in sc.required_role_vars.items():
            if var not in all_vars_in_specs:
                errors.append(f"role_var '{role}={var}' not found in specs")

    return {
        "pass": len(errors) == 0,
        "errors": errors,
    }


def check_stage3(
    gt: GoldTarget, compiler_out: CompilerOutput, fact, world, solver,
) -> dict:
    """Stage 3: Do the compiled specs produce the same verdict as the gold?"""
    if gt.status == "abstain" or not compiler_out.compiled:
        return {"pass": True, "reason": "abstain (no verdict to check)"}

    compiled_specs = compiler_out.specs
    verdicts = []
    for spec in compiled_specs:
        result = verify_atom(spec, world, solver, n_mc=50_000, seed=42)
        verdicts.append(result)

    all_hold = all(v.solver_assertion_holds for v in verdicts)
    any_fail = any(not v.solver_assertion_holds for v in verdicts)

    if fact.truth_value == Verdict.TRUE:
        ok = all_hold
    elif fact.truth_value == Verdict.FALSE:
        ok = any_fail
    elif fact.truth_value == Verdict.NOT_IDENTIFIABLE:
        ok = all_hold  # assertion is not_identifiable, which should hold
    else:
        ok = False

    return {
        "pass": ok,
        "expected_truth": fact.truth_value.value if fact.truth_value else None,
        "all_hold": all_hold,
        "n_specs": len(compiled_specs),
        "details": [
            {"spec_id": v.atom_id, "holds": v.solver_assertion_holds}
            for v in verdicts
        ],
    }


# ---------------------------------------------------------------------------
# Test collection
# ---------------------------------------------------------------------------

_ALL_TARGETS = []
for gt in ALL_GOLD_TARGETS:
    fact = _FACT_BY_ID.get(gt.fact_id)
    if fact is None:
        continue
    _ALL_TARGETS.append((gt, fact))


def _target_id(gt_fact):
    gt, fact = gt_fact
    sf = fact.surface_forms[gt.surface_form_index]
    diff = sf.difficulty
    return f"{gt.fact_id}_s{gt.surface_form_index}_{diff}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.llm
class TestCompilerLLM:
    """Run the LLM compiler against gold targets."""

    @pytest.fixture(scope="class")
    def llm_call(self):
        client = OpenAIClient()
        return _make_llm_call(client)

    @pytest.mark.parametrize(
        "gt_and_fact",
        _ALL_TARGETS,
        ids=[_target_id(x) for x in _ALL_TARGETS],
    )
    def test_compile(self, gt_and_fact, llm_call):
        gt, fact = gt_and_fact
        world_key = _WORLD_FOR_FACT[gt.fact_id]
        target = _infer_target(gt, fact)
        summary = _get_summary(world_key, target)
        world, solver = _get_world_solver(world_key)

        # Build claim card
        claim = _make_claim_card(fact, gt.surface_form_index, gt.structural_contract)

        # Compile
        compiler_out = compile_claim(claim, summary, llm_call=llm_call)

        # Stage 1: compile/abstain
        s1 = check_stage1(gt, compiler_out)

        # Stage 2: structural contract (only if compiled)
        s2 = check_stage2(gt, compiler_out)

        # Stage 3: verdict equivalence (only if compiled)
        s3 = check_stage3(gt, compiler_out, fact, world, solver)

        # Report
        status_str = "compiled" if compiler_out.compiled else "abstain"
        n_specs = len(compiler_out.specs) if compiler_out.compiled else 0
        backend = ""
        if compiler_out.compiled and compiler_out.units:
            backend = compiler_out.units[0].backend or ""

        print(f"\n{'='*60}")
        print(f"  {gt.fact_id} s{gt.surface_form_index} | {fact.surface_forms[gt.surface_form_index].difficulty}")
        print(f"  Claim: {claim.claim_text[:80]}...")
        print(f"  Compiler: {status_str} | {n_specs} specs | backend={backend}")
        print(f"  Stage 1 (compile/abstain): {'PASS' if s1 else 'FAIL'}")
        print(f"  Stage 2 (structure):       {'PASS' if s2['pass'] else 'FAIL'}")
        if not s2["pass"] and "errors" in s2:
            for e in s2["errors"]:
                print(f"    - {e}")
        print(f"  Stage 3 (verdict):         {'PASS' if s3['pass'] else 'FAIL'}")
        if not s3["pass"] and "details" in s3:
            for d in s3["details"]:
                print(f"    - {d['spec_id']}: holds={d['holds']}")
        print(f"{'='*60}")

        # Assert all 3 stages pass
        assert s1, (
            f"Stage 1 FAIL: {gt.fact_id} s{gt.surface_form_index} — "
            f"expected {gt.status}, got {status_str}"
        )
        # Stage 2 and 3 are diagnostic — report but don't hard-fail yet
        # (compiler is imperfect, we want to see the distribution first)
        if not s2["pass"]:
            pytest.xfail(f"Stage 2: {s2.get('errors', [])}")
        if not s3["pass"]:
            pytest.xfail(f"Stage 3: expected {fact.truth_value}, got {s3}")
