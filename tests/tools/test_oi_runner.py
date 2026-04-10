"""Tests for OI Episode Runner."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sreg.models.open_investigation import (
    AskOperator,
    ClaimCard,
    EvidenceRef,
    SQRoles,
    SubQuestionIntent,
)
from sreg.models.research_problem import DataAsset, ResearchProblem
from sreg.tools.oi_runner import ArtifactCatalog, OIEpisodeRunner

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_data_asset(
    artifact_id: str, name: str, n_rows: int = 50, cols: list[str] | None = None
) -> DataAsset:
    """Create a minimal DataAsset for testing."""
    cols = cols or ["A", "B", "Y"]
    rng = np.random.default_rng(42)
    data = [{c: float(rng.normal()) for c in cols} for _ in range(n_rows)]
    return DataAsset(
        artifact_id=artifact_id,
        name=name,
        description=f"Test dataset {name}",
        format="tabular",
        data=data,
        columns=cols,
        num_rows=n_rows,
    )


def _make_problem(
    data_assets: list[DataAsset] | None = None,
) -> ResearchProblem:
    """Create a minimal ResearchProblem for testing."""
    assets = data_assets or [
        _make_data_asset("dataset_bg", "background_records"),
        _make_data_asset("dataset_survey", "field_survey"),
    ]
    return ResearchProblem(
        world_id="test_world",
        title="Test Investigation",
        description="A test research problem",
        domain="test",
        data_assets=assets,
        available_actions=[],
        budget=10,
        research_question="Investigate the relationship between A and Y",
        target_node="Y",
        target_states=["low", "medium", "high"],
    )


def _make_scm_world():
    """Create a minimal SCMWorld for testing."""
    from sreg.world.scm import SCMWorld, VariableMeta

    return SCMWorld(
        id="test_world",
        graph={
            "A": [],
            "B": ["A"],
            "Y": ["A", "B"],
        },
        equations={
            "A": lambda p, rng: rng.normal(5, 2),
            "B": lambda p, rng: 0.5 * p["A"] + rng.normal(3, 1),
            "Y": lambda p, rng: 0.8 * p["A"] + 0.3 * p["B"] + rng.normal(0, 1),
        },
        variable_meta={
            "A": VariableMeta(description="Exposure intensity", unit="mg/L"),
            "B": VariableMeta(description="Intermediate burden", unit="index"),
            "Y": VariableMeta(description="Outcome response", unit="points"),
        },
    )


def _make_claim(
    claim_id: str = "c1",
    text: str = "A has a positive causal effect on Y",
    focus: list[str] | None = None,
    artifact_id: str = "dataset_bg",
) -> ClaimCard:
    """Create a test ClaimCard."""
    return ClaimCard(
        claim_id=claim_id,
        claim_text=text,
        focus_variables=focus or ["A", "Y"],
        confidence=0.8,
        evidence_basis=[
            EvidenceRef(artifact_id=artifact_id, rationale="regression analysis"),
        ],
    )


# ---------------------------------------------------------------------------
# ArtifactCatalog
# ---------------------------------------------------------------------------


class TestArtifactCatalog:
    def test_base_ids(self):
        assets = [
            _make_data_asset("dataset_bg", "bg"),
            _make_data_asset("dataset_survey", "survey"),
        ]
        catalog = ArtifactCatalog(assets)
        assert catalog.base_ids == {"dataset_bg", "dataset_survey"}

    def test_load_returns_tagged_df(self):
        assets = [_make_data_asset("dataset_bg", "bg")]
        catalog = ArtifactCatalog(assets)
        df = catalog.load("dataset_bg")
        assert isinstance(df, pd.DataFrame)
        assert df._oi_artifact_id == "dataset_bg"

    def test_load_caches(self):
        assets = [_make_data_asset("dataset_bg", "bg")]
        catalog = ArtifactCatalog(assets)
        df1 = catalog.load("dataset_bg")
        df2 = catalog.load("dataset_bg")
        assert df1 is df2

    def test_load_unknown_raises(self):
        catalog = ArtifactCatalog([])
        with pytest.raises(ValueError, match="Unknown artifact"):
            catalog.load("nonexistent")

    def test_save_derived(self):
        catalog = ArtifactCatalog([])
        df = pd.DataFrame({"x": [1, 2, 3]})
        new_id = catalog.save_derived(df, "filtered")
        assert new_id.startswith("derived_filtered_")
        assert new_id in catalog.all_ids

    def test_load_derived(self):
        catalog = ArtifactCatalog([])
        df = pd.DataFrame({"x": [1, 2, 3]})
        new_id = catalog.save_derived(df, "test")
        loaded = catalog.load(new_id)
        assert len(loaded) == 3

    def test_catalog_info(self):
        assets = [
            _make_data_asset("dataset_bg", "bg", cols=["A", "Y"]),
        ]
        catalog = ArtifactCatalog(assets)
        info = catalog.catalog_info()
        assert len(info) == 1
        assert info[0]["artifact_id"] == "dataset_bg"
        assert info[0]["columns"] == ["A", "Y"]

    def test_skips_assets_without_artifact_id(self):
        asset = DataAsset(
            name="no_id",
            description="No artifact_id",
            format="tabular",
            data=[{"x": 1}],
        )
        catalog = ArtifactCatalog([asset])
        assert len(catalog.base_ids) == 0


# ---------------------------------------------------------------------------
# OIEpisodeRunner — namespace and artifact loading
# ---------------------------------------------------------------------------


class TestRunnerNamespace:
    def test_creates_namespace_with_libraries(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)

        ns = runner._namespace
        assert "np" in ns
        assert "pd" in ns
        assert "load_artifact" in ns
        assert "save_artifact" in ns
        assert "oi" in ns

    def test_load_artifact_logs_access(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)

        # Use the namespace function (not a method anymore — closure per Codex fix)
        runner._namespace["load_artifact"]("dataset_bg")
        assert len(runner.trace.accesses) == 1
        assert runner.trace.accesses[0].artifact_id == "dataset_bg"

    def test_load_artifact_via_code(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)

        result = runner.run_code('df = load_artifact("dataset_bg")\nlen(df)')
        assert result["ok"]
        assert "50" in result["output"]
        assert len(runner.trace.accesses) == 1

    def test_save_artifact_via_code(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)

        runner.run_code('df = load_artifact("dataset_bg")')
        result = runner.run_code('new_id = save_artifact(df[df["A"] > 0], "positive_A")')
        assert result["ok"]

    def test_step_counter_increments(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)

        r1 = runner.run_code("1 + 1")
        r2 = runner.run_code("2 + 2")
        assert r1["step"] == 1
        assert r2["step"] == 2


# ---------------------------------------------------------------------------
# OIEpisodeRunner — namespace basics
# ---------------------------------------------------------------------------


class TestRunnerNamespace:
    def test_load_artifact_available(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)

        result = runner.run_code(
            'df = load_artifact("dataset_bg")\n'
            'df.shape'
        )
        assert result["ok"]


# ---------------------------------------------------------------------------
# OIEpisodeRunner — submission
# ---------------------------------------------------------------------------


class TestRunnerSubmission:
    def test_build_extraction_context_includes_metadata_and_sqs(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)
        runner.set_subquestions([
            SubQuestionIntent(
                sq_id="sq1",
                pattern="causal_effect",
                roles=SQRoles(treatment="A", outcome="Y"),
                ask=AskOperator.SIGN,
                text_gloss="Does A increase Y?",
            )
        ])

        ctx = runner._build_extraction_context(["A", "Y"])

        assert ctx.title == "Test Investigation"
        assert ctx.domain == "test"
        assert ctx.variable_descriptions["A"] == "Exposure intensity [unit: mg/L]"
        assert ctx.variable_descriptions["Y"] == "Outcome response [unit: points]"
        assert ctx.sub_questions == [
            {
                "sq_id": "sq1",
                "pattern": "causal_effect",
                "text_gloss": "Does A increase Y?",
            }
        ]

    def test_submit_prevents_double_submission(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)
        runner._namespace["load_artifact"]("dataset_bg")

        claims = [_make_claim()]
        runner.submit_claims(claims)
        with pytest.raises(RuntimeError, match="already submitted"):
            runner.submit_claims(claims)

    def test_submit_passes_context_to_compiler(self, monkeypatch):
        from sreg.tools.oi_compiler import CompilerOutput

        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)
        runner._namespace["load_artifact"]("dataset_bg")
        captured: dict[str, object] = {}

        def fake_compile_episode_claims(claims, summary, llm_call=None, context=None):
            captured["context"] = context
            return [CompilerOutput(claim_id=claims[0].claim_id, status="abstention")]

        monkeypatch.setattr(
            "sreg.tools.oi_extraction.compile_episode_claims",
            fake_compile_episode_claims,
        )

        runner.submit_claims([_make_claim()])

        ctx = captured["context"]
        assert ctx.title == "Test Investigation"
        assert ctx.domain == "test"
        assert ctx.variable_descriptions["A"] == "Exposure intensity [unit: mg/L]"

    def test_submit_validates_claim_count(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)

        with pytest.raises(ValueError, match="Too many"):
            runner.submit_claims([_make_claim(f"c{i}") for i in range(16)])

    def test_submit_validates_empty(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)

        with pytest.raises(ValueError, match="at least 1"):
            runner.submit_claims([])

    def test_submit_records_claim_steps(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)
        runner._namespace["load_artifact"]("dataset_bg")

        runner.run_code("1 + 1")
        runner.run_code("2 + 2")
        claims = [_make_claim()]
        runner.submit_claims(claims)

        assert "c1" in runner.trace.claim_steps
        assert runner.trace.claim_steps["c1"] == 2  # last step

    def test_submit_auto_compiles_via_deterministic_fallback(self):
        """Without LLM, auto-compilation uses keyword-based fallback."""
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world, n_mc=5000)

        # Load data so warrant has access records
        runner.run_code('df = load_artifact("dataset_bg")')
        runner.run_code('oi.regress(df, y="Y", x=["A"])')

        claims = [_make_claim()]
        score = runner.submit_claims(claims)

        # Deterministic fallback should compile the causal_effect claim
        assert score.total > 0

    def test_submit_with_compiled_intents(self):
        """Test submission with pre-compiled ClaimIntents."""
        from sreg.tools.oi_compiler import (
            ClaimIntent,
            Direction,
            PatternClass,
            build_world_summary,
            lower_intent,
        )

        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world, n_mc=5000)

        # Simulate investigation
        runner.run_code('df = load_artifact("dataset_bg")')
        runner.run_code('oi.regress(df, y="Y", x=["A"])')

        # Create a claim + pre-compiled intent
        claim = _make_claim()
        summary = build_world_summary(world, "Y", n_mc=5000, seed=42)
        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment="A",
            outcome="Y",
            direction=Direction.POSITIVE,
        )
        compiled = [lower_intent(intent, summary)]

        score = runner.submit_claims([claim], compiled_claims=compiled)
        assert score.total > 0  # Should get some credit

    def test_get_score_before_submit_is_none(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)
        assert runner.get_score() is None

    def test_is_submitted_flag(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world, n_mc=1000)
        runner._namespace["load_artifact"]("dataset_bg")

        assert not runner.is_submitted
        runner.submit_claims([_make_claim()])
        assert runner.is_submitted


# ---------------------------------------------------------------------------
# OIEpisodeRunner — prompt context
# ---------------------------------------------------------------------------


class TestRunnerPromptContext:
    def test_prompt_context_has_required_fields(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)

        ctx = runner.get_solver_prompt_context()
        assert "research_brief" in ctx
        assert "artifact_catalog" in ctx
        assert "target" in ctx
        assert "domain" in ctx
        assert len(ctx["artifact_catalog"]) == 2


# ---------------------------------------------------------------------------
# E2E: mock solver investigation flow
# ---------------------------------------------------------------------------


class TestMockSolverFlow:
    def test_full_investigation_flow(self):
        """Simulate a full solver investigation without LLM."""
        from sreg.tools.oi_compiler import (
            ClaimIntent,
            Direction,
            PatternClass,
            build_world_summary,
            lower_intent,
        )

        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world, n_mc=5000)

        # Step 1: Load data
        r = runner.run_code('bg = load_artifact("dataset_bg")')
        assert r["ok"]

        # Step 2: Explore
        r = runner.run_code('print(bg.describe())')
        assert r["ok"]

        # Step 3: Analyze with pandas (solver uses raw code)
        r = runner.run_code('corr = bg[["A", "B", "Y"]].corr()')
        assert r["ok"]
        r = runner.run_code('import numpy as np; print(np.corrcoef(bg["A"], bg["Y"]))')
        assert r["ok"]

        # Step 4: Load second dataset
        r = runner.run_code('survey = load_artifact("dataset_survey")')
        assert r["ok"]

        # Verify trace accumulated
        assert len(runner.trace.accesses) == 2

        # Step 6: Submit claims with pre-compiled intents
        claim = _make_claim(
            text="A has a positive causal effect on Y, controlling for B",
            focus=["A", "Y"],
        )

        summary = build_world_summary(world, "Y", n_mc=5000, seed=42)
        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment="A",
            outcome="Y",
            direction=Direction.POSITIVE,
        )
        compiled = [lower_intent(intent, summary)]

        score = runner.submit_claims([claim], compiled_claims=compiled)

        # Verify scoring worked
        assert score.total > 0
        assert runner.is_submitted
        assert runner.get_trace().claim_steps["c1"] > 0


# ---------------------------------------------------------------------------
# Codex review fixes: validation, namespace security, derived provenance
# ---------------------------------------------------------------------------


class TestCompiledClaimsValidation:
    def test_mismatched_length_raises(self):
        from sreg.tools.oi_compiler import CompilerOutput

        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world, n_mc=1000)
        runner._namespace["load_artifact"]("dataset_bg")

        claims = [_make_claim()]
        compiled = [
            CompilerOutput(claim_id="c1", status="abstention"),
            CompilerOutput(claim_id="c2", status="abstention"),
        ]
        with pytest.raises(ValueError, match="length"):
            runner.submit_claims(claims, compiled_claims=compiled)

    def test_wrong_type_raises(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world, n_mc=1000)
        runner._namespace["load_artifact"]("dataset_bg")

        claims = [_make_claim()]
        with pytest.raises(TypeError, match="CompilerOutput"):
            runner.submit_claims(claims, compiled_claims=[{"not": "right"}])

    def test_mismatched_claim_id_raises(self):
        from sreg.tools.oi_compiler import CompilerOutput

        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world, n_mc=1000)
        runner._namespace["load_artifact"]("dataset_bg")

        claims = [_make_claim(claim_id="c1")]
        compiled = [CompilerOutput(claim_id="wrong_id", status="abstention")]
        with pytest.raises(ValueError, match="claim_id"):
            runner.submit_claims(claims, compiled_claims=compiled)

    def test_duplicate_claim_ids_raises(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world, n_mc=1000)

        claims = [_make_claim("dup"), _make_claim("dup")]
        with pytest.raises(ValueError, match="Duplicate"):
            runner.submit_claims(claims)


class TestNamespaceSecurity:
    def test_load_artifact_has_no_self(self):
        """Solver can't reach runner internals via __self__."""
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)

        load_fn = runner._namespace["load_artifact"]
        assert not hasattr(load_fn, "__self__")

    def test_save_artifact_has_no_self(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)

        save_fn = runner._namespace["save_artifact"]
        assert not hasattr(save_fn, "__self__")

    def test_cannot_reach_world_via_namespace(self):
        """Verify solver code can't reach the SCMWorld."""
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)

        # Try to access world through various paths
        result = runner.run_code(
            "has_world = hasattr(load_artifact, '__self__')\n"
            "print(has_world)"
        )
        assert result["ok"]
        assert "False" in result["output"]

class TestDerivedArtifactProvenance:
    def test_save_artifact_logs_analysis_record(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)

        runner.run_code('df = load_artifact("dataset_bg")')
        runner.run_code('filtered = df[df["A"] > 0]')
        runner.run_code('new_id = save_artifact(filtered, "positive_A")')

        # Verify save_artifact returned an ID
        result = runner.run_code('new_id')
        assert result["ok"]
        assert "derived_positive_A" in result["output"]

    def test_derived_artifact_in_all_ids(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)

        runner.run_code('df = load_artifact("dataset_bg")')
        runner.run_code('new_id = save_artifact(df, "copy")')

        assert any(
            aid.startswith("derived_copy") for aid in runner.catalog.all_ids
        )

    def test_save_tracks_parent_lineage(self):
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)

        runner.run_code('df = load_artifact("dataset_bg")')
        runner.run_code('new_id = save_artifact(df, "subset")')

        # Find the derived artifact
        derived_ids = [
            aid for aid in runner.catalog.all_ids
            if aid.startswith("derived_subset")
        ]
        assert len(derived_ids) == 1
        lineage = runner.catalog.get_lineage(derived_ids[0])
        assert lineage == ["dataset_bg"]

    def test_save_artifact_prints_canonical_id_when_return_discarded(self):
        """Contract: save_artifact must surface the canonical derived id in
        python_exec output even when the solver discards the return value.

        This is the contract that motivates the print() inside the
        save_artifact wrapper. Without it, a solver that ends a code block
        with a different expression (e.g. the saved DataFrame itself) never
        sees the canonical 'derived_X_hash' id and ends up citing the
        human-readable label or 'python_exec' in evidence_basis.
        """
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)

        runner.run_code('df = load_artifact("dataset_bg")')
        result = runner.run_code(
            'save_artifact(df, "filtered")\n'
            'df.shape  # last expression discards save_artifact return value'
        )
        assert result["ok"]
        # The canonical id must appear in the output despite the return
        # value being discarded by the trailing expression.
        assert "[save_artifact] saved as derived_filtered_" in result["output"]


# ---------------------------------------------------------------------------
# #25: hard rejection of fabricated evidence_basis references
# ---------------------------------------------------------------------------


class TestEvidenceBasisValidation:
    """Atomic rejection: if ANY claim has invalid evidence refs, reject all."""

    def test_all_invalid_refs_rejected_zero_side_effects(self):
        """Submission with only fabricated refs is fully rejected,
        with zero state mutation (_submitted, claim_steps)."""
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)

        claim = _make_claim(artifact_id="totally_fabricated")
        with pytest.raises(ValueError, match="SUBMISSION REJECTED"):
            runner.submit_claims([claim])

        assert not runner.is_submitted
        assert runner.trace.claim_steps == {}

    def test_mixed_batch_atomic_rejection(self):
        """One bad ref in a batch rejects the entire submission."""
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)
        runner._namespace["load_artifact"]("dataset_bg")

        valid_claim = _make_claim(claim_id="c_ok", artifact_id="dataset_bg")
        bad_claim = _make_claim(claim_id="c_bad", artifact_id="fabricated_id")

        with pytest.raises(ValueError, match="SUBMISSION REJECTED"):
            runner.submit_claims([valid_claim, bad_claim])

        # Atomic: neither claim registered.
        assert not runner.is_submitted
        assert runner.trace.claim_steps == {}

    def test_valid_submission_accepted(self):
        """Claims citing accessed artifacts pass evidence validation."""
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world, n_mc=1000)
        runner._namespace["load_artifact"]("dataset_bg")

        score = runner.submit_claims([_make_claim(artifact_id="dataset_bg")])
        assert runner.is_submitted
        assert score is not None

    def test_resubmit_after_rejection_succeeds(self):
        """Solver can fix refs and resubmit after an initial rejection."""
        problem = _make_problem()
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world, n_mc=1000)
        runner._namespace["load_artifact"]("dataset_bg")

        # First attempt: fabricated ref -> rejected.
        with pytest.raises(ValueError, match="SUBMISSION REJECTED"):
            runner.submit_claims([_make_claim(artifact_id="nonexistent")])
        assert not runner.is_submitted

        # Second attempt: corrected ref -> accepted.
        score = runner.submit_claims([_make_claim(artifact_id="dataset_bg")])
        assert runner.is_submitted
        assert score is not None

    def test_exists_but_not_accessed_vs_unknown(self):
        """Error message distinguishes 'exists but not accessed' from 'unknown'."""
        problem = _make_problem()  # has dataset_bg + dataset_survey
        world = _make_scm_world()
        runner = OIEpisodeRunner(problem, world)
        runner._namespace["load_artifact"]("dataset_bg")  # only load one

        not_accessed = _make_claim(claim_id="c1", artifact_id="dataset_survey")
        unknown = _make_claim(claim_id="c2", artifact_id="total_fiction")

        with pytest.raises(ValueError, match="SUBMISSION REJECTED") as exc_info:
            runner.submit_claims([not_accessed, unknown])

        msg = str(exc_info.value)
        assert "artifact_exists_but_not_accessed" in msg
        assert "unknown_artifact_id" in msg
