"""Suite 1 Core Correctness — Parametrized test runner.

Runs every EvalCase from the registry against the verifier and checks
that the verdict matches the expected outcome. Generates a coverage
report at results/suite1_coverage.json.

Target: 100% accuracy. Any failure is a bug, not noise.
Only Monte Carlo tolerance (+-0.01 at N=50K) is acceptable.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from sreg.models.open_investigation import (
    AssertionKind,
    AtomicSpec,
    ComparisonKind,
    MeasurementKind,
    QueryKind,
)
from sreg.solver.scm_solver import SCMSolver
from sreg.tools.oi_verifier import verify_atom

from .registry import REGISTRY, EvalCase
from .worlds import ALL_WORLDS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

N_MC = 50_000
SEED = 42

# All active enum values (PROB and DISTRIBUTION are skipped)
ALL_QUERY_KINDS = {k.value for k in QueryKind}
ALL_MEASUREMENT_KINDS = {k.value for k in MeasurementKind} - {"prob", "distribution"}
ALL_COMPARISON_KINDS = {k.value for k in ComparisonKind}
ALL_ASSERTION_KINDS = {k.value for k in AssertionKind}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def solvers() -> dict[str, SCMSolver]:
    """Pre-build solvers for all worlds (shared across tests in module)."""
    return {name: SCMSolver(world) for name, world in ALL_WORLDS.items()}


# ---------------------------------------------------------------------------
# Parametrized verifier tests
# ---------------------------------------------------------------------------


@pytest.fixture(params=REGISTRY, ids=[c.case_id for c in REGISTRY])
def eval_case(request: pytest.FixtureRequest) -> EvalCase:
    return request.param


def test_verify_atom(eval_case: EvalCase, solvers: dict[str, SCMSolver]) -> None:
    """Run a single eval case and verify the verdict."""
    world = ALL_WORLDS[eval_case.world_name]
    solver = solvers[eval_case.world_name]

    verdict = verify_atom(
        eval_case.spec, world, solver, n_mc=N_MC, seed=SEED
    )

    # Primary assertion: does the verdict match expectations?
    assert verdict.solver_assertion_holds is eval_case.expected_holds, (
        f"Case {eval_case.case_id}: expected holds={eval_case.expected_holds}, "
        f"got holds={verdict.solver_assertion_holds}. "
        f"ground_truth={verdict.ground_truth}, score={verdict.score}. "
        f"Description: {eval_case.description}"
    )

    # Score consistency: holds=True -> score=1.0, holds=False -> score=0.0
    if eval_case.expected_holds:
        assert verdict.score == 1.0, (
            f"Case {eval_case.case_id}: holds=True but score={verdict.score}"
        )
    else:
        assert verdict.score == 0.0, (
            f"Case {eval_case.case_id}: holds=False but score={verdict.score}"
        )

    # Optional: check approximate ground truth value
    if eval_case.expected_value is not None and eval_case.expected_holds:
        gt = verdict.ground_truth
        if isinstance(gt, (int, float)):
            assert abs(gt - eval_case.expected_value) <= eval_case.mc_tolerance, (
                f"Case {eval_case.case_id}: ground_truth={gt}, "
                f"expected ~{eval_case.expected_value} "
                f"(tolerance={eval_case.mc_tolerance})"
            )


# ---------------------------------------------------------------------------
# Validation rejection tests
# ---------------------------------------------------------------------------


class TestValidationRejections:
    """Verify that structurally invalid specs are rejected at construction."""

    def test_adjust_correlation_rejected(self):
        """ADJUST + CORRELATION is structurally incoherent (P06 fix)."""
        with pytest.raises(ValueError, match="ADJUST"):
            AtomicSpec(
                spec_id="bad_adjust_corr",
                arms=(
                    QueryArm(
                        label="adj",
                        kind=QueryKind.ADJUST,
                        treatment="A",
                        outcome="Y",
                        values={"A": 1.0},
                    ),
                ),
                measurement=Measurement(
                    kind=MeasurementKind.CORRELATION, lhs="A", rhs="Y"
                ),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            )

    def test_adjust_partial_correlation_rejected(self):
        """ADJUST + PARTIAL_CORRELATION is structurally incoherent."""
        with pytest.raises(ValueError, match="ADJUST"):
            AtomicSpec(
                spec_id="bad_adjust_pcorr",
                arms=(
                    QueryArm(
                        label="adj",
                        kind=QueryKind.ADJUST,
                        treatment="A",
                        outcome="Y",
                        values={"A": 1.0},
                    ),
                ),
                measurement=Measurement(
                    kind=MeasurementKind.PARTIAL_CORRELATION,
                    lhs="A",
                    rhs="Y",
                    cond_set=("Z",),
                ),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            )

    def test_difference_requires_two_arms(self):
        """DIFFERENCE comparison requires exactly 2 arms."""
        with pytest.raises(ValueError, match="2 arms"):
            AtomicSpec(
                spec_id="bad_diff_3arms",
                arms=(
                    QueryArm(
                        label="a", kind=QueryKind.INTERVENE, values={"X": 1.0}
                    ),
                    QueryArm(
                        label="b", kind=QueryKind.INTERVENE, values={"X": 0.0}
                    ),
                    QueryArm(
                        label="c", kind=QueryKind.INTERVENE, values={"X": -1.0}
                    ),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(
                    kind=ComparisonKind.DIFFERENCE, ref_arm="c"
                ),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            )

    def test_quantile_requires_q(self):
        """QUANTILE measurement requires q parameter."""
        with pytest.raises(ValueError, match="quantile.*requires q"):
            Measurement(kind=MeasurementKind.QUANTILE, target="Y")

    def test_tail_prob_requires_threshold(self):
        """TAIL_PROB measurement requires threshold."""
        with pytest.raises(ValueError, match="tail_prob.*requires threshold"):
            Measurement(kind=MeasurementKind.TAIL_PROB, target="Y")


# Need these imports for validation tests
from sreg.models.open_investigation import (
    Assertion,
    Comparison,
    Measurement,
    QueryArm,
)


# ---------------------------------------------------------------------------
# Rescore determinism test
# ---------------------------------------------------------------------------


class TestRescoreDeterminism:
    """Same inputs to verify_atom must produce identical outputs."""

    def test_double_run_same_result(self, solvers: dict[str, SCMSolver]):
        """Run the same spec twice with same seed -> identical verdict."""
        case = REGISTRY[0]  # lc_ate_positive
        world = ALL_WORLDS[case.world_name]
        solver = solvers[case.world_name]

        v1 = verify_atom(case.spec, world, solver, n_mc=N_MC, seed=SEED)
        v2 = verify_atom(case.spec, world, solver, n_mc=N_MC, seed=SEED)

        assert v1.solver_assertion_holds == v2.solver_assertion_holds
        assert v1.score == v2.score
        assert v1.ground_truth == v2.ground_truth, (
            f"Rescore delta != 0: run1={v1.ground_truth}, run2={v2.ground_truth}"
        )


# ---------------------------------------------------------------------------
# Coverage report generation (runs after all tests)
# ---------------------------------------------------------------------------


def _compute_coverage_from_registry() -> dict:
    """Compute enum coverage from the registry tags."""
    query_coverage: dict[str, int] = defaultdict(int)
    measurement_coverage: dict[str, int] = defaultdict(int)
    comparison_coverage: dict[str, int] = defaultdict(int)
    assertion_coverage: dict[str, int] = defaultdict(int)

    for case in REGISTRY:
        for tag in case.tags:
            tag_upper = tag.upper()
            if tag_upper in {k.value.upper() for k in QueryKind}:
                query_coverage[tag_upper] += 1
            elif tag_upper in {k.value.upper() for k in MeasurementKind}:
                measurement_coverage[tag_upper] += 1
            elif tag_upper in {k.value.upper() for k in ComparisonKind}:
                comparison_coverage[tag_upper] += 1
            elif tag_upper in {k.value.upper() for k in AssertionKind}:
                assertion_coverage[tag_upper] += 1

    return {
        "QueryKind": dict(query_coverage),
        "MeasurementKind": dict(measurement_coverage),
        "ComparisonKind": dict(comparison_coverage),
        "AssertionKind": dict(assertion_coverage),
    }


class TestCoverageReport:
    """Verify that the registry achieves 100% enum coverage."""

    def test_all_query_kinds_covered(self):
        coverage = _compute_coverage_from_registry()
        covered = set(coverage["QueryKind"].keys())
        expected = {k.value.upper() for k in QueryKind}
        missing = expected - covered
        assert not missing, f"QueryKind not covered: {missing}"

    def test_all_measurement_kinds_covered(self):
        coverage = _compute_coverage_from_registry()
        covered = set(coverage["MeasurementKind"].keys())
        expected = ALL_MEASUREMENT_KINDS
        # Compare uppercase
        missing = {e.upper() for e in expected} - {c.upper() for c in covered}
        assert not missing, f"MeasurementKind not covered: {missing}"

    def test_all_comparison_kinds_covered(self):
        coverage = _compute_coverage_from_registry()
        covered = set(coverage["ComparisonKind"].keys())
        expected = {k.value.upper() for k in ComparisonKind}
        missing = expected - covered
        assert not missing, f"ComparisonKind not covered: {missing}"

    def test_all_assertion_kinds_covered(self):
        coverage = _compute_coverage_from_registry()
        covered = set(coverage["AssertionKind"].keys())
        expected = {k.value.upper() for k in AssertionKind}
        missing = expected - covered
        assert not missing, f"AssertionKind not covered: {missing}"
