"""Suite 2 — Gold target sanity check: do our gold specs produce correct verdicts?

For every GoldTarget with status="compile", runs each AtomicSpec through the
verifier against the corresponding SCMWorld. Checks:
  - TRUE facts: all atoms hold (solver_assertion_holds=True)
  - FALSE facts: at least one atom fails (assertion doesn't hold)
  - NOT_IDENTIFIABLE facts: atom holds (assertion IS not_identifiable → True)

This does NOT test the compiler. It tests that our hand-written gold specs
are correct — a prerequisite for using them to evaluate the compiler.
"""

from __future__ import annotations

import pytest

from sreg.solver.scm_solver import SCMSolver
from sreg.tools.oi_verifier import verify_atom

from tests.eval.suite2_translation.fact_tables import ALL_FACTS, Verdict
from tests.eval.suite2_translation.gold_targets import ALL_GOLD_TARGETS
from tests.eval.suite2_translation.worlds import ALL_WORLDS

# ---------------------------------------------------------------------------
# Build lookup tables
# ---------------------------------------------------------------------------

_FACT_BY_ID = {f.fact_id: f for f in ALL_FACTS}

_WORLD_FOR_FACT = {f.fact_id: f.world for f in ALL_FACTS}

# Map world key -> (SCMWorld, SCMSolver), lazily cached
_SOLVER_CACHE: dict[str, tuple] = {}


def _get_world_and_solver(world_key: str):
    if world_key not in _SOLVER_CACHE:
        world = ALL_WORLDS[world_key]
        solver = SCMSolver(world, n_mc=50_000)
        _SOLVER_CACHE[world_key] = (world, solver)
    return _SOLVER_CACHE[world_key]


# ---------------------------------------------------------------------------
# Collect compileable gold targets with expected verdicts
# ---------------------------------------------------------------------------

_COMPILE_TARGETS = []
for gt in ALL_GOLD_TARGETS:
    if gt.status != "compile":
        continue
    fact = _FACT_BY_ID.get(gt.fact_id)
    if fact is None:
        continue
    _COMPILE_TARGETS.append((gt, fact))


def _target_id(gt_and_fact):
    gt, fact = gt_and_fact
    return f"{gt.fact_id}_s{gt.surface_form_index}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGoldVerdictSanity:
    """Every gold spec must produce the expected verdict against the SCM."""

    @pytest.mark.parametrize(
        "gt_and_fact",
        _COMPILE_TARGETS,
        ids=[_target_id(x) for x in _COMPILE_TARGETS],
    )
    def test_gold_verdict(self, gt_and_fact):
        gt, fact = gt_and_fact
        world_key = _WORLD_FOR_FACT[gt.fact_id]
        world, solver = _get_world_and_solver(world_key)

        verdicts = []
        for atom in gt.atoms:
            result = verify_atom(atom, world, solver, n_mc=50_000, seed=42)
            verdicts.append(result)

        # TODO: This logic assumes all_of acceptance rule. When any_of or
        # alternative_atoms are used, adapt: TRUE+any_of means at least one
        # holds; FALSE+any_of means all fail. See GoldTarget.acceptance_rule.
        if fact.truth_value == Verdict.TRUE:
            # All atoms must hold (under all_of)
            for v in verdicts:
                assert v.solver_assertion_holds, (
                    f"{gt.fact_id} s{gt.surface_form_index} "
                    f"atom {v.atom_id}: expected TRUE but got FALSE. "
                    f"Detail: {v.detail}"
                )

        elif fact.truth_value == Verdict.FALSE:
            # At least one atom must fail (the claim is wrong)
            any_fails = any(not v.solver_assertion_holds for v in verdicts)
            assert any_fails, (
                f"{gt.fact_id} s{gt.surface_form_index}: "
                f"expected FALSE verdict but all atoms held. "
                f"Details: {[v.detail for v in verdicts]}"
            )

        elif fact.truth_value == Verdict.NOT_IDENTIFIABLE:
            # The identifiability check itself should hold
            # (the assertion IS "not_identifiable", and it should be true)
            for v in verdicts:
                assert v.solver_assertion_holds, (
                    f"{gt.fact_id} s{gt.surface_form_index} "
                    f"atom {v.atom_id}: expected NOT_IDENTIFIABLE to hold "
                    f"but it didn't. Detail: {v.detail}"
                )


class TestAbstentionTargetsHaveNoAtoms:
    """Abstention targets must have zero atoms (nothing to verify)."""

    @pytest.mark.parametrize(
        "gt",
        [g for g in ALL_GOLD_TARGETS if g.status == "abstain"],
        ids=[f"{g.fact_id}_s{g.surface_form_index}" for g in ALL_GOLD_TARGETS
             if g.status == "abstain"],
    )
    def test_no_atoms(self, gt):
        assert len(gt.atoms) == 0, (
            f"Abstention target {gt.fact_id} s{gt.surface_form_index} "
            f"should have 0 atoms but has {len(gt.atoms)}"
        )
        assert gt.abstain_reason_code is not None, (
            f"Abstention target {gt.fact_id} s{gt.surface_form_index} "
            f"should have an abstain_reason_code"
        )
