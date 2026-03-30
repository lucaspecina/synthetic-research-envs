"""OI Episode Runner: orchestrates solver investigation + scoring pipeline.

This is the central piece that connects all OI components:
  solver namespace -> load_artifact -> python_exec -> helpers -> trace
  -> submit_claims -> compile -> verify -> warrant -> score

The runner manages:
1. Artifact catalog + loading with provenance tracking
2. Python execution namespace with OI helpers injected
3. EpisodeTrace accumulation
4. Scoring pipeline integration

The solver itself (LLM generating code/decisions) is injected externally.
This module handles everything EXCEPT the LLM calls.

Design: research/notes/oi_trace_contract.md
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import pandas as pd

from sreg.models.open_investigation import (
    AnalysisRecord,
    ArtifactAccess,
    ClaimCard,
    EpisodeScore,
    EpisodeSubQuestionScore,
    EpisodeTrace,
    SubQuestionIntent,
)
from sreg.models.research_problem import DataAsset, ResearchProblem
from sreg.solver.scm_solver import SCMSolver
from sreg.tools.oi_helpers import OIHelpers, tag_dataframe
from sreg.world.scm import SCMWorld

logger = logging.getLogger(__name__)

MAX_CODE_CHARS = 8000
MAX_OUTPUT_CHARS = 12000
MAX_CLAIMS = 5


class ArtifactCatalog:
    """Manages base + derived artifacts for an OI episode.

    Base artifacts come from the ResearchProblem. Derived artifacts
    are created by the solver during investigation.
    """

    def __init__(self, data_assets: list[DataAsset]):
        self._base: dict[str, DataAsset] = {}
        self._loaded: dict[str, pd.DataFrame] = {}
        self._derived: dict[str, pd.DataFrame] = {}
        # Lineage: derived_id -> list of parent artifact_ids
        self._lineage: dict[str, list[str]] = {}

        for asset in data_assets:
            if asset.artifact_id:
                self._base[asset.artifact_id] = asset

    @property
    def base_ids(self) -> set[str]:
        return set(self._base.keys())

    @property
    def all_ids(self) -> set[str]:
        return self.base_ids | set(self._derived.keys())

    def exists(self, artifact_id: str) -> bool:
        return artifact_id in self._base or artifact_id in self._derived

    def load(self, artifact_id: str) -> pd.DataFrame:
        """Load an artifact by ID. Returns tagged DataFrame."""
        if artifact_id in self._loaded:
            return self._loaded[artifact_id]

        if artifact_id in self._derived:
            return self._derived[artifact_id]

        if artifact_id not in self._base:
            raise ValueError(
                f"Unknown artifact '{artifact_id}'. "
                f"Available: {sorted(self.all_ids)}"
            )

        asset = self._base[artifact_id]
        df = pd.DataFrame(asset.data)
        df = tag_dataframe(df, artifact_id)
        self._loaded[artifact_id] = df
        return df

    def save_derived(
        self, df: pd.DataFrame, label: str, parent_ids: list[str] | None = None
    ) -> str:
        """Save a solver-created artifact. Returns new artifact_id."""
        new_id = f"derived_{label}_{uuid.uuid4().hex[:6]}"
        tagged = tag_dataframe(df.copy(), new_id)
        self._derived[new_id] = tagged
        self._lineage[new_id] = parent_ids or []
        return new_id

    def get_lineage(self, artifact_id: str) -> list[str]:
        """Get parent artifact IDs for a derived artifact."""
        return self._lineage.get(artifact_id, [])

    def catalog_info(self) -> list[dict[str, Any]]:
        """Return metadata for the solver prompt's artifact catalog."""
        info = []
        for aid, asset in self._base.items():
            entry: dict[str, Any] = {
                "artifact_id": aid,
                "description": asset.description,
            }
            if asset.columns:
                entry["columns"] = asset.columns
            if asset.num_rows is not None:
                entry["num_rows"] = asset.num_rows
            if asset.source:
                entry["source"] = asset.source
            info.append(entry)
        return info


class _OIHelpersProxy:
    """Proxy that exposes only public analysis methods of OIHelpers.

    Prevents solver code from accessing _log(), _trace, or other internals
    that would allow forging warrant evidence without real analysis.
    """

    __slots__ = ("_corr", "_regress", "_stratify", "_test_independence", "_groupby_mean")

    def __init__(self, helpers: OIHelpers):
        # Bind to the methods directly — no backref to helpers object
        self._corr = helpers.corr
        self._regress = helpers.regress
        self._stratify = helpers.stratify
        self._test_independence = helpers.test_independence
        self._groupby_mean = helpers.groupby_mean

    def corr(self, *args: Any, **kwargs: Any) -> Any:
        return self._corr(*args, **kwargs)

    def regress(self, *args: Any, **kwargs: Any) -> Any:
        return self._regress(*args, **kwargs)

    def stratify(self, *args: Any, **kwargs: Any) -> Any:
        return self._stratify(*args, **kwargs)

    def test_independence(self, *args: Any, **kwargs: Any) -> Any:
        return self._test_independence(*args, **kwargs)

    def groupby_mean(self, *args: Any, **kwargs: Any) -> Any:
        return self._groupby_mean(*args, **kwargs)


class OIEpisodeRunner:
    """Runs an Open Investigation episode.

    Lifecycle:
      1. __init__: set up catalog, trace, namespace
      2. run_code(): solver executes analysis code (multiple calls)
      3. submit_claims(): solver submits findings -> score computed
      4. get_results(): return score + trace

    The runner does NOT drive the solver loop -- that's the caller's job.
    The runner provides the execution environment and scoring.
    """

    def __init__(
        self,
        problem: ResearchProblem,
        world: SCMWorld,
        *,
        seed: int = 42,
        n_mc: int = 50_000,
        llm_call: Any | None = None,
    ):
        self.problem = problem
        self.world = world
        self.seed = seed
        self.n_mc = n_mc
        self._llm_call = llm_call

        # Sub-questions for scoring (optional)
        self._subquestions: list[SubQuestionIntent] = []
        self._sq_score: EpisodeSubQuestionScore | None = None

        # Trace infrastructure
        self.trace = EpisodeTrace()
        self._step: dict[str, int] = {"current": 0}

        # Artifact management
        self.catalog = ArtifactCatalog(problem.data_assets)

        # Instrumented helpers
        self._helpers = OIHelpers(self.trace, self._step)

        # Python namespace
        self._namespace = self._build_namespace()

        # Submission state
        self._submitted = False
        self._score: EpisodeScore | None = None

    def _build_namespace(self) -> dict:
        """Build the solver's Python namespace with OI-specific tools.

        SECURITY: Functions are wrapped as plain closures to prevent
        solver code from reaching runner internals via __self__.
        The oi helpers object only exposes public analysis methods.
        """
        from sreg.agent.python_exec import make_python_namespace

        ns = make_python_namespace()

        # Wrap as plain functions — no __self__ backref to runner
        catalog = self.catalog
        trace = self.trace
        step = self._step

        def load_artifact(artifact_id: str) -> pd.DataFrame:
            trace.accesses.append(
                ArtifactAccess(artifact_id=artifact_id, step=step["current"])
            )
            return catalog.load(artifact_id)

        def save_artifact(df: pd.DataFrame, label: str) -> str:
            # Infer parent from source df's tag
            parent_id = getattr(df, "_oi_artifact_id", None)
            parent_ids = [parent_id] if parent_id else []
            new_id = catalog.save_derived(df, label, parent_ids=parent_ids)
            # Log as analysis record for provenance
            trace.analyses.append(
                AnalysisRecord(
                    analysis_id=f"oi_save_{uuid.uuid4().hex[:8]}",
                    input_artifact_ids=parent_ids or ["unknown"],
                    columns_used=[],
                    op_type="derive",
                    step=step["current"],
                    output_artifact_id=new_id,
                )
            )
            return new_id

        ns["load_artifact"] = load_artifact
        ns["save_artifact"] = save_artifact
        # Expose OIHelpers via proxy — only public analysis methods,
        # no _log, _trace, or other internals accessible to solver
        ns["oi"] = _OIHelpersProxy(self._helpers)
        return ns

    @property
    def target(self) -> str:
        """The target variable for this investigation."""
        return self.problem.target_node

    def _build_extraction_context(self, observable_names: list[str]):
        """Build rich context for the claim-extraction LLM."""
        from sreg.tools.oi_extraction import ExtractionContext

        variable_descriptions: dict[str, str] = {}
        for name in observable_names:
            meta = self.world.variable_meta.get(name)
            if not meta or not (meta.description or meta.unit):
                continue
            desc = meta.description.rstrip(".") if meta.description else ""
            if meta.unit:
                desc = f"{desc} [unit: {meta.unit}]" if desc else f"unit: {meta.unit}"
            variable_descriptions[name] = desc

        return ExtractionContext(
            research_brief=self.problem.research_question,
            domain=self.problem.domain,
            description=self.problem.description,
            title=self.problem.title,
            variable_descriptions=variable_descriptions,
            sub_questions=[
                {
                    "sq_id": sq.sq_id,
                    "pattern": sq.pattern,
                    "text_gloss": sq.text_gloss or sq.sq_id,
                }
                for sq in self._subquestions
            ],
        )

    @property
    def research_brief(self) -> str:
        """The research question/brief visible to the solver."""
        return self.problem.research_question

    @property
    def is_submitted(self) -> bool:
        return self._submitted

    # -----------------------------------------------------------------
    # Solver interface: run_code
    # -----------------------------------------------------------------

    def run_code(self, code: str) -> dict[str, Any]:
        """Execute Python code in the persistent namespace.

        Returns dict with keys: output, ok, step.
        """
        from sreg.agent.python_exec import execute_code

        self._step["current"] += 1
        result = execute_code(code, self._namespace)

        return {
            "output": result.output,
            "ok": result.ok,
            "step": self._step["current"],
        }

    # -----------------------------------------------------------------
    # Claim submission and scoring
    # -----------------------------------------------------------------

    def submit_claims(
        self,
        claims: list[ClaimCard],
        compiled_claims: list | None = None,
    ) -> EpisodeScore:
        """Submit claims and compute the episode score.

        Args:
            claims: The solver's ClaimCards (1-5 claims).
            compiled_claims: Pre-compiled CompilerOutputs aligned 1:1
                with claims (same order, same claim_ids). If None,
                auto-compiles via extraction pipeline.

        Returns:
            EpisodeScore with correctness, coverage, efficiency, warrant.
        """
        from sreg.tools.oi_salience import build_salience_map

        if self._submitted:
            raise RuntimeError("Claims already submitted for this episode")

        if len(claims) > MAX_CLAIMS:
            raise ValueError(f"Too many claims: {len(claims)} > {MAX_CLAIMS}")

        if len(claims) == 0:
            raise ValueError("Must submit at least 1 claim")

        # Check for duplicate claim_ids
        claim_ids = [c.claim_id for c in claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("Duplicate claim_ids in submission")

        # Record claim steps in trace
        for claim in claims:
            self.trace.claim_steps[claim.claim_id] = self._step["current"]

        # Validate and use pre-compiled claims, or auto-compile
        if compiled_claims is not None:
            self._validate_compiled_alignment(claims, compiled_claims)
            compiled = compiled_claims
        else:
            from sreg.tools.oi_compiler import build_world_summary
            from sreg.tools.oi_extraction import compile_episode_claims

            summary = build_world_summary(
                self.world, self.target, n_mc=self.n_mc, seed=self.seed
            )
            ctx = self._build_extraction_context(summary.observable_names)
            compiled = compile_episode_claims(
                claims, summary, llm_call=self._llm_call, context=ctx
            )

        self._submitted = True

        # --- Primary scoring: sub-questions (fast, no salience map) ---
        if self._subquestions:
            self._sq_score = self._score_with_subquestions(compiled)
            logger.info(
                "SQ score (primary): total=%.3f correctness=%.3f "
                "coverage=%.3f",
                self._sq_score.total,
                self._sq_score.correctness,
                self._sq_score.weighted_coverage,
            )

        # --- Diagnostic scoring: v2 with salience map (slow, optional) ---
        # Only computed when no sub-questions are set (legacy/curated worlds)
        # or for explicit diagnostic runs. NOT in the E2E critical path.
        if not self._subquestions:
            solver = SCMSolver(self.world, n_mc=self.n_mc)
            salience = build_salience_map(
                self.world, self.target, n_mc=self.n_mc, seed=self.seed
            )
            all_asset_ids = self.catalog.all_ids
            from sreg.tools.oi_compiler import score_compiled_episode_v2

            score = score_compiled_episode_v2(
                compiled_claims=compiled,
                families=salience.families,
                world=self.world,
                solver=solver,
                target=self.target,
                n_mc=self.n_mc,
                seed=self.seed,
                claim_cards=claims,
                trace=None,
                data_asset_ids=all_asset_ids,
            )
            self._score = score
            logger.info(
                "v2 score (diagnostic): total=%.3f correctness=%.3f "
                "coverage=%.3f",
                score.total,
                score.correctness,
                score.coverage,
            )

        return self._sq_score or self._score

    @staticmethod
    def _validate_compiled_alignment(
        claims: list[ClaimCard], compiled: list
    ) -> None:
        """Validate compiled_claims aligns 1:1 with claims."""
        from sreg.tools.oi_compiler import CompilerOutput

        if len(compiled) != len(claims):
            raise ValueError(
                f"compiled_claims length ({len(compiled)}) != "
                f"claims length ({len(claims)})"
            )
        for i, item in enumerate(compiled):
            if not isinstance(item, CompilerOutput):
                raise TypeError(
                    f"compiled_claims[{i}] must be CompilerOutput, "
                    f"got {type(item).__name__}"
                )
            if item.claim_id != claims[i].claim_id:
                raise ValueError(
                    f"compiled_claims[{i}].claim_id='{item.claim_id}' != "
                    f"claims[{i}].claim_id='{claims[i].claim_id}'"
                )

    # -----------------------------------------------------------------
    # Sub-question support
    # -----------------------------------------------------------------

    def set_subquestions(self, sqs: list[SubQuestionIntent]) -> None:
        """Set sub-questions for SQ scoring. Call before submit_claims."""
        self._subquestions = list(sqs)

    def _score_with_subquestions(
        self, compiled: list,
    ) -> EpisodeSubQuestionScore:
        """Compute sub-question score from compiled claims."""
        from sreg.tools.oi_subquestions import (
            resolve_all,
            score_episode_with_subquestions,
        )

        # Resolve SQs against the world
        resolved = resolve_all(
            self._subquestions, self.world,
            target=self.target, n_mc=self.n_mc, seed=self.seed,
        )

        # Extract (ClaimIntent, truth) tuples — one per CompiledUnit (A22)
        from sreg.tools.oi_compiler import CompilerOutput
        from sreg.tools.oi_verifier import verify_atom

        solver = SCMSolver(self.world, n_mc=self.n_mc)
        claim_tuples = []
        for co in compiled:
            if not isinstance(co, CompilerOutput) or not co.compiled:
                continue
            for unit in co.units:
                # Per-unit truth: conjunctive (all atoms in unit must hold)
                if unit.specs:
                    verdicts = [
                        verify_atom(s, self.world, solver, self.n_mc, self.seed)
                        for s in unit.specs
                    ]
                    truth = 1.0 if all(v.solver_assertion_holds for v in verdicts) else 0.0
                else:
                    truth = 0.0
                claim_tuples.append((unit.intent, truth))

        return score_episode_with_subquestions(claim_tuples, resolved)

    # -----------------------------------------------------------------
    # Results and metadata
    # -----------------------------------------------------------------

    def get_score(self) -> EpisodeScore | None:
        """Return the episode score, or None if not yet submitted."""
        return self._score

    def get_sq_score(self) -> EpisodeSubQuestionScore | None:
        """Return the sub-question score, or None if not computed."""
        return self._sq_score

    def get_trace(self) -> EpisodeTrace:
        """Return the full episode trace."""
        return self.trace

    def get_solver_prompt_context(self) -> dict[str, Any]:
        """Return context needed to build the solver prompt.

        This provides the briefing, artifact catalog, and other metadata
        that the solver prompt template needs.
        """
        return {
            "research_brief": self.research_brief,
            "artifact_catalog": self.catalog.catalog_info(),
            "target": self.target,
            "domain": self.problem.domain,
            "title": self.problem.title,
        }


__all__ = [
    "ArtifactCatalog",
    "OIEpisodeRunner",
]
