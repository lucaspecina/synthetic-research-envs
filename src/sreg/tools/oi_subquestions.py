"""OI Sub-Question Resolution and Scoring.

This module handles the orchestrator's hidden sub-questions:
    SubQuestionIntent -> [resolve against SCM] -> ResolvedSubQuestion
    Claims + ResolvedSubQuestions -> [matching + scoring] -> EpisodeSubQuestionScore

Resolution reuses the existing compiler lowering + verifier pipeline.
The approach is scalar-first: compute the raw effect, classify deterministically,
then build canonical specs for matching.

Design decisions (from Codex debate, thread 019d32e4):
- Sub-questions are NOT claims — they represent investigation agenda
- Resolution is deterministic (no LLM)
- Matching uses pattern + roles as primary key, with subsumption
- Multi-component SQs (mediation, confounding) use ALL_OF acceptance
- Weights come from tiers (high/medium/low), not continuous LLM values
"""

from __future__ import annotations

import logging
from typing import Any

from sreg.models.open_investigation import (
    AcceptanceRule,
    AskOperator,
    AtomicSpec,
    EpisodeSubQuestionScore,
    ResolvedAnswer,
    ResolvedSubQuestion,
    SQComponent,
    SQRoles,
    SubQuestionIntent,
    SubQuestionScore,
)
from sreg.solver.scm_solver import SCMSolver
from sreg.tools.oi_compiler import (
    ClaimIntent,
    CompilerOutput,
    Direction,
    PatternClass,
    WorldSummary,
    build_world_summary,
    lower_intent,
    validate_intent,
)
from sreg.tools.oi_verifier import verify_atom
from sreg.world.scm import SCMWorld

logger = logging.getLogger(__name__)

# Default materiality thresholds per pattern (effect_size units)
DEFAULT_THRESHOLDS: dict[str, float] = {
    "causal_effect": 0.10,
    "mediation": 0.08,
    "confounding": 0.08,
    "heterogeneity": 0.10,
    "observational_association": 0.05,
    "tail_risk": 0.10,
    "variance_effect": 0.10,
    "effect_ranking": 0.0,
}

# Subsumption weights: (claim_pattern, sq_pattern) -> weight
# Only non-zero entries listed. All others = 0.0.
SUBSUMPTION_WEIGHTS: dict[tuple[str, str], float] = {
    # mediation claim gives partial credit to causal_effect SQ
    ("mediation", "causal_effect"): 0.60,
    # heterogeneity claim gives partial credit to causal_effect SQ
    ("heterogeneity", "causal_effect"): 0.40,
    # causal_effect claim gives partial credit to mediation SQ (total effect component)
    ("causal_effect", "mediation"): 0.35,
    # causal_effect claim gives partial credit to confounding SQ
    ("causal_effect", "confounding"): 0.35,
    # obs_association claim gives partial credit to confounding SQ
    ("observational_association", "confounding"): 0.35,
    # causal_effect gives partial credit to heterogeneity SQ (base effect)
    ("causal_effect", "heterogeneity"): 0.35,
}


# ---------------------------------------------------------------------------
# Resolution: SubQuestionIntent -> ResolvedSubQuestion
# ---------------------------------------------------------------------------


def resolve_subquestion(
    sq: SubQuestionIntent,
    world: SCMWorld,
    summary: WorldSummary,
    solver: SCMSolver,
    n_mc: int = 20_000,
    seed: int = 42,
) -> ResolvedSubQuestion:
    """Resolve a sub-question deterministically against the SCM.

    Approach (scalar-first, per Codex review):
    1. Build ClaimIntent candidates for each possible direction
    2. Lower + verify each against the SCM
    3. Use scalar values to classify the answer
    4. Build canonical ResolvedSubQuestion with specs
    """
    pattern = sq.pattern
    threshold = sq.materiality_threshold or DEFAULT_THRESHOLDS.get(pattern, 0.10)

    if pattern == "effect_ranking":
        return _resolve_ranking(sq, world, summary, solver, n_mc, seed)

    if pattern in ("mediation", "confounding"):
        return _resolve_multi_component(sq, world, summary, solver, n_mc, seed, threshold)

    # Simple patterns: causal_effect, heterogeneity, obs_association, tail_risk, variance_effect
    return _resolve_simple(sq, world, summary, solver, n_mc, seed, threshold)


def resolve_all(
    sqs: list[SubQuestionIntent],
    world: SCMWorld,
    target: str | None = None,
    n_mc: int = 20_000,
    seed: int = 42,
) -> list[ResolvedSubQuestion]:
    """Resolve all sub-questions for a world in batch.

    Builds WorldSummary and SCMSolver once, shared across all SQs.
    """
    # Use first SQ's outcome as target if not specified
    effective_target = target
    if effective_target is None:
        for sq in sqs:
            if sq.roles.outcome:
                effective_target = sq.roles.outcome
                break
    if effective_target is None:
        effective_target = world.variables[0] if world.variables else "unknown"

    summary = build_world_summary(world, effective_target, n_mc=n_mc, seed=seed)
    solver = SCMSolver(world)

    results = []
    for sq in sqs:
        try:
            rsq = resolve_subquestion(sq, world, summary, solver, n_mc, seed)
            results.append(rsq)
        except Exception as e:
            logger.warning("Failed to resolve SQ %s: %s", sq.sq_id, e)
            # Create a minimal failed resolution
            results.append(ResolvedSubQuestion(
                intent=sq,
                resolved_answer=ResolvedAnswer(exists=None),
                components=[SQComponent(
                    component_id=f"{sq.sq_id}:failed",
                    pattern=sq.pattern,
                    roles=sq.roles,
                    ask=sq.ask,
                    contribution=1.0,
                    resolved_answer=ResolvedAnswer(exists=None),
                )],
                resolution_evidence={"error": str(e)},
            ))
    return results


# ---------------------------------------------------------------------------
# Validation: check sub-questions before scoring
# ---------------------------------------------------------------------------

# Patterns that require causal semantics — reject in observational_only regime
_CAUSAL_PATTERNS = {"causal_effect", "mediation", "heterogeneity", "tail_risk"}

# Patterns allowed in observational_only regime
_OBS_PATTERNS = {"observational_association", "confounding", "effect_ranking"}

# Required roles per pattern
_REQUIRED_ROLES: dict[str, set[str]] = {
    "causal_effect": {"treatment", "outcome"},
    "mediation": {"treatment", "mediator", "outcome"},
    "confounding": {"treatment", "outcome", "confounder"},
    "heterogeneity": {"treatment", "modifier", "outcome"},
    "observational_association": {"treatment", "outcome"},
    "tail_risk": {"treatment", "outcome"},
    "effect_ranking": {"outcome"},  # ranking_vars also needed, checked separately
}

# Valid epistemic regimes
_VALID_REGIMES = {"observational_only", "experimental", "mixed"}


def validate_sub_questions(
    sqs: list[SubQuestionIntent],
    world: SCMWorld,
    epistemic_regime: str = "observational_only",
) -> tuple[list[SubQuestionIntent], list[dict]]:
    """Validate sub-questions structurally against a world.

    Returns (accepted_sqs, errors) where errors is a list of
    {"sq_id": ..., "reasons": [...], "severity": "hard"|"soft"} dicts.

    Hard errors = SQ must be fixed or removed. Soft = advisory (LLM can keep).
    Does NOT resolve against SCM (that's expensive; done at scoring time).
    """
    errors: list[dict] = []
    accepted: list[SubQuestionIntent] = []
    world_vars = set(world.variables)
    obs_vars = set(world.observable_variables)
    valid_patterns = {p.value for p in PatternClass}

    for sq in sqs:
        sq_errors: list[str] = []

        # 1. Pattern exists
        if sq.pattern not in valid_patterns:
            sq_errors.append(
                f"Unknown pattern '{sq.pattern}'. "
                f"Valid: {sorted(valid_patterns)}"
            )

        # 2. Variable grounding — all role vars exist and are observable
        for var in sq.roles.focus_variables:
            if var not in world_vars:
                sq_errors.append(
                    f"Variable '{var}' not in world. "
                    f"Available: {sorted(world_vars)}"
                )
            elif var not in obs_vars:
                sq_errors.append(
                    f"Variable '{var}' is latent (not observable). "
                    f"SQ roles must use observable variables. "
                    f"Observable: {sorted(obs_vars)}"
                )

        # 3. Pattern-role consistency
        required = _REQUIRED_ROLES.get(sq.pattern, set())
        roles_dict = sq.roles.model_dump(exclude_none=True, exclude_defaults=True)
        # Remove ranking_vars and conditioning_set (list fields)
        present_roles = {
            k for k, v in roles_dict.items()
            if k not in ("ranking_vars", "conditioning_set") and v
        }
        missing = required - present_roles
        if missing:
            sq_errors.append(
                f"Pattern '{sq.pattern}' requires roles: {sorted(required)}, "
                f"missing: {sorted(missing)}"
            )

        # effect_ranking needs ranking_vars with 2+ vars
        if sq.pattern == "effect_ranking":
            if len(sq.roles.ranking_vars) < 2:
                sq_errors.append(
                    "effect_ranking requires ranking_vars with at least 2 variables"
                )

        # 4. Epistemological check
        if epistemic_regime in _VALID_REGIMES:
            if (
                epistemic_regime == "observational_only"
                and sq.pattern in _CAUSAL_PATTERNS
            ):
                sq_errors.append(
                    f"Pattern '{sq.pattern}' requires causal evidence, "
                    f"but epistemic_regime is 'observational_only'. "
                    f"Use observational patterns: {sorted(_OBS_PATTERNS)}"
                )

        # 5. Ask operator compatibility with pattern
        if sq.pattern == "effect_ranking" and sq.ask != AskOperator.RANK_ORDER:
            sq_errors.append(
                f"effect_ranking pattern requires ask=RANK_ORDER, got {sq.ask}"
            )

        if sq_errors:
            errors.append({
                "sq_id": sq.sq_id,
                "reasons": sq_errors,
                "severity": "hard",
            })
        else:
            accepted.append(sq)

    # Portfolio checks (soft errors, applied to full list)
    _check_portfolio(sqs, errors)

    return accepted, errors


def _check_portfolio(
    sqs: list[SubQuestionIntent], errors: list[dict]
) -> None:
    """Portfolio-level soft checks: count, diversity, near_zero cap."""
    # Count
    if len(sqs) < 3:
        errors.append({
            "sq_id": "_portfolio",
            "reasons": [f"Too few sub-questions ({len(sqs)}). Minimum 3."],
            "severity": "soft",
        })
    if len(sqs) > 7:
        errors.append({
            "sq_id": "_portfolio",
            "reasons": [f"Too many sub-questions ({len(sqs)}). Maximum 7."],
            "severity": "soft",
        })

    # Diversity: at least 2 distinct patterns
    patterns = {sq.pattern for sq in sqs}
    if len(sqs) >= 3 and len(patterns) < 2:
        errors.append({
            "sq_id": "_portfolio",
            "reasons": [
                f"Low pattern diversity: only '{patterns.pop()}'. "
                f"Use at least 2 distinct patterns."
            ],
            "severity": "soft",
        })

    # Duplicate check: same pattern + same directional role signature
    # Use (pattern, treatment, outcome, mediator, modifier, confounder) as key
    # so causal_effect(A→B) != causal_effect(B→A)
    seen: set[tuple] = set()
    for sq in sqs:
        r = sq.roles
        key = (
            sq.pattern, r.treatment, r.outcome,
            r.mediator, r.modifier, r.confounder,
            tuple(sorted(r.ranking_vars)),
        )
        if key in seen:
            errors.append({
                "sq_id": sq.sq_id,
                "reasons": [
                    f"Duplicate SQ: same pattern '{sq.pattern}' "
                    f"and roles {sorted(sq.roles.focus_variables)}"
                ],
                "severity": "hard",
            })
        seen.add(key)

    # Tier distribution: at least 1 HIGH
    tiers = [sq.tier.value for sq in sqs]
    if "high" not in tiers and len(sqs) >= 2:
        errors.append({
            "sq_id": "_portfolio",
            "reasons": ["No HIGH-tier sub-question. At least 1 required."],
            "severity": "soft",
        })


def _resolve_simple(
    sq: SubQuestionIntent,
    world: SCMWorld,
    summary: WorldSummary,
    solver: SCMSolver,
    n_mc: int,
    seed: int,
    threshold: float,
) -> ResolvedSubQuestion:
    """Resolve simple patterns (one component, three candidate directions)."""
    roles = sq.roles
    candidates = _build_directional_candidates(sq, roles)

    # Lower + verify all candidates
    best_scalar: float | None = None
    best_specs: list[AtomicSpec] = []
    all_evidence: dict[str, Any] = {}
    is_heterogeneity = sq.pattern == "heterogeneity"

    for direction_str, intent in candidates:
        errors = validate_intent(intent, summary)
        if errors:
            all_evidence[f"validation_errors_{direction_str}"] = errors
            continue

        result = lower_intent(intent, summary)
        if result.status != "compiled" or not result.specs:
            continue

        # For heterogeneity: use interaction spec (index 1), not ATE (index 0)
        # Heterogeneity lowering produces [ATE_spec, interaction_spec]
        classify_idx = 1 if (is_heterogeneity and len(result.specs) >= 2) else 0

        # Verify each spec
        for i, spec in enumerate(result.specs):
            verdict = verify_atom(spec, world, solver, n_mc, seed)
            scalar = (
                verdict.ground_truth
                if isinstance(verdict.ground_truth, (int, float))
                else 0.0
            )

            # Use the classification spec for scalar-first resolution
            if i == classify_idx:
                if best_scalar is None or abs(scalar) > abs(best_scalar):
                    best_scalar = scalar
                    best_specs = list(result.specs)

            all_evidence[f"scalar_{direction_str}_{spec.spec_id}"] = scalar
            all_evidence[f"holds_{direction_str}_{spec.spec_id}"] = verdict.solver_assertion_holds

    # Scalar-first classification
    if best_scalar is None:
        best_scalar = 0.0

    if roles.outcome:
        effect_size = abs(best_scalar) / max(summary.anchors(roles.outcome).std, 1e-6)
    else:
        effect_size = abs(best_scalar)
    all_evidence["raw_scalar"] = best_scalar
    all_evidence["effect_size"] = effect_size

    answer = _classify_scalar(best_scalar, effect_size, threshold)

    component = SQComponent(
        component_id=f"{sq.sq_id}:main",
        pattern=sq.pattern,
        roles=roles,
        ask=sq.ask,
        contribution=1.0,
        resolved_answer=answer,
        resolved_specs=best_specs,
    )

    return ResolvedSubQuestion(
        intent=sq,
        resolved_answer=answer,
        components=[component],
        acceptance_rule=AcceptanceRule.ANY_OF,
        resolution_evidence=all_evidence,
    )


def _resolve_multi_component(
    sq: SubQuestionIntent,
    world: SCMWorld,
    summary: WorldSummary,
    solver: SCMSolver,
    n_mc: int,
    seed: int,
    threshold: float,
) -> ResolvedSubQuestion:
    """Resolve mediation and confounding (multi-component SQs)."""
    roles = sq.roles
    pattern = sq.pattern
    evidence: dict[str, Any] = {}
    components: list[SQComponent] = []

    if pattern == "mediation":
        # Component 1: indirect effect (the mediation itself)
        med_intent = ClaimIntent(
            claim_id=f"{sq.sq_id}:indirect",
            pattern=PatternClass.MEDIATION,
            treatment=roles.treatment or "",
            outcome=roles.outcome or "",
            mediator=roles.mediator,
            direction=Direction.POSITIVE,
        )
        med_result, med_scalar, med_specs = _try_lower_verify(
            med_intent, summary, world, solver, n_mc, seed,
        )
        # Mediation lowering produces 2 specs: total effect + contrast_diff
        # The contrast_diff (spec[1]) measures the indirect effect
        indirect_scalar = med_scalar
        if med_result and len(med_result.specs) >= 2:
            v1 = verify_atom(med_result.specs[1], world, solver, n_mc, seed)
            indirect_scalar = (
                v1.ground_truth if isinstance(v1.ground_truth, (int, float)) else 0.0
            )

        if roles.outcome:
            outcome_std = max(summary.anchors(roles.outcome).std, 1e-6)
            indirect_es = abs(indirect_scalar) / outcome_std
        else:
            indirect_es = abs(indirect_scalar)
        indirect_answer = _classify_scalar(indirect_scalar, indirect_es, threshold)
        evidence["indirect_effect"] = indirect_scalar
        evidence["indirect_effect_size"] = indirect_es

        components.append(SQComponent(
            component_id=f"{sq.sq_id}:indirect",
            pattern="mediation",
            roles=roles,
            ask=sq.ask,
            contribution=0.7,
            resolved_answer=indirect_answer,
            resolved_specs=list(med_result.specs) if med_result else [],
        ))

        # Component 2: total effect (treatment -> outcome)
        total_intent = ClaimIntent(
            claim_id=f"{sq.sq_id}:total",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment=roles.treatment or "",
            outcome=roles.outcome or "",
            direction=Direction.POSITIVE,
        )
        total_result, total_scalar, total_specs = _try_lower_verify(
            total_intent, summary, world, solver, n_mc, seed,
        )
        if roles.outcome:
            total_es = abs(total_scalar) / max(summary.anchors(roles.outcome).std, 1e-6)
        else:
            total_es = abs(total_scalar)
        total_answer = _classify_scalar(total_scalar, total_es, threshold)
        evidence["total_effect"] = total_scalar
        evidence["total_effect_size"] = total_es

        components.append(SQComponent(
            component_id=f"{sq.sq_id}:total",
            pattern="causal_effect",
            roles=SQRoles(treatment=roles.treatment, outcome=roles.outcome),
            ask=AskOperator.EXISTENCE,
            contribution=0.3,
            resolved_answer=total_answer,
            resolved_specs=list(total_result.specs) if total_result else [],
        ))

        # Overall answer: mediation exists if indirect effect is material
        overall = indirect_answer

    elif pattern == "confounding":
        # Component 1: causal effect (the "true" relationship)
        causal_intent = ClaimIntent(
            claim_id=f"{sq.sq_id}:causal",
            pattern=PatternClass.CONFOUNDING,
            treatment=roles.treatment or "",
            outcome=roles.outcome or "",
            confounder=roles.confounder,
            direction=Direction.POSITIVE,
        )
        causal_result, _, _ = _try_lower_verify(
            causal_intent, summary, world, solver, n_mc, seed,
        )
        # Confounding lowering produces 2 specs: ATE + confounding bias
        causal_scalar = 0.0
        bias_scalar = 0.0
        if causal_result and causal_result.specs:
            v0 = verify_atom(causal_result.specs[0], world, solver, n_mc, seed)
            causal_scalar = v0.ground_truth if isinstance(v0.ground_truth, (int, float)) else 0.0
        if causal_result and len(causal_result.specs) >= 2:
            v1 = verify_atom(causal_result.specs[1], world, solver, n_mc, seed)
            bias_scalar = v1.ground_truth if isinstance(v1.ground_truth, (int, float)) else 0.0

        evidence["causal_effect"] = causal_scalar
        evidence["confounding_bias"] = bias_scalar

        bias_es = abs(bias_scalar)
        bias_answer = ResolvedAnswer(
            exists=(bias_es >= threshold),
            direction=(
                "positive" if bias_scalar > 0
                else "negative" if bias_scalar < 0
                else "near_zero"
            ),
            magnitude=bias_scalar,
            effect_size=bias_es,
        )

        components.append(SQComponent(
            component_id=f"{sq.sq_id}:bias",
            pattern="confounding",
            roles=roles,
            ask=sq.ask,
            contribution=0.6,
            resolved_answer=bias_answer,
            resolved_specs=list(causal_result.specs) if causal_result else [],
        ))

        # Component 2: the adjusted causal effect
        if roles.outcome:
            ce_es = abs(causal_scalar) / max(summary.anchors(roles.outcome).std, 1e-6)
        else:
            ce_es = abs(causal_scalar)
        ce_answer = _classify_scalar(causal_scalar, ce_es, threshold)
        components.append(SQComponent(
            component_id=f"{sq.sq_id}:causal",
            pattern="causal_effect",
            roles=SQRoles(treatment=roles.treatment, outcome=roles.outcome),
            ask=AskOperator.EXISTENCE,
            contribution=0.4,
            resolved_answer=ce_answer,
        ))

        overall = bias_answer
    else:
        raise ValueError(f"Unexpected multi-component pattern: {pattern}")

    return ResolvedSubQuestion(
        intent=sq,
        resolved_answer=overall,
        components=components,
        acceptance_rule=AcceptanceRule.ALL_OF,
        resolution_evidence=evidence,
    )


def _resolve_ranking(
    sq: SubQuestionIntent,
    world: SCMWorld,
    summary: WorldSummary,
    solver: SCMSolver,
    n_mc: int,
    seed: int,
) -> ResolvedSubQuestion:
    """Resolve effect_ranking by computing ATE for each candidate variable."""
    roles = sq.roles
    outcome = roles.outcome or ""
    candidates = list(roles.ranking_vars)
    evidence: dict[str, Any] = {}

    scalars: dict[str, float] = {}
    for var in candidates:
        intent = ClaimIntent(
            claim_id=f"{sq.sq_id}:rank_{var}",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment=var,
            outcome=outcome,
            direction=Direction.POSITIVE,
        )
        _, scalar, _ = _try_lower_verify(intent, summary, world, solver, n_mc, seed)
        scalars[var] = abs(scalar)
        evidence[f"ate_{var}"] = scalar

    # Sort by absolute effect size
    rank_order = tuple(sorted(scalars, key=lambda v: scalars[v], reverse=True))
    evidence["rank_order"] = rank_order

    answer = ResolvedAnswer(
        exists=True,
        rank_order=rank_order,
    )

    component = SQComponent(
        component_id=f"{sq.sq_id}:ranking",
        pattern="effect_ranking",
        roles=roles,
        ask=sq.ask,
        contribution=1.0,
        resolved_answer=answer,
    )

    return ResolvedSubQuestion(
        intent=sq,
        resolved_answer=answer,
        components=[component],
        acceptance_rule=AcceptanceRule.ANY_OF,
        resolution_evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_directional_candidates(
    sq: SubQuestionIntent, roles: SQRoles,
) -> list[tuple[str, ClaimIntent]]:
    """Build ClaimIntent candidates for each possible direction."""
    pattern = PatternClass(sq.pattern)
    base_kwargs: dict[str, Any] = {
        "pattern": pattern,
        "treatment": roles.treatment or "",
        "outcome": roles.outcome or "",
    }
    if roles.mediator:
        base_kwargs["mediator"] = roles.mediator
    if roles.modifier:
        base_kwargs["modifier"] = roles.modifier
    if roles.confounder:
        base_kwargs["confounder"] = roles.confounder

    candidates = []
    for d in [Direction.POSITIVE, Direction.NEGATIVE, Direction.NEAR_ZERO]:
        intent = ClaimIntent(
            claim_id=f"{sq.sq_id}:candidate_{d.value}",
            direction=d,
            **base_kwargs,
        )
        candidates.append((d.value, intent))
    return candidates


def _try_lower_verify(
    intent: ClaimIntent,
    summary: WorldSummary,
    world: SCMWorld,
    solver: SCMSolver,
    n_mc: int,
    seed: int,
) -> tuple[CompilerOutput | None, float, list[AtomicSpec]]:
    """Try to lower + verify an intent. Returns (result, first_scalar, specs)."""
    errors = validate_intent(intent, summary)
    if errors:
        return None, 0.0, []

    result = lower_intent(intent, summary)
    if result.status != "compiled" or not result.specs:
        return None, 0.0, []

    # Verify first spec for scalar
    verdict = verify_atom(result.specs[0], world, solver, n_mc, seed)
    scalar = verdict.ground_truth if isinstance(verdict.ground_truth, (int, float)) else 0.0

    return result, scalar, list(result.specs)


def _classify_scalar(
    scalar: float, effect_size: float, threshold: float,
) -> ResolvedAnswer:
    """Classify a scalar value into direction + existence (scalar-first)."""
    if effect_size < threshold:
        return ResolvedAnswer(
            exists=False,
            direction="near_zero",
            magnitude=scalar,
            effect_size=effect_size,
        )
    elif scalar > 0:
        return ResolvedAnswer(
            exists=True,
            direction="positive",
            magnitude=scalar,
            effect_size=effect_size,
        )
    else:
        return ResolvedAnswer(
            exists=True,
            direction="negative",
            magnitude=scalar,
            effect_size=effect_size,
        )


# ---------------------------------------------------------------------------
# Matching + Scoring: Claims vs Sub-Questions
# ---------------------------------------------------------------------------


def score_claim_vs_subquestion(
    claim: ClaimIntent,
    claim_truth: float,
    resolved_sq: ResolvedSubQuestion,
) -> float:
    """Score how well one claim satisfies one resolved sub-question.

    Args:
        claim: The compiled ClaimIntent.
        claim_truth: Pre-computed truth score (0..1) from SCM verification.
        resolved_sq: The resolved sub-question.

    Returns:
        Score in [0, 1].
    """
    if claim_truth == 0.0:
        return 0.0

    sq = resolved_sq.intent

    # Try direct match at SQ level
    if _exact_pattern_roles_match(claim, sq):
        answer_compat = _answer_compatibility(claim, resolved_sq.resolved_answer, sq.ask)
        if answer_compat > 0:
            return claim_truth * answer_compat

    # Try component-level match
    best = 0.0
    for comp in resolved_sq.components:
        # Exact match with component
        comp_sq = SubQuestionIntent(
            sq_id=comp.component_id, pattern=comp.pattern,
            roles=comp.roles, ask=comp.ask,
        )
        if _exact_pattern_roles_match(claim, comp_sq):
            answer_compat = _answer_compatibility(claim, comp.resolved_answer, comp.ask)
            score = claim_truth * answer_compat * comp.contribution
            best = max(best, score)
            continue

        # Subsumption match
        sub_w = SUBSUMPTION_WEIGHTS.get((claim.pattern.value, comp.pattern), 0.0)
        if sub_w == 0.0:
            continue
        if not _roles_compatible_subsumption(claim, comp):
            continue

        answer_compat = _answer_compatibility(claim, comp.resolved_answer, comp.ask)
        score = claim_truth * sub_w * answer_compat * comp.contribution
        best = max(best, score)

    return best


def score_episode_with_subquestions(
    compiled_claims: list[tuple[ClaimIntent, float]],
    resolved_sqs: list[ResolvedSubQuestion],
    novel_cap: float = 0.20,
) -> EpisodeSubQuestionScore:
    """Score an episode's claims against resolved sub-questions.

    Args:
        compiled_claims: List of (ClaimIntent, truth_score) tuples.
        resolved_sqs: All resolved sub-questions for this episode.
        novel_cap: Maximum bonus for novel findings (outside all SQs).

    Returns:
        EpisodeSubQuestionScore with detailed per-SQ results.
    """
    sq_scores: list[SubQuestionScore] = []
    claim_used_for_sq: dict[str, str] = {}  # claim_id -> sq_id that used it best

    for rsq in resolved_sqs:
        if rsq.acceptance_rule == AcceptanceRule.ANY_OF:
            # Take the best claim
            best_score = 0.0
            best_claim_id = None
            for claim, truth in compiled_claims:
                s = score_claim_vs_subquestion(claim, truth, rsq)
                if s > best_score:
                    best_score = s
                    best_claim_id = claim.claim_id
            sq_scores.append(SubQuestionScore(
                sq_id=rsq.intent.sq_id,
                satisfaction=best_score,
                best_claim_id=best_claim_id,
                matched=best_score > 0.0,
            ))
            if best_claim_id:
                claim_used_for_sq[best_claim_id] = rsq.intent.sq_id

        elif rsq.acceptance_rule == AcceptanceRule.ALL_OF:
            # Per-component: each component takes its best claim
            comp_scores: dict[str, float] = {}
            best_claim_for_allof: str | None = None
            best_allof_score = 0.0
            for comp in rsq.components:
                best_comp = 0.0
                best_comp_claim: str | None = None
                # Build a component-level intent (not the parent SQ intent)
                comp_intent = SubQuestionIntent(
                    sq_id=comp.component_id,
                    pattern=comp.pattern,
                    roles=comp.roles,
                    ask=comp.ask,
                )
                for claim, truth in compiled_claims:
                    temp_rsq = ResolvedSubQuestion(
                        intent=comp_intent,
                        resolved_answer=comp.resolved_answer,
                        components=[comp],
                        acceptance_rule=AcceptanceRule.ANY_OF,
                    )
                    s = score_claim_vs_subquestion(claim, truth, temp_rsq)
                    if s > best_comp:
                        best_comp = s
                        best_comp_claim = claim.claim_id
                comp_scores[comp.component_id] = best_comp
                if best_comp > best_allof_score and best_comp_claim:
                    best_allof_score = best_comp
                    best_claim_for_allof = best_comp_claim

            # Weighted sum of component scores
            total_contribution = sum(c.contribution for c in rsq.components)
            if total_contribution > 0:
                satisfaction = sum(
                    comp_scores.get(c.component_id, 0.0) * c.contribution
                    for c in rsq.components
                ) / total_contribution
            else:
                satisfaction = 0.0

            sq_scores.append(SubQuestionScore(
                sq_id=rsq.intent.sq_id,
                satisfaction=satisfaction,
                best_claim_id=best_claim_for_allof,
                component_scores=comp_scores,
                matched=satisfaction > 0.0,
            ))
            # Track claims used by ALL_OF SQs for correctness
            if best_claim_for_allof:
                claim_used_for_sq[best_claim_for_allof] = rsq.intent.sq_id

    # Coverage: fraction of SQs with any satisfaction
    n_matched = sum(1 for s in sq_scores if s.matched)
    coverage = n_matched / len(sq_scores) if sq_scores else 0.0

    # Weighted coverage: weight-adjusted
    total_weight = sum(rsq.intent.weight for rsq in resolved_sqs)
    weighted_sum = sum(
        sq_scores[i].satisfaction * resolved_sqs[i].intent.weight
        for i in range(len(sq_scores))
    )
    weighted_coverage = weighted_sum / total_weight if total_weight > 0 else 0.0

    # Correctness: mean truth of claims that matched any SQ
    matched_truths = [truth for claim, truth in compiled_claims
                      if claim.claim_id in claim_used_for_sq]
    correctness = sum(matched_truths) / len(matched_truths) if matched_truths else 0.0

    # Novel bonus: true claims not matched to any SQ
    novel_scores: list[float] = []
    for claim, truth in compiled_claims:
        if truth > 0.0 and claim.claim_id not in claim_used_for_sq:
            # Check it didn't match ANY SQ at all
            any_match = any(
                score_claim_vs_subquestion(claim, truth, rsq) > 0.0
                for rsq in resolved_sqs
            )
            if not any_match:
                novel_scores.append(truth)
    novel_bonus = min(
        sum(novel_scores) / max(len(compiled_claims), 1) * 0.5,
        novel_cap,
    ) if novel_scores else 0.0

    # Total score
    total = min(1.0, weighted_coverage * 0.70 + correctness * 0.20 + novel_bonus + coverage * 0.10)

    return EpisodeSubQuestionScore(
        sq_scores=sq_scores,
        coverage=coverage,
        weighted_coverage=weighted_coverage,
        correctness=correctness,
        novel_bonus=novel_bonus,
        total=total,
    )


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------


def _exact_pattern_roles_match(claim: ClaimIntent, sq: SubQuestionIntent) -> bool:
    """Check if claim pattern + roles exactly match the sub-question."""
    if claim.pattern.value != sq.pattern:
        return False

    sr = sq.roles
    if sr.treatment and claim.treatment != sr.treatment:
        return False
    if sr.outcome and claim.outcome != sr.outcome:
        return False
    if sr.mediator and claim.mediator != sr.mediator:
        return False
    if sr.modifier and claim.modifier != sr.modifier:
        return False
    if sr.confounder and claim.confounder != sr.confounder:
        return False
    # Effect ranking: candidate set must match
    if sr.ranking_vars and set(claim.ranking_vars) != set(sr.ranking_vars):
        return False
    # Conditioning set: must match if specified
    if sr.conditioning_set and set(claim.conditioning_set) != set(sr.conditioning_set):
        return False
    return True


def _roles_compatible_subsumption(claim: ClaimIntent, comp: SQComponent) -> bool:
    """Check if claim roles are compatible under subsumption.

    More lenient than exact match but still checks key roles.
    Confounder/mediator/modifier must match if specified in component.
    """
    cr = comp.roles
    # Treatment and outcome must match if both specified
    if cr.treatment and claim.treatment and claim.treatment != cr.treatment:
        return False
    if cr.outcome and claim.outcome and claim.outcome != cr.outcome:
        return False
    # Confounder must match if component specifies one
    if cr.confounder and claim.confounder and claim.confounder != cr.confounder:
        return False
    # Mediator must match if component specifies one
    if cr.mediator and claim.mediator and claim.mediator != cr.mediator:
        return False
    return True


def _answer_compatibility(
    claim: ClaimIntent, answer: ResolvedAnswer, ask: AskOperator,
) -> float:
    """Check if the claim's direction is compatible with the resolved answer.

    Returns 1.0 for exact match, 0.8 for compatible, 0.0 for contradiction.
    """
    # Ranking: check order concordance if available
    if ask == AskOperator.RANK_ORDER and answer.rank_order:
        claim_order = tuple(claim.ranking_vars) if claim.ranking_vars else ()
        if not claim_order:
            return 0.5  # No order specified
        if claim_order == answer.rank_order:
            return 1.0  # Exact order match
        # Partial: pairwise concordance
        pairs_correct = 0
        pairs_total = 0
        for i, a in enumerate(answer.rank_order):
            for b in answer.rank_order[i + 1:]:
                pairs_total += 1
                if a in claim_order and b in claim_order:
                    if claim_order.index(a) < claim_order.index(b):
                        pairs_correct += 1
        if pairs_total > 0:
            return pairs_correct / pairs_total
        return 0.5

    if answer.direction is None:
        return 1.0  # No direction to check

    claim_dir = claim.direction.value

    if ask in (AskOperator.EXISTENCE, AskOperator.MAGNITUDE, AskOperator.RANK_ORDER):
        # Existence: any direction claim about a real effect is compatible
        if answer.exists:
            return 1.0 if claim_dir != "near_zero" else 0.0
        else:
            return 1.0 if claim_dir == "near_zero" else 0.0

    if ask in (AskOperator.SIGN, AskOperator.EXISTENCE_AND_SIGN):
        if claim_dir == answer.direction:
            return 1.0
        # Claiming positive when answer is negative = contradiction
        if claim_dir in ("positive", "negative") and answer.direction in ("positive", "negative"):
            if claim_dir != answer.direction:
                return 0.0
        # Claiming near_zero for a real effect = partial miss
        if claim_dir == "near_zero" and answer.exists:
            return 0.0
        # Claiming positive/negative for near_zero = wrong
        if answer.direction == "near_zero" and claim_dir != "near_zero":
            return 0.0
        return 0.8  # Other partial matches

    return 1.0


__all__ = [
    "resolve_subquestion",
    "resolve_all",
    "score_claim_vs_subquestion",
    "score_episode_with_subquestions",
    "DEFAULT_THRESHOLDS",
    "SUBSUMPTION_WEIGHTS",
]
