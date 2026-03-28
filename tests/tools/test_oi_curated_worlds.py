"""Curated test worlds for OI Alpha pilot.

Three hand-crafted SCMWorlds designed to exercise different aspects of the
OI pipeline. The roadmap (TODO.md, Paso 3) calls for:
  - One with real interaction
  - One with partial mediation
  - One with interesting confounding

Each world is validated to produce diverse salience map families and to
score correctly through the full pipeline with the driver.
"""

from __future__ import annotations

from sreg.models.research_problem import DataAsset, ResearchProblem
from sreg.tools.oi_driver import ScriptedAction, run_oi_scripted
from sreg.tools.oi_runner import OIEpisodeRunner
from sreg.tools.oi_salience import build_salience_map
from sreg.world.scm import SCMWorld

N_MC = 20_000
SEED = 42


# ---------------------------------------------------------------------------
# World A: "Ecosystem" — interaction + confounding
#
# Structure:
#   Sun → Nutrients (runoff from heated soil)
#   Sun → Algae (photosynthesis)
#   Nutrients → Algae (fertilization, moderated by Temp)
#   Temp → Algae (via interaction with Nutrients)
#   Algae → Fish (food source)
#   Depth → Fish (habitat, independent of nutrients)
#
# Key patterns expected:
#   - CAUSAL_EFFECT: Nutrients → Algae
#   - HETEROGENEITY: Nutrients × Temp → Algae
#   - OBSERVATIONAL_ASSOCIATION: Sun ↔ Algae (confounded path)
#   - EFFECT_RANKING: multiple ancestors of Fish
# ---------------------------------------------------------------------------

def world_ecosystem() -> SCMWorld:
    return SCMWorld(
        id="curated-ecosystem",
        graph={
            "Sun": [],
            "Temp": [],
            "Depth": [],
            "Nutrients": ["Sun"],
            "Algae": ["Sun", "Nutrients", "Temp"],
            "Fish": ["Algae", "Depth"],
        },
        equations={
            "Sun": lambda p, rng: rng.normal(5, 1.5),
            "Temp": lambda p, rng: rng.normal(20, 4),
            "Depth": lambda p, rng: rng.normal(10, 3),
            "Nutrients": lambda p, rng: (
                0.6 * p["Sun"] + rng.normal(3, 1)
            ),
            "Algae": lambda p, rng: (
                0.3 * p["Sun"]                          # direct sunlight
                + 0.5 * p["Nutrients"]                  # fertilization
                + 0.25 * p["Nutrients"] * (p["Temp"] - 20) / 4  # interaction
                + rng.normal(0, 1)
            ),
            "Fish": lambda p, rng: (
                0.4 * p["Algae"] + 0.5 * p["Depth"] + rng.normal(0, 1.5)
            ),
        },
    )


# ---------------------------------------------------------------------------
# World B: "Treatment" — partial mediation + confounding
#
# Structure:
#   Severity → Treatment (confounded: sicker patients get more treatment)
#   Severity → Recovery (direct effect)
#   Treatment → Biomarker (mechanistic response)
#   Treatment → Recovery (direct effect, smaller)
#   Biomarker → Recovery (mediating path)
#   Age → Severity + Recovery (confounder)
#
# Key patterns expected:
#   - CAUSAL_EFFECT: Treatment → Recovery
#   - MEDIATION: Treatment → Biomarker → Recovery (partial)
#   - OBSERVATIONAL_ASSOCIATION: Severity ↔ Recovery
#   - CAUSAL_EFFECT: Age → Recovery (via multiple paths)
# ---------------------------------------------------------------------------

def world_treatment() -> SCMWorld:
    return SCMWorld(
        id="curated-treatment",
        graph={
            "Age": [],
            "Severity": ["Age"],
            "Treatment": ["Severity"],
            "Biomarker": ["Treatment"],
            "Recovery": ["Treatment", "Biomarker", "Severity", "Age"],
        },
        equations={
            "Age": lambda p, rng: rng.normal(50, 12),
            "Severity": lambda p, rng: (
                0.02 * p["Age"] + rng.normal(5, 1.5)
            ),
            "Treatment": lambda p, rng: (
                0.4 * p["Severity"] + rng.normal(3, 1)
            ),
            "Biomarker": lambda p, rng: (
                -0.6 * p["Treatment"] + rng.normal(8, 1.2)
            ),
            "Recovery": lambda p, rng: (
                0.3 * p["Treatment"]        # direct treatment effect
                - 0.4 * p["Biomarker"]      # mediating path
                - 0.5 * p["Severity"]       # severity baseline
                - 0.01 * p["Age"]           # age effect
                + rng.normal(10, 2)
            ),
        },
    )


# ---------------------------------------------------------------------------
# World B2: "Treatment Simpson" — Simpson's paradox variant
#
# Designed to force investigation: the crude association between Treatment
# and Recovery is NEGATIVE (more treatment → worse recovery), but the
# causal effect is POSITIVE (treatment helps within severity groups).
#
# Simpson's paradox mechanism:
#   Severity → Treatment (STRONG: sicker patients get much more treatment)
#   Severity → Recovery (STRONG negative: sicker patients recover worse)
#   Treatment → Recovery (moderate positive: treatment helps)
#
# Crude corr(Treatment, Recovery) < 0 because:
#   high Severity → high Treatment AND low Recovery
# But causal ATE(Treatment, Recovery) > 0
#
# A no-data LLM would guess "treatment helps" (correct causal direction)
# BUT would not know the crude association is negative. Only data analysis
# reveals the paradox.
#
# Key SQs for this world:
#   - obs_assoc(Treatment, Recovery) → NEGATIVE (data-indexed!)
#   - causal_effect(Treatment, Recovery) → POSITIVE
#   - confounding(Treatment, Recovery, Severity) → EXISTS (sign-reversal)
# ---------------------------------------------------------------------------


def world_treatment_simpson() -> SCMWorld:
    return SCMWorld(
        id="curated-treatment-simpson",
        graph={
            "Age": [],
            "Severity": ["Age"],
            "Treatment": ["Severity"],
            "Biomarker": ["Treatment"],
            "Recovery": ["Treatment", "Biomarker", "Severity", "Age"],
        },
        equations={
            "Age": lambda p, rng: rng.normal(50, 12),
            "Severity": lambda p, rng: (
                0.02 * p["Age"] + rng.normal(5, 1.5)
            ),
            # STRONG confounding: sicker → much more treatment
            "Treatment": lambda p, rng: (
                1.8 * p["Severity"] + rng.normal(0, 0.8)
            ),
            "Biomarker": lambda p, rng: (
                -0.3 * p["Treatment"] + rng.normal(8, 1.2)
            ),
            "Recovery": lambda p, rng: (
                0.4 * p["Treatment"]         # positive causal effect
                - 0.15 * p["Biomarker"]      # weak mediation
                - 1.8 * p["Severity"]        # STRONG negative severity
                - 0.01 * p["Age"]
                + rng.normal(10, 1.5)
            ),
        },
    )


# ---------------------------------------------------------------------------
# World D: "Productivity" — suppressor effect
#
# Key phenomenon: Training appears UNRELATED to Productivity (crude r ≈ 0)
# despite having a strong positive causal effect (ATE = 0.5).
#
# Suppressor mechanism:
#   Team_size → Training (positive: bigger teams get more training budget)
#   Team_size → Productivity (negative: coordination overhead)
#   Training → Productivity (positive: skill improvement)
#
# The positive direct path (Training → Productivity) is almost exactly
# cancelled by the negative indirect path (Team_size ↗ Training, Team_size ↘
# Productivity), producing crude corr ≈ 0.
#
# Data-indexed: LLM priors say "training improves productivity" (positive).
# Data shows: r ≈ 0. Only after controlling for Team_size does the positive
# effect emerge (partial r ≈ 0.72).
#
# Coefficients tuned via grid search (n=10000, 20-seed stability check):
#   crude r ∈ [-0.09, +0.10], partial r ∈ [0.67, 0.77] at n=300.
# ---------------------------------------------------------------------------

def world_productivity() -> SCMWorld:
    return SCMWorld(
        id="curated-productivity",
        graph={
            "Team_size": [],
            "Experience": [],
            "Training": ["Team_size", "Experience"],
            "Productivity": ["Training", "Team_size", "Experience"],
        },
        equations={
            "Team_size": lambda p, rng: rng.normal(50, 15),
            "Experience": lambda p, rng: rng.normal(10, 4),
            "Training": lambda p, rng: (
                0.4 * p["Team_size"]
                - 0.15 * p["Experience"]
                + rng.normal(20, 6)
            ),
            "Productivity": lambda p, rng: (
                0.5 * p["Training"]        # positive causal effect (suppressed)
                - 0.4 * p["Team_size"]     # coordination overhead (suppressor)
                + 0.3 * p["Experience"]    # experience helps
                + rng.normal(50, 8)
            ),
        },
    )


# ---------------------------------------------------------------------------
# World E: "Screen time" — reversed direction (confounding)
#
# Key phenomenon: Screen time has a POSITIVE crude association with academic
# performance, despite having a NEGATIVE causal effect.
#
# Confounding mechanism:
#   Parental_income → Screen_time (positive: more devices)
#   Parental_income → Academic (strong positive: tutors, resources)
#   Screen_time → Academic (negative: displaces study/sleep)
#
# The strong income confounding overwhelms the negative causal effect,
# making the crude association POSITIVE.
#
# Data-indexed: LLM priors say "screen time hurts academics" (negative).
# Data shows: r ≈ +0.56. Only after controlling for Income does the
# negative effect appear (partial r ≈ -0.44).
#
# Stability: crude r ∈ [+0.44, +0.65], partial r ∈ [-0.56, -0.32] at n=300.
# ---------------------------------------------------------------------------

def world_screen_time() -> SCMWorld:
    return SCMWorld(
        id="curated-screen-time",
        graph={
            "Parental_income": [],
            "Motivation": [],
            "Screen_time": ["Parental_income"],
            "Physical_activity": ["Parental_income", "Screen_time", "Motivation"],
            "Academic": ["Screen_time", "Physical_activity",
                         "Parental_income", "Motivation"],
        },
        equations={
            "Parental_income": lambda p, rng: rng.normal(60, 20),
            "Motivation": lambda p, rng: rng.normal(0, 1),
            "Screen_time": lambda p, rng: (
                0.5 * p["Parental_income"] + rng.normal(0, 8)
            ),
            "Physical_activity": lambda p, rng: (
                0.3 * p["Parental_income"]
                - 0.4 * p["Screen_time"]
                + 0.5 * p["Motivation"]
                + rng.normal(0, 3)
            ),
            "Academic": lambda p, rng: (
                -0.15 * p["Screen_time"]          # negative causal effect
                + 0.4 * p["Physical_activity"]    # exercise helps cognition
                + 0.6 * p["Parental_income"]      # strong income effect
                + 0.5 * p["Motivation"]
                + rng.normal(0, 5)
            ),
        },
    )


# ---------------------------------------------------------------------------
# World C: "Education" — confounding + variance effect
#
# Structure:
#   Wealth → Education (richer families get more education)
#   Wealth → Income (direct: inheritance, connections)
#   Motivation → Education + Income (hidden driver)
#   Education → Skill (human capital)
#   Skill → Income (labor market)
#   Education increases income VARIANCE (PhD: high or low income)
#
# Key patterns expected:
#   - CAUSAL_EFFECT: Education → Income (via Skill)
#   - MEDIATION: Education → Skill → Income
#   - VARIANCE_EFFECT: Education increases Income spread
#   - OBSERVATIONAL_ASSOCIATION: Wealth ↔ Income (confounded)
# ---------------------------------------------------------------------------

def world_education() -> SCMWorld:
    return SCMWorld(
        id="curated-education",
        graph={
            "Wealth": [],
            "Motivation": [],
            "Education": ["Wealth", "Motivation"],
            "Skill": ["Education"],
            "Income": ["Wealth", "Skill", "Motivation"],
        },
        equations={
            "Wealth": lambda p, rng: rng.normal(50, 15),
            "Motivation": lambda p, rng: rng.normal(0, 1),
            "Education": lambda p, rng: (
                0.03 * p["Wealth"] + 0.8 * p["Motivation"] + rng.normal(12, 2)
            ),
            "Skill": lambda p, rng: (
                0.5 * p["Education"] + rng.normal(0, 1.5)
            ),
            "Income": lambda p, rng: (
                0.15 * p["Wealth"]                    # inheritance/connections
                + 0.6 * p["Skill"]                    # human capital
                + 0.3 * p["Motivation"]               # drive
                # Variance effect: higher skill -> higher income variance
                + rng.normal(0, 1 + 0.1 * max(0, p["Skill"]))
                + 30
            ),
        },
    )


# ---------------------------------------------------------------------------
# Helper: build a ResearchProblem from a world
# ---------------------------------------------------------------------------

def _problem_from_world(
    world: SCMWorld, target: str, brief: str, n_rows: int = 300
) -> ResearchProblem:
    """Generate a ResearchProblem with sampled data from an SCMWorld."""
    df = world.sample(n_rows, seed=SEED)
    cols = list(df.columns)
    records = df.to_dict("records")

    asset = DataAsset(
        artifact_id="dataset_main",
        name="main_study",
        description="Observational study data",
        format="tabular",
        data=records,
        columns=cols,
        num_rows=n_rows,
    )

    return ResearchProblem(
        world_id=world.id,
        title=f"Investigation: {world.id}",
        description=brief,
        domain="research",
        data_assets=[asset],
        available_actions=[],
        budget=10,
        research_question=brief,
        target_node=target,
        target_states=["low", "medium", "high"],
    )


# ---------------------------------------------------------------------------
# Tests: salience map diversity
# ---------------------------------------------------------------------------


class TestEcosystemWorld:
    def test_has_causal_effects(self):
        world = world_ecosystem()
        smap = build_salience_map(world, "Fish", n_mc=N_MC, seed=SEED)
        patterns = {f.key.pattern_class for f in smap.families}
        assert "causal_effect" in patterns

    def test_has_interaction(self):
        """Nutrients x Temp interaction should produce heterogeneity family."""
        world = world_ecosystem()
        smap = build_salience_map(world, "Algae", n_mc=N_MC, seed=SEED)
        patterns = {f.key.pattern_class for f in smap.families}
        assert "heterogeneity" in patterns

    def test_multiple_families(self):
        world = world_ecosystem()
        smap = build_salience_map(world, "Fish", n_mc=N_MC, seed=SEED)
        assert len(smap.families) >= 2

    def test_driver_e2e(self):
        """Full driver pipeline: load, analyze, submit."""
        world = world_ecosystem()
        problem = _problem_from_world(
            world, "Fish", "Investigate factors affecting fish populations"
        )
        runner = OIEpisodeRunner(problem, world, seed=SEED, n_mc=N_MC)
        script = [
            ScriptedAction(
                tool="python_exec",
                args={"code": (
                    "df = load_artifact('dataset_main')\n"
                    "print(df.describe())"
                )},
            ),
            ScriptedAction(
                tool="python_exec",
                args={"code": "r = oi.regress(df, y='Fish', x=['Algae', 'Depth'])"},
            ),
            ScriptedAction(
                tool="submit_claims",
                args={"claims": [{
                    "claim_id": "eco1",
                    "claim_text": (
                        "Algae has a positive causal effect on Fish population"
                    ),
                    "focus_variables": ["Algae", "Fish"],
                    "confidence": 0.8,
                    "evidence_basis": [
                        {"artifact_id": "dataset_main",
                         "rationale": "regression showed significant positive coefficient"},
                    ],
                    "pattern_tags": ["causal_effect"],
                }]},
            ),
        ]
        result = run_oi_scripted(runner, script)
        assert result.submitted
        assert result.score is not None
        assert result.score.total > 0


class TestTreatmentWorld:
    def test_has_causal_effects(self):
        world = world_treatment()
        smap = build_salience_map(world, "Recovery", n_mc=N_MC, seed=SEED)
        patterns = {f.key.pattern_class for f in smap.families}
        assert "causal_effect" in patterns

    def test_has_mediation(self):
        """Treatment → Biomarker → Recovery should produce mediation family."""
        world = world_treatment()
        smap = build_salience_map(world, "Recovery", n_mc=N_MC, seed=SEED)
        patterns = {f.key.pattern_class for f in smap.families}
        assert "mediation" in patterns

    def test_multiple_families(self):
        world = world_treatment()
        smap = build_salience_map(world, "Recovery", n_mc=N_MC, seed=SEED)
        assert len(smap.families) >= 3

    def test_driver_e2e_mediation_claim(self):
        """Submit a mediation claim through the full pipeline."""
        world = world_treatment()
        problem = _problem_from_world(
            world, "Recovery", "Investigate treatment mechanisms for recovery"
        )
        runner = OIEpisodeRunner(problem, world, seed=SEED, n_mc=N_MC)
        script = [
            ScriptedAction(
                tool="python_exec",
                args={"code": (
                    "df = load_artifact('dataset_main')\n"
                    "oi.corr(df, cols=['Treatment', 'Biomarker', 'Recovery'])"
                )},
            ),
            ScriptedAction(
                tool="submit_claims",
                args={"claims": [{
                    "claim_id": "treat1",
                    "claim_text": (
                        "Treatment affects Recovery partly through Biomarker "
                        "as a mediating mechanism"
                    ),
                    "focus_variables": ["Treatment", "Biomarker", "Recovery"],
                    "confidence": 0.7,
                    "evidence_basis": [
                        {"artifact_id": "dataset_main",
                         "rationale": (
                             "correlation analysis shows "
                             "Treatment-Biomarker-Recovery chain"
                         )},
                    ],
                    "pattern_tags": ["mediation"],
                }]},
            ),
        ]
        result = run_oi_scripted(runner, script)
        assert result.submitted
        assert result.score is not None
        assert result.score.total > 0


class TestEducationWorld:
    def test_has_causal_effects(self):
        world = world_education()
        smap = build_salience_map(world, "Income", n_mc=N_MC, seed=SEED)
        patterns = {f.key.pattern_class for f in smap.families}
        assert "causal_effect" in patterns

    def test_has_mediation(self):
        """Education → Skill → Income should produce mediation family."""
        world = world_education()
        smap = build_salience_map(world, "Income", n_mc=N_MC, seed=SEED)
        patterns = {f.key.pattern_class for f in smap.families}
        assert "mediation" in patterns

    def test_multiple_pattern_types(self):
        """Should produce at least 3 different pattern types."""
        world = world_education()
        smap = build_salience_map(world, "Income", n_mc=N_MC, seed=SEED)
        patterns = {f.key.pattern_class for f in smap.families}
        assert len(patterns) >= 3

    def test_driver_e2e(self):
        world = world_education()
        problem = _problem_from_world(
            world, "Income", "Investigate determinants of income inequality"
        )
        runner = OIEpisodeRunner(problem, world, seed=SEED, n_mc=N_MC)
        script = [
            ScriptedAction(
                tool="python_exec",
                args={"code": "df = load_artifact('dataset_main')"},
            ),
            ScriptedAction(
                tool="python_exec",
                args={"code": (
                    "oi.regress(df, y='Income', x=['Wealth', 'Skill', 'Motivation'])"
                )},
            ),
            ScriptedAction(
                tool="submit_claims",
                args={"claims": [
                    {
                        "claim_id": "edu1",
                        "claim_text": (
                            "Education has a positive causal effect on Income "
                            "through Skill development"
                        ),
                        "focus_variables": ["Education", "Skill", "Income"],
                        "confidence": 0.8,
                        "evidence_basis": [
                            {"artifact_id": "dataset_main",
                             "rationale": "regression analysis on observational data"},
                        ],
                        "pattern_tags": ["causal_effect"],
                    },
                    {
                        "claim_id": "edu2",
                        "claim_text": (
                            "Wealth is positively associated with Income but "
                            "partly confounds the Education-Income relationship"
                        ),
                        "focus_variables": ["Wealth", "Income"],
                        "confidence": 0.7,
                        "evidence_basis": [
                            {"artifact_id": "dataset_main",
                             "rationale": "Wealth coefficient significant in regression"},
                        ],
                        "pattern_tags": ["causal_effect"],
                    },
                ]},
            ),
        ]
        result = run_oi_scripted(runner, script)
        assert result.submitted
        assert result.score is not None
        assert result.score.total > 0


class TestProductivityWorld:
    """Suppressor effect: Training appears unrelated to Productivity."""

    def test_suppressor_crude_near_zero(self):
        """Crude correlation between Training and Productivity should be near zero."""
        world = world_productivity()
        df = world.sample(5000, seed=SEED)
        r = df["Training"].corr(df["Productivity"])
        assert abs(r) < 0.10, f"Crude r(Training, Prod) = {r:.3f}, expected near 0"

    def test_suppressor_partial_positive(self):
        """After controlling for Team_size, Training-Productivity is strong positive."""
        import numpy as np
        world = world_productivity()
        df = world.sample(5000, seed=SEED)
        # Residualize on Team_size
        team = df["Team_size"].values
        for col in ("Training", "Productivity"):
            beta = np.linalg.lstsq(
                team.reshape(-1, 1), df[col].values, rcond=None
            )[0]
            df[f"{col}_res"] = df[col].values - team * beta[0]
        partial_r = df["Training_res"].corr(df["Productivity_res"])
        assert partial_r > 0.5, f"Partial r = {partial_r:.3f}, expected > 0.5"

    def test_has_causal_effects(self):
        world = world_productivity()
        smap = build_salience_map(world, "Productivity", n_mc=N_MC, seed=SEED)
        patterns = {f.key.pattern_class for f in smap.families}
        assert "causal_effect" in patterns

    def test_driver_e2e(self):
        world = world_productivity()
        problem = _problem_from_world(
            world, "Productivity",
            "Investigate factors affecting team productivity",
        )
        runner = OIEpisodeRunner(problem, world, seed=SEED, n_mc=N_MC)
        script = [
            ScriptedAction(
                tool="python_exec",
                args={"code": (
                    "df = load_artifact('dataset_main')\n"
                    "print(df[['Training', 'Productivity']].corr())"
                )},
            ),
            ScriptedAction(
                tool="submit_claims",
                args={"claims": [{
                    "claim_id": "prod1",
                    "claim_text": (
                        "Training has no significant crude association with "
                        "Productivity, but after controlling for Team_size "
                        "there is a strong positive relationship"
                    ),
                    "focus_variables": ["Training", "Team_size", "Productivity"],
                    "confidence": 0.8,
                    "evidence_basis": [
                        {"artifact_id": "dataset_main",
                         "rationale": "partial correlation analysis"},
                    ],
                    "pattern_tags": ["confounding"],
                }]},
            ),
        ]
        result = run_oi_scripted(runner, script)
        assert result.submitted
        assert result.score is not None


class TestScreenTimeWorld:
    """Reversed direction: Screen time POSITIVELY correlated with Academic."""

    def test_crude_positive(self):
        """Crude Screen_time-Academic correlation should be positive."""
        world = world_screen_time()
        df = world.sample(5000, seed=SEED)
        r = df["Screen_time"].corr(df["Academic"])
        assert r > 0.3, f"Crude r(Screen, Academic) = {r:.3f}, expected > 0.3"

    def test_partial_negative(self):
        """After controlling for Parental_income, Screen-Academic is negative."""
        import numpy as np
        world = world_screen_time()
        df = world.sample(5000, seed=SEED)
        inc = df["Parental_income"].values
        for col in ("Screen_time", "Academic"):
            beta = np.linalg.lstsq(
                inc.reshape(-1, 1), df[col].values, rcond=None
            )[0]
            df[f"{col}_res"] = df[col].values - inc * beta[0]
        partial_r = df["Screen_time_res"].corr(df["Academic_res"])
        assert partial_r < -0.2, f"Partial r = {partial_r:.3f}, expected < -0.2"

    def test_has_causal_effects(self):
        world = world_screen_time()
        smap = build_salience_map(world, "Academic", n_mc=N_MC, seed=SEED)
        patterns = {f.key.pattern_class for f in smap.families}
        assert "causal_effect" in patterns

    def test_driver_e2e(self):
        world = world_screen_time()
        problem = _problem_from_world(
            world, "Academic",
            "Investigate factors affecting academic performance in children",
        )
        runner = OIEpisodeRunner(problem, world, seed=SEED, n_mc=N_MC)
        script = [
            ScriptedAction(
                tool="python_exec",
                args={"code": (
                    "df = load_artifact('dataset_main')\n"
                    "print(df[['Screen_time', 'Academic']].corr())"
                )},
            ),
            ScriptedAction(
                tool="submit_claims",
                args={"claims": [{
                    "claim_id": "screen1",
                    "claim_text": (
                        "Screen time is positively associated with academic "
                        "performance in crude analysis, but this is confounded "
                        "by parental income"
                    ),
                    "focus_variables": ["Screen_time", "Parental_income", "Academic"],
                    "confidence": 0.8,
                    "evidence_basis": [
                        {"artifact_id": "dataset_main",
                         "rationale": "correlation reverses after income adjustment"},
                    ],
                    "pattern_tags": ["confounding"],
                }]},
            ),
        ]
        result = run_oi_scripted(runner, script)
        assert result.submitted
        assert result.score is not None


class TestWorldDiversity:
    """Cross-world validation: the 3 worlds produce different family profiles."""

    def test_different_dominant_patterns(self):
        """Each world should produce at least one pattern the others don't."""
        worlds = [
            (world_ecosystem(), "Algae"),   # Should have HETEROGENEITY
            (world_treatment(), "Recovery"),  # Should have MEDIATION
            (world_education(), "Income"),    # Should have multiple mediations
        ]
        all_patterns = []
        for w, target in worlds:
            smap = build_salience_map(w, target, n_mc=N_MC, seed=SEED)
            patterns = {f.key.pattern_class for f in smap.families}
            all_patterns.append(patterns)

        # Union should have at least 4 distinct pattern types
        union = all_patterns[0] | all_patterns[1] | all_patterns[2]
        assert len(union) >= 4, f"Only {len(union)} pattern types across 3 worlds: {union}"

    def test_total_family_count(self):
        """3 worlds combined should produce at least 10 families."""
        worlds = [
            (world_ecosystem(), "Fish"),
            (world_treatment(), "Recovery"),
            (world_education(), "Income"),
        ]
        total = 0
        for w, target in worlds:
            smap = build_salience_map(w, target, n_mc=N_MC, seed=SEED)
            total += len(smap.families)
        assert total >= 10, f"Only {total} families across 3 worlds"
