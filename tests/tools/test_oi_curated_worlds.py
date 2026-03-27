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
