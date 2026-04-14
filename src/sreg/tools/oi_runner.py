"""OI Episode Runner: orchestrates solver investigation + scoring pipeline.

This is the central piece that connects all OI components:
  solver namespace -> load_artifact -> python_exec -> trace
  -> submit_claims -> compile -> verify -> score

The runner manages:
1. Artifact catalog + loading with provenance tracking
2. Python execution namespace
3. EpisodeTrace accumulation
4. Scoring pipeline integration

The solver itself (LLM generating code/decisions) is injected externally.
This module handles everything EXCEPT the LLM calls.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import pandas as pd

from sreg.models.open_investigation import (
    MAX_CLAIMS,
    ArtifactAccess,
    ClaimCard,
    EpisodeSubQuestionScore,
    EpisodeTrace,
    SubQuestionIntentV2,
    SubQuestionScore,
)
from sreg.models.research_problem import DataAsset, ResearchProblem
from sreg.solver.scm_solver import SCMSolver
from sreg.world.scm import SCMWorld

logger = logging.getLogger(__name__)

MAX_CODE_CHARS = 8000
MAX_OUTPUT_CHARS = 12000


# ---------------------------------------------------------------------------
# Evidence-basis validation helper (#25)
# ---------------------------------------------------------------------------

def validate_evidence_refs(
    claims: list[ClaimCard],
    accessed_ids: set[str],
    catalog_ids: set[str] | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Check that every evidence_basis.artifact_id was actually accessed.

    Returns a dict mapping claim_id -> list of error dicts for each invalid
    ref. Empty dict means all refs are valid.

    Each error dict has:
      - artifact_id: the invalid id
      - reason: "unknown_artifact_id" or "artifact_exists_but_not_accessed"
    """
    errors: dict[str, list[dict[str, str]]] = {}
    for claim in claims:
        if not claim.evidence_basis:
            continue
        claim_errors = []
        for ref in claim.evidence_basis:
            if ref.artifact_id not in accessed_ids:
                if catalog_ids and ref.artifact_id in catalog_ids:
                    reason = "artifact_exists_but_not_accessed"
                else:
                    reason = "unknown_artifact_id"
                claim_errors.append({
                    "artifact_id": ref.artifact_id,
                    "reason": reason,
                })
        if claim_errors:
            errors[claim.claim_id] = claim_errors
    return errors


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
        df._oi_artifact_id = artifact_id  # type: ignore[attr-defined]
        self._loaded[artifact_id] = df
        return df

    def save_derived(
        self, df: pd.DataFrame, label: str, parent_ids: list[str] | None = None
    ) -> str:
        """Save a solver-created artifact. Returns new artifact_id."""
        new_id = f"derived_{label}_{uuid.uuid4().hex[:6]}"
        self._derived[new_id] = df.copy()
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
        claim_cap: int = MAX_CLAIMS,
    ):
        self.problem = problem
        self.world = world
        self.seed = seed
        self.n_mc = n_mc
        self._llm_call = llm_call
        self.claim_cap = claim_cap

        # Sub-questions for scoring (SQ v2 only)
        self._subquestions_v2: list[SubQuestionIntentV2] = []
        self._sq_score: EpisodeSubQuestionScore | None = None

        # Trace infrastructure
        self.trace = EpisodeTrace()
        self._step: dict[str, int] = {"current": 0}

        # Artifact management
        self.catalog = ArtifactCatalog(problem.data_assets)

        # Python namespace
        self._namespace = self._build_namespace()

        # Submission state
        self._submitted = False
        self._last_compiled: list | None = None

        # Scoring internals (for rescore / P0 persistence)
        self._claim_truths: dict[str, float] | None = None
        self._relevance_results: list[dict] | None = None
        self._judge_claims: list[dict] | None = None
        self._last_claims: list[ClaimCard] | None = None

    def _build_namespace(self) -> dict:
        """Build the solver's Python namespace with OI-specific tools.

        SECURITY: Functions are wrapped as plain closures to prevent
        solver code from reaching runner internals via __self__.
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
            parent_id = getattr(df, "_oi_artifact_id", None)
            parent_ids = [parent_id] if parent_id else []
            new_id = catalog.save_derived(df, label, parent_ids=parent_ids)
            trace.accesses.append(
                ArtifactAccess(artifact_id=new_id, step=step["current"],
                               access_type="analyze")
            )
            print(f"[save_artifact] saved as {new_id}")
            return new_id

        ns["load_artifact"] = load_artifact
        ns["save_artifact"] = save_artifact
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

        sq_context = [
            {
                "sq_id": sq.sq_id,
                "pattern": "free_text",
                "text_gloss": sq.text_gloss,
            }
            for sq in self._subquestions_v2
        ]

        return ExtractionContext(
            research_brief=self.problem.research_question,
            domain=self.problem.domain,
            description=self.problem.description,
            title=self.problem.title,
            variable_descriptions=variable_descriptions,
            sub_questions=sq_context,
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
    ) -> EpisodeSubQuestionScore:
        """Submit claims and compute the episode score.

        Transactional: ALL side effects (`_submitted`, `_last_compiled`,
        `_last_claims`, `_claim_truths`, `_relevance_results`,
        `_judge_claims`, `_sq_score`, `trace.claim_steps`) are committed
        atomically AFTER both compilation and scoring succeed. If compile
        or scoring raises (e.g. LLM timeout during judge), the runner is
        left exactly as it was before the call, so the solver can retry.

        Args:
            claims: The solver's ClaimCards (1-claim_cap claims).
            compiled_claims: Pre-compiled CompilerOutputs aligned 1:1
                with claims (same order, same claim_ids). If None,
                auto-compiles via extraction pipeline.

        Returns:
            EpisodeSubQuestionScore with correctness, coverage, total.
        """

        # --- Pre-flight validation (no mutation) ---

        if self._submitted:
            raise RuntimeError("Claims already submitted for this episode")

        logger.info(
            "submit_claims: claim_cap=%d, received=%d",
            self.claim_cap, len(claims),
        )
        if len(claims) > self.claim_cap:
            raise ValueError(
                f"Too many claims: {len(claims)} > {self.claim_cap}"
            )

        if len(claims) == 0:
            raise ValueError("Must submit at least 1 claim")

        # Check for duplicate claim_ids
        claim_ids = [c.claim_id for c in claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("Duplicate claim_ids in submission")

        # Validate evidence_basis: atomic rejection of entire submission
        # if ANY claim cites an artifact_id that was never accessed (#25).
        accessed = self.trace.accessed_artifact_ids()
        evidence_errors = validate_evidence_refs(
            claims, accessed, catalog_ids=self.catalog.all_ids,
        )
        if evidence_errors:
            detail_lines = []
            for cid, errs in evidence_errors.items():
                refs = ", ".join(
                    f"{e['artifact_id']} ({e['reason']})" for e in errs
                )
                detail_lines.append(f"  claim {cid}: {refs}")
            accessed_list = sorted(accessed) if accessed else ["(none)"]
            raise ValueError(
                "SUBMISSION REJECTED: fabricated evidence_basis references. "
                "Every artifact_id in evidence_basis must be an id you "
                "received from load_artifact() or save_artifact() during "
                "this episode.\n"
                "Invalid references:\n"
                + "\n".join(detail_lines)
                + "\n\nValid artifact IDs you accessed in this episode: "
                + ", ".join(accessed_list)
                + "\n\nFix the invalid references and resubmit."
            )

        # --- Stage compile (in locals, no mutation yet) ---
        # Compile-alignment errors (length, type, claim_id mismatch) must
        # surface here before the subquestions_v2 check — they describe the
        # caller's arguments, which is a more actionable error than a runner
        # configuration issue.

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

        if not self._subquestions_v2:
            raise RuntimeError(
                "No sub_questions_v2 provided. SQ v2 + LLM judge is the "
                "only supported scoring path. Ensure the SRC was generated "
                "with sub_questions_v2 in src.json."
            )

        # --- Stage scoring (pure; raises on LLM timeout / judge failure) ---
        # If this raises, nothing below runs, and none of the state below is
        # touched. That is the transactional invariant.

        bundle = self._score_with_judge(claims, compiled)

        # --- COMMIT: atomic mutation of runner state ---
        self._commit_scoring_result(
            compiled=compiled, claims=claims, bundle=bundle,
            record_claim_steps=True,
        )

        score = bundle[0]
        logger.info(
            "SQ v2 judge score: total=%.3f correctness=%.3f "
            "weighted_coverage=%.3f coverage=%.3f",
            score.total,
            score.correctness,
            score.weighted_coverage,
            score.coverage,
        )

        return score

    def _commit_scoring_result(
        self,
        *,
        compiled: list,
        claims: list[ClaimCard],
        bundle: tuple[
            EpisodeSubQuestionScore, dict[str, float], list[dict], list[dict]
        ],
        record_claim_steps: bool,
    ) -> None:
        """Atomically commit the result of a scoring pass.

        Single source of truth for the submit-commit invariant. Used by:
          - submit_claims (record_claim_steps=True): full lifecycle.
          - rescore pipelines (record_claim_steps=False): the rescore path
            hydrates the runner's trace from a frozen episode, so recording
            claim_steps here would either duplicate or clobber frozen state.

        All fields are written together. `_submitted` goes LAST so that a
        hypothetical exception between mutations leaves the runner
        re-submittable (the claim-already-submitted guard only trips once
        every other field is in a consistent state).
        """
        score, claim_truths, relevance_results, judge_claims = bundle
        if record_claim_steps:
            for claim in claims:
                self.trace.claim_steps[claim.claim_id] = self._step["current"]
        self._last_compiled = compiled
        self._last_claims = list(claims)
        self._claim_truths = dict(claim_truths)
        self._relevance_results = list(relevance_results)
        self._judge_claims = list(judge_claims)
        self._sq_score = score
        self._submitted = True

    def compiler_stats(self) -> dict:
        """Return compiler backend stats from last submission."""
        from sreg.tools.oi_compiler import CompilerOutput

        if not self._last_compiled:
            return {"total_claims": 0}

        stats = {
            "total_claims": 0,
            "grammar_direct": 0,
            "v1_fallback": 0,
            "abstention": 0,
            "total_specs": 0,
            "per_claim": [],
        }
        for co in self._last_compiled:
            if not isinstance(co, CompilerOutput):
                continue
            stats["total_claims"] += 1
            if co.status == "abstention":
                stats["abstention"] += 1
                stats["per_claim"].append({
                    "claim_id": co.claim_id, "backend": "abstention",
                    "n_specs": 0,
                })
                continue
            # Check backend of units
            claim_backend = "v1_fallback"
            n_specs = 0
            for u in co.units:
                n_specs += len(u.specs)
                if u.backend == "grammar_direct":
                    claim_backend = "grammar_direct"
            stats[claim_backend] += 1
            stats["total_specs"] += n_specs
            stats["per_claim"].append({
                "claim_id": co.claim_id, "backend": claim_backend,
                "n_specs": n_specs,
            })
        return stats

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

    def set_subquestions_v2(self, sqs: list[SubQuestionIntentV2]) -> None:
        """Set pre-grounded SQ v2s for LLM judge scoring.

        SQs must have verdicts already filled via ground_sq_answer_key().
        Requires llm_call in __init__ (the judge needs an LLM).
        """
        for sq in sqs:
            for vs in sq.verification_specs:
                if vs.verdict is None:
                    raise ValueError(
                        f"SQ {sq.sq_id} spec {vs.spec.spec_id} has no verdict. "
                        "SQs must be pre-grounded via ground_sq_answer_key()."
                    )
        self._subquestions_v2 = list(sqs)

    def _score_with_judge(
        self,
        claims: list[ClaimCard],
        compiled: list,
    ) -> tuple[EpisodeSubQuestionScore, dict[str, float], list[dict], list[dict]]:
        """Score claims against SQ v2s using LLM relevance judge.

        Pure function — does NOT mutate runner state. Returns the bundle
        (score, claim_truths, relevance_results, judge_claims) so that the
        caller (submit_claims) can commit all fields atomically after a
        successful scoring, or leave the runner untouched if scoring raises
        (e.g. LLM timeout). This is the transactional invariant.

        Steps:
        1. Compute truth per claim (verify compiled specs against SCM)
        2. Render answer keys from pre-grounded SQ verdicts
        3. Run LLM judge: relevance per claim x SQ pair
        4. Compute per-SQ satisfaction and episode-level scores
        """
        from sreg.tools.oi_compiler import CompilerOutput
        from sreg.tools.oi_relevance_judge import judge_all_claims
        from sreg.tools.oi_sq_compiler import render_answer_key
        from sreg.tools.oi_verifier import verify_atom

        if not self._llm_call:
            raise RuntimeError(
                "LLM judge scoring requires llm_call in OIEpisodeRunner.__init__"
            )

        # Adapt llm_call to judge protocol: (system, user) -> str
        # Runner's llm_call may use messages format (1 arg) or (system, user) format
        _raw_llm = self._llm_call

        def judge_llm(system: str, user: str) -> str:
            try:
                # Try (system, user) protocol first
                return _raw_llm(system, user)
            except TypeError:
                # Fall back to messages protocol
                return _raw_llm([
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ])

        solver = SCMSolver(self.world, n_mc=self.n_mc)

        # -- 1. Truth per claim (proportional: M/N specs that hold) --
        claim_truths: dict[str, float] = {}
        for co in compiled:
            if not isinstance(co, CompilerOutput):
                continue
            if not co.compiled:
                claim_truths[co.claim_id] = 0.0
                continue
            n_total = 0
            n_hold = 0
            for unit in co.units:
                if not unit.specs:
                    continue
                for s in unit.specs:
                    n_total += 1
                    v = verify_atom(s, self.world, solver, self.n_mc, self.seed)
                    if v.solver_assertion_holds:
                        n_hold += 1
            claim_truths[co.claim_id] = n_hold / n_total if n_total > 0 else 0.0

        # -- 1b. Validate evidence_basis against actual artifact accesses --
        # Penalty instead of zeroing: bad citations reduce truth but don't
        # destroy it. This preserves RL signal when the solver cites
        # python_exec steps or other non-artifact IDs.
        accessed = self.trace.accessed_artifact_ids()
        claims_by_id = {c.claim_id: c for c in claims}
        for claim_id in list(claim_truths.keys()):
            claim = claims_by_id.get(claim_id)
            if not claim or not claim.evidence_basis:
                continue
            cited = {ref.artifact_id for ref in claim.evidence_basis}
            fabricated = cited - accessed
            if fabricated:
                valid_ratio = 1 - len(fabricated) / len(cited)
                # All fabricated → harsh penalty; some valid → proportional
                penalty = valid_ratio if valid_ratio > 0 else 0.1
                logger.warning(
                    "Claim %s cites artifacts never accessed: %s. "
                    "Applying penalty %.2f (was %.3f -> %.3f).",
                    claim_id, sorted(fabricated), penalty,
                    claim_truths[claim_id],
                    claim_truths[claim_id] * penalty,
                )
                claim_truths[claim_id] *= penalty

        # -- 2. Build judge inputs from SQ v2s --
        judge_sqs = []
        for sq in self._subquestions_v2:
            answer_keys = []
            for vs in sq.verification_specs:
                if vs.verdict:
                    ak = render_answer_key(vs.verdict)
                    ak["role"] = vs.role
                    answer_keys.append(ak)
            judge_sqs.append({
                "sq_id": sq.sq_id,
                "text_gloss": sq.text_gloss,
                "focus_variables": list(sq.focus_variables),
                "tier": sq.tier.value,
                "answer_keys": answer_keys,
            })

        # Build judge claims from ClaimCards + compiled specs
        judge_claims = []
        for claim, co in zip(claims, compiled):
            specs_summary = []
            if isinstance(co, CompilerOutput) and co.compiled:
                for unit in co.units:
                    for s in unit.specs:
                        # Extract ALL variables from spec for pre-filter
                        spec_vars: set[str] = set()
                        m = s.measurement
                        if m:
                            if m.target:
                                targets = m.target if isinstance(m.target, tuple) else (m.target,)
                                spec_vars.update(str(t) for t in targets)
                            if m.lhs:
                                spec_vars.add(m.lhs)
                            if m.rhs:
                                spec_vars.add(m.rhs)
                            if m.treatment:
                                spec_vars.add(m.treatment)
                            if m.outcome:
                                spec_vars.add(m.outcome)
                            spec_vars.update(m.candidate_causes)
                            spec_vars.update(m.cond_set)
                        for arm in s.arms:
                            if arm.treatment:
                                spec_vars.add(arm.treatment)
                            if arm.outcome:
                                spec_vars.add(arm.outcome)
                            spec_vars.update(arm.values.keys())
                            spec_vars.update(arm.condition_on.keys())
                            if arm.sweep_var:
                                spec_vars.add(arm.sweep_var)
                        specs_summary.append({
                            "measurement_kind": m.kind.value if m else "?",
                            "comparison_kind": s.comparison.kind.value if s.comparison else "?",
                            "primary_vars": ", ".join(sorted(spec_vars)),
                        })
            judge_claims.append({
                "claim_id": claim.claim_id,
                "claim_text": claim.claim_text,
                "specs_summary": specs_summary,
            })

        # -- 3. Run LLM judge --
        # NOTE: this is the most likely point of failure (LLM timeout /
        # network error). If it raises, self._claim_truths / _relevance_results
        # / _judge_claims must remain untouched so a retry sees a pristine
        # runner. That is why persistence is deferred to submit_claims after
        # the full bundle is computed (see _score_with_judge docstring).
        relevance_results = judge_all_claims(
            claims=judge_claims,
            sqs=judge_sqs,
            brief_text=self.problem.research_question,
            llm_call=judge_llm,
        )

        # Index: (claim_id, sq_id) -> relevance
        rel_map: dict[tuple[str, str], float] = {}
        for r in relevance_results:
            rel_map[(r["claim_id"], r["sq_id"])] = r["relevance"]

        # -- 4. Compute per-SQ satisfaction and episode scores --
        sq_scores = []
        total_weight = 0.0
        weighted_sat_sum = 0.0

        for sq in self._subquestions_v2:
            best_score = 0.0
            best_claim_id = None

            for claim in claims:
                truth = claim_truths.get(claim.claim_id, 0.0)
                rel = rel_map.get((claim.claim_id, sq.sq_id), 0.0)
                score = truth * rel
                if score > best_score:
                    best_score = score
                    best_claim_id = claim.claim_id

            satisfaction = best_score
            sq_scores.append(SubQuestionScore(
                sq_id=sq.sq_id,
                satisfaction=min(1.0, satisfaction),
                best_claim_id=best_claim_id,
                matched=best_score > 0.0,
            ))

            w = sq.weight
            total_weight += w
            weighted_sat_sum += w * satisfaction

            logger.info(
                "  SQ %s [%s w=%.1f]: sat=%.3f best=%s",
                sq.sq_id, sq.tier.value, w, satisfaction,
                best_claim_id or "(none)",
            )

        weighted_coverage = weighted_sat_sum / total_weight if total_weight > 0 else 0.0

        # Correctness = mean truth of ALL claims (penalizes spam/hallucinations)
        all_truths = [claim_truths.get(c.claim_id, 0.0) for c in claims]
        correctness = sum(all_truths) / len(all_truths) if all_truths else 0.0

        # Total = correctness × weighted_coverage (both must be high)
        total = min(1.0, correctness * weighted_coverage)

        score = EpisodeSubQuestionScore(
            sq_scores=sq_scores,
            coverage=sum(1 for s in sq_scores if s.matched) / len(sq_scores) if sq_scores else 0.0,
            weighted_coverage=weighted_coverage,
            correctness=correctness,
            novel_bonus=0.0,
            total=total,
        )
        return score, claim_truths, relevance_results, judge_claims

    # -----------------------------------------------------------------
    # Results and metadata
    # -----------------------------------------------------------------

    def get_score(self) -> EpisodeSubQuestionScore | None:
        """Return the episode score, or None if not yet submitted."""
        return self._sq_score

    def get_trace(self) -> EpisodeTrace:
        """Return the full episode trace."""
        return self.trace

    def get_score_inputs(self) -> dict | None:
        """Return scoring internals for P0 rescore persistence.

        Returns None if scoring hasn't run yet. Otherwise returns a dict
        with claims, trace, compiled_claims, claim_truths, relevance_results,
        and runner_config — everything needed for controlled rescore.
        """
        if self._last_compiled is None:
            return None
        from sreg.tools.oi_compiler import CompilerOutput

        compiled_dump = []
        for co in self._last_compiled:
            if isinstance(co, CompilerOutput):
                compiled_dump.append({
                    "claim_id": co.claim_id,
                    "status": co.status,
                    "units": [
                        {
                            "unit_id": u.unit_id,
                            "backend": u.backend,
                            "specs": [s.model_dump(mode="json") for s in u.specs],
                        }
                        for u in co.units
                    ],
                    "abstention_reason": co.abstention_reason,
                    "uncompiled_fragments": co.uncompiled_fragments,
                })

        claims_dump = []
        if hasattr(self, "_last_claims") and self._last_claims:
            claims_dump = [c.model_dump(mode="json") for c in self._last_claims]

        return {
            "schema_version": 1,
            "claims": claims_dump,
            "trace": self.trace.model_dump(mode="json"),
            "compiled_claims": compiled_dump,
            "claim_truths": self._claim_truths or {},
            "relevance_results": self._relevance_results or [],
            "judge_claims": getattr(self, "_judge_claims", []),
            "runner_config": {
                "seed": self.seed,
                "n_mc": self.n_mc,
                "claim_cap": self.claim_cap,
            },
        }

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
