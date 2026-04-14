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
    """Build a minimal ClaimCard from a fact + surface form."""
    sf = fact.surface_forms[surface_form_index]

    # Derive focus variables from contract or fact
    focus = []
    if contract and contract.required_role_vars:
        focus = list(set(contract.required_role_vars.values()))
    if not focus:
        focus = ["Y"]  # fallback

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


def check_stage2(gt: GoldTarget, compiler_out: CompilerOutput) -> dict:
    """Stage 2: Does the compiler output satisfy the structural contract?"""
    if gt.status == "abstain" or not compiler_out.compiled:
        return {"pass": True, "reason": "abstain (no contract to check)"}

    sc = gt.structural_contract
    if sc is None:
        return {"pass": True, "reason": "no contract defined"}

    specs = compiler_out.specs
    errors = []

    # n_atoms check
    if isinstance(sc.n_atoms, int):
        if len(specs) != sc.n_atoms:
            errors.append(f"n_atoms: expected {sc.n_atoms}, got {len(specs)}")
    elif isinstance(sc.n_atoms, tuple):
        lo, hi = sc.n_atoms
        if not (lo <= len(specs) <= hi):
            errors.append(f"n_atoms: expected {lo}-{hi}, got {len(specs)}")

    for i, spec in enumerate(specs):
        # Arm kinds
        arm_kinds = {a.kind.value for a in spec.arms}
        if not arm_kinds.issubset(sc.allowed_arm_kinds):
            errors.append(
                f"spec[{i}] arm_kinds: {arm_kinds} not subset of {sc.allowed_arm_kinds}"
            )

        # Measurement kind
        if spec.measurement.kind.value != sc.required_measurement_kind:
            errors.append(
                f"spec[{i}] measurement: {spec.measurement.kind.value} "
                f"!= {sc.required_measurement_kind}"
            )

        # Comparison kind
        if spec.comparison.kind.value != sc.required_comparison_kind:
            errors.append(
                f"spec[{i}] comparison: {spec.comparison.kind.value} "
                f"!= {sc.required_comparison_kind}"
            )

        # Assertion polarity
        if spec.assertion.kind.value != sc.required_assertion_polarity:
            errors.append(
                f"spec[{i}] assertion: {spec.assertion.kind.value} "
                f"!= {sc.required_assertion_polarity}"
            )

    # Role variables (check across all specs)
    if sc.required_role_vars and specs:
        all_vars_in_specs = set()
        for spec in specs:
            for arm in spec.arms:
                all_vars_in_specs.update(arm.values.keys())
                all_vars_in_specs.update(arm.condition_on.keys())
            if spec.measurement.target:
                t = spec.measurement.target
                if isinstance(t, str):
                    all_vars_in_specs.add(t)
                else:
                    all_vars_in_specs.update(t)
            if spec.measurement.lhs:
                all_vars_in_specs.add(spec.measurement.lhs)
            if spec.measurement.rhs:
                all_vars_in_specs.add(spec.measurement.rhs)
            if spec.measurement.treatment:
                all_vars_in_specs.add(spec.measurement.treatment)
            if spec.measurement.outcome:
                all_vars_in_specs.add(spec.measurement.outcome)

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
