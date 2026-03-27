"""Tests for Open Investigation Verifier: execute AtomicSpecs against SCMWorld."""

from __future__ import annotations

from sreg.models.open_investigation import (
    Assertion,
    AssertionKind,
    AtomicSpec,
    Comparison,
    ComparisonKind,
    FamilyAtom,
    FamilyKey,
    Measurement,
    MeasurementKind,
    QueryArm,
    QueryKind,
    SalienceFamily,
)
from sreg.solver.scm_solver import SCMSolver
from sreg.tools.oi_verifier import (
    score_claim_against_family,
    score_episode,
    verify_atom,
)
from sreg.world.scm import SCMWorld

# ---------------------------------------------------------------------------
# Test worlds
# ---------------------------------------------------------------------------


def _simple_world() -> SCMWorld:
    """A -> Y with positive effect. Simple and predictable."""
    return SCMWorld(
        id="test-simple",
        graph={"A": [], "Y": ["A"]},
        equations={
            "A": lambda p, rng: rng.normal(0, 1),
            "Y": lambda p, rng: 0.8 * p["A"] + rng.normal(0, 0.5),
        },
    )


def _confounder_world() -> SCMWorld:
    """C -> A -> Y, C -> Y. C confounds A->Y."""
    return SCMWorld(
        id="test-conf",
        graph={"C": [], "A": ["C"], "Y": ["A", "C"]},
        equations={
            "C": lambda p, rng: rng.normal(0, 1),
            "A": lambda p, rng: p["C"] + rng.normal(0, 1),
            "Y": lambda p, rng: 0.5 * p["A"] + 0.3 * p["C"] + rng.normal(0, 0.5),
        },
    )


def _threshold_world() -> SCMWorld:
    """A -> Y with threshold: Y = 0 if A < 0.5 else 2*A + noise."""
    return SCMWorld(
        id="test-threshold",
        graph={"A": [], "Y": ["A"]},
        equations={
            "A": lambda p, rng: rng.uniform(0, 1),
            "Y": lambda p, rng: (
                2.0 * p["A"] + rng.normal(0, 0.1) if p["A"] > 0.5 else rng.normal(0, 0.1)
            ),
        },
    )


# ---------------------------------------------------------------------------
# verify_atom tests
# ---------------------------------------------------------------------------


class TestVerifyAtom:
    def test_positive_effect_detected(self):
        """A -> Y with positive effect should verify as positive."""
        world = _simple_world()
        solver = SCMSolver(world)
        spec = AtomicSpec(
            spec_id="ate_pos",
            arms=(
                QueryArm(label="hi", kind=QueryKind.INTERVENE, values={"A": 1.0}),
                QueryArm(label="lo", kind=QueryKind.INTERVENE, values={"A": -1.0}),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
            comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
            assertion=Assertion(kind=AssertionKind.POSITIVE),
        )
        verdict = verify_atom(spec, world, solver, n_mc=20_000, seed=42)
        assert verdict.solver_assertion_holds is True
        assert verdict.score == 1.0
        assert isinstance(verdict.ground_truth, float)
        assert verdict.ground_truth > 0  # positive effect

    def test_near_zero_when_no_effect(self):
        """Two independent variables: effect should be near zero."""
        world = SCMWorld(
            id="test-indep",
            graph={"A": [], "Y": []},
            equations={
                "A": lambda p, rng: rng.normal(0, 1),
                "Y": lambda p, rng: rng.normal(0, 1),
            },
        )
        solver = SCMSolver(world)
        spec = AtomicSpec(
            spec_id="no_effect",
            arms=(
                QueryArm(label="hi", kind=QueryKind.INTERVENE, values={"A": 1.0}),
                QueryArm(label="lo", kind=QueryKind.INTERVENE, values={"A": -1.0}),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
            comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
            assertion=Assertion(kind=AssertionKind.NEAR_ZERO, tolerance=0.15),
        )
        verdict = verify_atom(spec, world, solver, n_mc=20_000, seed=42)
        assert verdict.solver_assertion_holds is True

    def test_observational_conditioning(self):
        """Observational conditioning: P(Y | A=high) vs P(Y | A=low)."""
        world = _simple_world()
        solver = SCMSolver(world)
        spec = AtomicSpec(
            spec_id="obs_cond",
            arms=(
                QueryArm(label="hi", kind=QueryKind.OBSERVE, values={"A": 1.0}),
                QueryArm(label="lo", kind=QueryKind.OBSERVE, values={"A": -1.0}),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
            comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
            assertion=Assertion(kind=AssertionKind.POSITIVE),
        )
        verdict = verify_atom(spec, world, solver, n_mc=50_000, seed=42)
        assert verdict.solver_assertion_holds is True

    def test_variance_measurement(self):
        """Verify variance measurement works."""
        world = _simple_world()
        solver = SCMSolver(world)
        spec = AtomicSpec(
            spec_id="var1",
            arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
            measurement=Measurement(kind=MeasurementKind.VARIANCE, target="Y"),
            comparison=Comparison(kind=ComparisonKind.IDENTITY),
            assertion=Assertion(kind=AssertionKind.POSITIVE),
        )
        verdict = verify_atom(spec, world, solver, n_mc=20_000, seed=42)
        assert verdict.solver_assertion_holds is True
        assert verdict.ground_truth > 0

    def test_tail_probability(self):
        """Verify tail probability measurement."""
        world = _simple_world()
        solver = SCMSolver(world)
        spec = AtomicSpec(
            spec_id="tail1",
            arms=(
                QueryArm(label="hi", kind=QueryKind.INTERVENE, values={"A": 2.0}),
                QueryArm(label="lo", kind=QueryKind.INTERVENE, values={"A": -2.0}),
            ),
            measurement=Measurement(
                kind=MeasurementKind.TAIL_PROB, target="Y", threshold=1.0
            ),
            comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
            assertion=Assertion(kind=AssertionKind.POSITIVE),
        )
        verdict = verify_atom(spec, world, solver, n_mc=20_000, seed=42)
        assert verdict.solver_assertion_holds is True

    def test_partial_correlation(self):
        """Verify partial correlation measurement."""
        world = _confounder_world()
        solver = SCMSolver(world)
        spec = AtomicSpec(
            spec_id="pcor1",
            arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
            measurement=Measurement(
                kind=MeasurementKind.PARTIAL_CORRELATION,
                lhs="A",
                rhs="Y",
                cond_set=("C",),
            ),
            comparison=Comparison(kind=ComparisonKind.IDENTITY),
            assertion=Assertion(kind=AssertionKind.POSITIVE),
        )
        verdict = verify_atom(spec, world, solver, n_mc=50_000, seed=42)
        assert verdict.solver_assertion_holds is True

    def test_sweep_changepoint(self):
        """Verify sweep + changepoint detection."""
        world = _threshold_world()
        solver = SCMSolver(world)
        spec = AtomicSpec(
            spec_id="cp1",
            arms=(
                QueryArm(
                    label="sweep",
                    kind=QueryKind.SWEEP,
                    sweep_var="A",
                    sweep_values=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9),
                    sweep_base=QueryKind.INTERVENE,
                ),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
            comparison=Comparison(kind=ComparisonKind.PIECEWISE_FIT),
            assertion=Assertion(kind=AssertionKind.CHANGEPOINT_EXISTS),
        )
        verdict = verify_atom(spec, world, solver, n_mc=10_000, seed=42)
        assert verdict.solver_assertion_holds is True


# ---------------------------------------------------------------------------
# Scoring tests
# ---------------------------------------------------------------------------


class TestScoring:
    def _make_family(self, n_atoms: int = 2, n_material: int = 2) -> SalienceFamily:
        specs = []
        for i in range(n_atoms):
            specs.append(
                FamilyAtom(
                    atom_id=f"a{i}",
                    spec=AtomicSpec(
                        spec_id=f"s{i}",
                        arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
                        measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                        comparison=Comparison(kind=ComparisonKind.IDENTITY),
                        assertion=Assertion(kind=AssertionKind.POSITIVE),
                    ),
                    weight=1.0,
                    material=i < n_material,
                )
            )
        return SalienceFamily(
            family_id="f1",
            key=FamilyKey(
                brief_target="Y",
                focus_signature=("X", "Y"),
                pattern_class="causal_effect",
            ),
            atoms=tuple(specs),
            salience=0.8,
        )

    def test_fully_true(self):
        """All atoms correct, all material covered."""
        family = self._make_family(n_atoms=2, n_material=2)
        scores = {"a0": 1.0, "a1": 1.0}
        score, verdict = score_claim_against_family(scores, family)
        assert verdict == "fully_true"
        assert score == 1.0

    def test_partially_true_with_omission(self):
        """One atom correct, one material atom omitted."""
        family = self._make_family(n_atoms=2, n_material=2)
        scores = {"a0": 1.0}  # a1 omitted but material
        score, verdict = score_claim_against_family(scores, family)
        assert verdict == "partially_true_with_omission"
        assert 0.0 < score < 1.0

    def test_false_claim(self):
        """All atoms wrong."""
        family = self._make_family(n_atoms=2, n_material=2)
        scores = {"a0": 0.0, "a1": 0.0}
        score, verdict = score_claim_against_family(scores, family)
        assert verdict == "false"
        assert score == 0.0

    def test_unmatched(self):
        """No atoms match."""
        family = self._make_family(n_atoms=2, n_material=2)
        scores = {"a99": 1.0}  # doesn't exist in family
        score, verdict = score_claim_against_family(scores, family)
        assert verdict == "unmatched"
        assert score == 0.0

    def test_specificity_bonus(self):
        """More atoms covered → higher score."""
        family = self._make_family(n_atoms=3, n_material=1)
        score_1, _ = score_claim_against_family({"a0": 1.0}, family)
        score_2, _ = score_claim_against_family({"a0": 1.0, "a1": 1.0}, family)
        score_3, _ = score_claim_against_family({"a0": 1.0, "a1": 1.0, "a2": 1.0}, family)
        assert score_1 < score_2 < score_3

    def test_episode_scoring(self):
        """Episode-level scoring with precision gate."""
        families = [self._make_family()]
        # Good solver: 1 claim matching family with high score
        ep = score_episode([("f1", 0.9)], families, n_claims=1)
        assert ep.correctness == 0.9
        assert ep.coverage > 0  # family hit
        assert ep.total > 0

    def test_precision_gate(self):
        """Low precision should zero out coverage."""
        families = [self._make_family()]
        ep = score_episode([("f1", 0.3)], families, n_claims=1)
        assert ep.correctness == 0.3
        assert ep.precision_gate_active is True
        assert ep.coverage == 0.0

    def test_efficiency_penalty(self):
        """Submitting over budget reduces efficiency."""
        families = [self._make_family()]
        ep = score_episode([("f1", 0.9)], families, n_claims=7, claim_budget=5)
        assert ep.efficiency < 1.0
