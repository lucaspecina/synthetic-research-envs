"""Exemplar bank for the OI Compiler: hand-crafted (claim_text → ClaimIntent) pairs.

These are used as few-shot examples for the LLM extraction step:
    ClaimCard → [LLM with exemplars] → ClaimIntent

Design principles:
- Static, hand-crafted (not auto-generated — avoids inheriting salience map quirks)
- Cover all 7 pattern types + negative examples
- Include diverse phrasings for each pattern
- Negative examples: claims that should produce abstention

Source: Codex review recommended hand-crafted exemplars first, then
auto-generated for coverage expansion with human review.
"""

from __future__ import annotations

from sreg.tools.oi_compiler import ClaimIntent, Direction, PatternClass

# ---------------------------------------------------------------------------
# Positive exemplars: claim text + correct ClaimIntent
# ---------------------------------------------------------------------------

POSITIVE_EXEMPLARS: list[tuple[str, ClaimIntent]] = [
    # --- CAUSAL EFFECT (3 phrasings) ---
    (
        "Increasing A leads to higher Y values",
        ClaimIntent(
            claim_id="ex_ce_1",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment="A",
            outcome="Y",
            direction=Direction.POSITIVE,
        ),
    ),
    (
        "A has a negative causal effect on Y: raising A reduces Y",
        ClaimIntent(
            claim_id="ex_ce_2",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment="A",
            outcome="Y",
            direction=Direction.NEGATIVE,
        ),
    ),
    (
        "There is no meaningful causal relationship between X and Y",
        ClaimIntent(
            claim_id="ex_ce_3",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment="X",
            outcome="Y",
            direction=Direction.NEAR_ZERO,
        ),
    ),
    # --- MEDIATION (2 phrasings) ---
    (
        "A affects Y partly through M: the indirect pathway via M accounts for "
        "a substantial portion of the total effect",
        ClaimIntent(
            claim_id="ex_med_1",
            pattern=PatternClass.MEDIATION,
            treatment="A",
            outcome="Y",
            mediator="M",
            direction=Direction.POSITIVE,
        ),
    ),
    (
        "The effect of temperature on yield is mediated by soil_moisture",
        ClaimIntent(
            claim_id="ex_med_2",
            pattern=PatternClass.MEDIATION,
            treatment="temperature",
            outcome="yield",
            mediator="soil_moisture",
            direction=Direction.POSITIVE,
        ),
    ),
    # --- HETEROGENEITY (2 phrasings) ---
    (
        "The effect of A on Y depends on the level of Z: at high Z the effect "
        "is stronger than at low Z",
        ClaimIntent(
            claim_id="ex_het_1",
            pattern=PatternClass.HETEROGENEITY,
            treatment="A",
            outcome="Y",
            modifier="Z",
            direction=Direction.POSITIVE,
        ),
    ),
    (
        "Treatment effectiveness varies by patient age: older patients benefit "
        "more from the intervention on recovery_time",
        ClaimIntent(
            claim_id="ex_het_2",
            pattern=PatternClass.HETEROGENEITY,
            treatment="treatment",
            outcome="recovery_time",
            modifier="age",
            direction=Direction.NEGATIVE,
        ),
    ),
    # --- TAIL RISK (2 phrasings) ---
    (
        "High levels of A increase the probability of extreme Y outcomes "
        "(above the 90th percentile)",
        ClaimIntent(
            claim_id="ex_tail_1",
            pattern=PatternClass.TAIL_RISK,
            treatment="A",
            outcome="Y",
            direction=Direction.POSITIVE,
        ),
    ),
    (
        "Elevated pollution exposure raises the risk of severe health outcomes",
        ClaimIntent(
            claim_id="ex_tail_2",
            pattern=PatternClass.TAIL_RISK,
            treatment="pollution",
            outcome="health",
            direction=Direction.POSITIVE,
        ),
    ),
    # --- VARIANCE EFFECT (1 phrasing) ---
    (
        "Intervening on A not only shifts the mean of Y but also increases "
        "its variability — outcomes become more unpredictable",
        ClaimIntent(
            claim_id="ex_var_1",
            pattern=PatternClass.VARIANCE_EFFECT,
            treatment="A",
            outcome="Y",
            direction=Direction.POSITIVE,
        ),
    ),
    # --- OBSERVATIONAL ASSOCIATION (2 phrasings) ---
    (
        "A and Y are positively correlated even after controlling for C",
        ClaimIntent(
            claim_id="ex_obs_1",
            pattern=PatternClass.OBSERVATIONAL_ASSOCIATION,
            treatment="A",
            outcome="Y",
            conditioning_set=["C"],
            direction=Direction.POSITIVE,
            evidence_type="observational",
        ),
    ),
    (
        "In the data, education and income show a strong positive association "
        "after adjusting for region and age",
        ClaimIntent(
            claim_id="ex_obs_2",
            pattern=PatternClass.OBSERVATIONAL_ASSOCIATION,
            treatment="education",
            outcome="income",
            conditioning_set=["region", "age"],
            direction=Direction.POSITIVE,
            evidence_type="observational",
        ),
    ),
    # --- SIGN vs SIGNIFICANCE: slope sign matters, not p-value ---
    (
        "Wind is weakly related to pollution (slope = -3.83, p = 0.32), "
        "suggesting a non-significant but directionally negative relationship",
        ClaimIntent(
            claim_id="ex_obs_sign",
            pattern=PatternClass.OBSERVATIONAL_ASSOCIATION,
            treatment="Wind",
            outcome="pollution",
            direction=Direction.NEGATIVE,  # slope is -3.83 → NEGATIVE, despite p > 0.05
            evidence_type="observational",
        ),
    ),
    # --- NULL EFFECT / NEAR_ZERO (2 phrasings) ---
    (
        "There is no significant interaction between Depth and Algae on Fish",
        ClaimIntent(
            claim_id="ex_nz_1",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment="Depth",
            outcome="Fish",
            direction=Direction.NEAR_ZERO,
        ),
    ),
    (
        "The effect of Education on Income is negligible after controlling for Skill",
        ClaimIntent(
            claim_id="ex_nz_2",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment="Education",
            outcome="Income",
            direction=Direction.NEAR_ZERO,
        ),
    ),
    # --- CONFOUNDING (2 phrasings) ---
    (
        "Severity confounds the relationship between Treatment and Recovery: "
        "without adjusting for Severity, the treatment effect appears weaker",
        ClaimIntent(
            claim_id="ex_conf_1",
            pattern=PatternClass.CONFOUNDING,
            treatment="Treatment",
            outcome="Recovery",
            confounder="Severity",
            direction=Direction.POSITIVE,
        ),
    ),
    (
        "Wealth is a confounder of the Education-Income relationship: part of the "
        "apparent effect of Education on Income is due to Wealth influencing both",
        ClaimIntent(
            claim_id="ex_conf_2",
            pattern=PatternClass.CONFOUNDING,
            treatment="Education",
            outcome="Income",
            confounder="Wealth",
            direction=Direction.POSITIVE,
        ),
    ),
    # --- EFFECT RANKING (2 phrasings) ---
    (
        "Among all factors studied, A has the strongest causal effect on Y, "
        "followed by C and then Z",
        ClaimIntent(
            claim_id="ex_rank_1",
            pattern=PatternClass.EFFECT_RANKING,
            treatment="A",
            outcome="Y",
            ranking_vars=["A", "C", "Z"],
        ),
    ),
    (
        "Temperature is the primary driver of crop yield, with irrigation "
        "being the second most important factor",
        ClaimIntent(
            claim_id="ex_rank_2",
            pattern=PatternClass.EFFECT_RANKING,
            treatment="temperature",
            outcome="yield",
            ranking_vars=["temperature", "irrigation"],
        ),
    ),
]

# ---------------------------------------------------------------------------
# Negative exemplars: claims that should produce ABSTENTION
# ---------------------------------------------------------------------------

ABSTENTION_EXEMPLARS: list[tuple[str, str]] = [
    # Statistical artifacts — can't verify against SCM
    (
        "The regression coefficient of A on Y is 0.45 (p < 0.001)",
        "regression_coefficient: model-dependent, not world truth",
    ),
    (
        "The R-squared of the model predicting Y from A and C is 0.72",
        "model_fit_metric: depends on modeling choices, not verifiable",
    ),
    # Vague claims without identifiable variables
    (
        "The data suggests some interesting patterns",
        "too_vague: no identifiable treatment, outcome, or direction",
    ),
    # Claims about sample properties, not causal structure
    (
        "The sample size was sufficient to detect small effects",
        "sample_property: not a claim about the world",
    ),
    # Claims requiring multi-outcome comparison (not yet supported)
    (
        "Increasing A improves Y but worsens Z, creating a trade-off",
        "multi_outcome: trade-off between outcomes not yet supported",
    ),
]


def get_positive_exemplars() -> list[tuple[str, ClaimIntent]]:
    """Return all positive exemplars for few-shot prompting."""
    return POSITIVE_EXEMPLARS


def get_abstention_exemplars() -> list[tuple[str, str]]:
    """Return all abstention exemplars (claim_text, reason)."""
    return ABSTENTION_EXEMPLARS


def get_all_exemplar_texts() -> list[str]:
    """Return all exemplar claim texts (positive + negative)."""
    texts = [t for t, _ in POSITIVE_EXEMPLARS]
    texts.extend(t for t, _ in ABSTENTION_EXEMPLARS)
    return texts


__all__ = [
    "ABSTENTION_EXEMPLARS",
    "POSITIVE_EXEMPLARS",
    "get_abstention_exemplars",
    "get_all_exemplar_texts",
    "get_positive_exemplars",
]
