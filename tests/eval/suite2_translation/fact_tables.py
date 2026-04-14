"""Suite 2 — Formal fact tables derived bottom-up from SCM equations.

Each fact is an analytical truth about a world, derived from the
structural equations. Facts are the bridge between equations and
gold claims: equations -> facts -> natural language claims/SQs.

The chain of trust:
  1. Equations are DEFINITIONS (true by construction)
  2. Facts are DERIVED from equations (verified by Monte Carlo)
  3. Claims are FORMULATIONS of facts (human-written, curated)
  4. Gold verdicts come from running gold specs against the SCM

Every fact has:
  - Unique ID (W{n}_F{nn})
  - Regime (do / observational / adjusted / identifiability)
  - Estimand (what is being measured)
  - Truth (analytical value + holds/not-holds)
  - Semantic families covered (from the 41-family matrix)
  - Surface forms (2-3 natural language formulations at varying difficulty)
  - Hard negatives (related facts that sound similar but differ)
  - Abstain reason (if the fact is about a non-expressible property)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Regime(str, Enum):
    """The causal regime under which the fact holds."""
    DO = "do"                         # Interventional (do-calculus)
    OBSERVATIONAL = "observational"   # No intervention, just conditioning
    ADJUSTED = "adjusted"             # Observational with adjustment set
    IDENTIFIABILITY = "identifiability"  # About whether something CAN be estimated
    COMPARATIVE = "comparative"       # Comparing two regimes


class ExpectedStatus(str, Enum):
    """What the compiler should do with this claim."""
    COMPILE = "compile"           # Compiler should produce specs
    ABSTAIN = "abstain"           # Compiler should refuse (non-expressible)


class Verdict(str, Enum):
    """What the verifier should return (only if status=COMPILE)."""
    TRUE = "true"                 # Claim holds against the SCM
    FALSE = "false"               # Claim does NOT hold against the SCM
    NOT_IDENTIFIABLE = "not_identifiable"  # Causal effect is not identifiable


@dataclass
class SurfaceForm:
    """A natural language formulation of a fact."""
    text: str
    difficulty: str  # "easy", "medium", "hard"
    notes: str = ""  # Why this formulation is interesting/tricky


@dataclass
class Fact:
    """A single analytical fact derived from an SCM world."""
    fact_id: str
    world: str
    regime: Regime
    estimand: str
    conditioning: str
    truth_numerical: float | None
    truth_description: str
    families: list[str]
    surface_forms: list[SurfaceForm]
    expected_status: ExpectedStatus = ExpectedStatus.COMPILE
    truth_value: Verdict | None = None  # None if expected_status == ABSTAIN
    hard_negative_of: list[str] = field(default_factory=list)
    abstain_reason: str | None = None
    margin_note: str = ""


# ===================================================================
# W1 — COMPARATIVE EFFECTIVENESS
# ===================================================================

W1_FACTS: list[Fact] = [
    # --- CC-A1: Causal effects ---
    Fact(
        fact_id="W1_F01",
        world="w1_comparative_effectiveness",
        regime=Regime.DO,
        estimand="ATE(T -> Y)",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=0.68,
        truth_description="Treatment has a positive causal effect on outcome (0.68 per unit)",
        families=["CC-A1"],
        surface_forms=[
            SurfaceForm(
                "Treatment has a positive causal effect on outcome.",
                "easy",
            ),
            SurfaceForm(
                "Intervening to increase treatment dosage improves patient outcomes.",
                "medium",
                "Uses 'intervening' instead of 'causes'",
            ),
            SurfaceForm(
                "The causal effect of treatment on outcome, accounting for all "
                "pathways including through compliance, is approximately 0.7 per "
                "unit increase.",
                "hard",
                "Specifies total effect including mediation + gives magnitude",
            ),
        ],
    ),
    Fact(
        fact_id="W1_F02",
        world="w1_comparative_effectiveness",
        regime=Regime.DO,
        estimand="ATE(A -> Y)",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=-0.106,
        truth_description="Age has a small NEGATIVE total causal effect on outcome (~-0.11)",
        families=["CC-A1", "CC-B4"],
        surface_forms=[
            SurfaceForm(
                "Older patients tend to have worse outcomes, all else being equal.",
                "easy",
                "Misleading! This is observational language for a causal claim",
            ),
            SurfaceForm(
                "The total causal effect of age on outcome is negative.",
                "medium",
            ),
            SurfaceForm(
                "Despite a positive direct effect of age on outcome, the total "
                "causal effect is negative because age worsens severity, which "
                "reduces treatment, which hurts outcomes.",
                "hard",
                "Describes the full causal chain with sign reversals",
            ),
        ],
        margin_note="Weak effect (-0.106), close to zero. Claims about magnitude "
        "should use 'small' or 'weak', not 'large'.",
    ),
    Fact(
        fact_id="W1_F03",
        world="w1_comparative_effectiveness",
        regime=Regime.DO,
        estimand="ATE(T -> SE)",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=0.70,
        truth_description="Treatment causes side effects (0.70 per unit)",
        families=["CC-A1", "CC-C3"],
        surface_forms=[
            SurfaceForm(
                "Treatment causes side effects.",
                "easy",
            ),
            SurfaceForm(
                "Treatment improves the primary outcome but also increases "
                "the risk of side effects.",
                "medium",
                "Compound claim (multi-outcome): both Y up and SE up",
            ),
            SurfaceForm(
                "The treatment faces a trade-off: it improves outcome (effect "
                "~0.7) but causes side effects of similar magnitude (~0.7).",
                "hard",
                "Multi-outcome with quantitative comparison",
            ),
        ],
    ),

    # --- CC-A3: Mediation ---
    Fact(
        fact_id="W1_F04",
        world="w1_comparative_effectiveness",
        regime=Regime.DO,
        estimand="Direct effect T -> Y (fixing M)",
        conditioning="M fixed",
        truth_value=Verdict.TRUE,
        truth_numerical=0.50,
        truth_description="Direct effect of treatment on outcome is 0.50 (excluding mediation)",
        families=["CC-A3"],
        surface_forms=[
            SurfaceForm(
                "Treatment has a direct effect on outcome beyond its effect "
                "through compliance.",
                "medium",
            ),
            SurfaceForm(
                "Even if compliance were held constant, treatment would still "
                "improve outcomes.",
                "medium",
                "Counterfactual framing of direct effect",
            ),
            SurfaceForm(
                "The direct causal effect of treatment on outcome, controlling "
                "for compliance, is approximately 0.5.",
                "hard",
                "Explicit controlled direct effect with magnitude",
            ),
        ],
    ),
    Fact(
        fact_id="W1_F05",
        world="w1_comparative_effectiveness",
        regime=Regime.DO,
        estimand="Indirect effect T -> M -> Y",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=0.18,
        truth_description="Compliance mediates ~26% of treatment's effect on outcome",
        families=["CC-A3", "CC-B2"],
        surface_forms=[
            SurfaceForm(
                "Part of treatment's benefit comes through improved compliance.",
                "easy",
            ),
            SurfaceForm(
                "Compliance mediates the relationship between treatment and "
                "outcome.",
                "medium",
            ),
            SurfaceForm(
                "The indirect effect of treatment on outcome through compliance "
                "is positive but smaller than the direct effect.",
                "hard",
                "Compares indirect < direct (0.18 < 0.50)",
            ),
        ],
        hard_negative_of=["W1_F04"],
    ),

    # --- CC-A4: Heterogeneity ---
    Fact(
        fact_id="W1_F06",
        world="w1_comparative_effectiveness",
        regime=Regime.DO,
        estimand="ATE(T -> Y | B=b)",
        conditioning="B (biomarker)",
        truth_value=Verdict.TRUE,
        truth_numerical=None,
        truth_description="Treatment effect varies by biomarker: 0.68 + 0.35*B per unit",
        families=["CC-A4", "CC-C4"],
        surface_forms=[
            SurfaceForm(
                "The effect of treatment on outcome depends on the patient's "
                "biomarker level.",
                "easy",
            ),
            SurfaceForm(
                "Patients with high biomarker levels benefit more from treatment "
                "than those with low biomarker levels.",
                "medium",
            ),
            SurfaceForm(
                "Among patients with biomarker one standard deviation above the "
                "mean, the treatment effect is approximately 1.0, while for those "
                "one standard deviation below, it is approximately 0.3.",
                "hard",
                "Quantifies the heterogeneity at specific strata",
            ),
        ],
    ),

    # --- CC-A5: Confounding ---
    Fact(
        fact_id="W1_F07",
        world="w1_comparative_effectiveness",
        regime=Regime.COMPARATIVE,
        estimand="Confounding of T -> Y by S",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=None,
        truth_description="Severity confounds the treatment-outcome relationship",
        families=["CC-A5", "CC-B2", "CC-D1"],
        surface_forms=[
            SurfaceForm(
                "Disease severity confounds the relationship between treatment "
                "and outcome.",
                "easy",
            ),
            SurfaceForm(
                "Without adjusting for severity, the observed association between "
                "treatment and outcome is biased.",
                "medium",
            ),
            SurfaceForm(
                "Severity is a confounder, not a mediator, of the treatment-outcome "
                "relationship: it causes both the treatment decision and the outcome "
                "independently.",
                "hard",
                "Explicitly distinguishes confounder from mediator role",
            ),
        ],
        hard_negative_of=["W1_F05"],
    ),

    # --- CC-A6: Effect ranking ---
    Fact(
        fact_id="W1_F08",
        world="w1_comparative_effectiveness",
        regime=Regime.DO,
        estimand="Ranking of causal effects on Y",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=None,
        truth_description="T (0.68) > M_direct (0.30) > B (0.20) > A_direct (0.15)",
        families=["CC-A6"],
        surface_forms=[
            SurfaceForm(
                "Treatment has the strongest causal effect on outcome among "
                "all variables.",
                "easy",
            ),
            SurfaceForm(
                "Of all the variables in this system, treatment has a larger "
                "causal effect on outcome than biomarker, compliance, or age.",
                "medium",
            ),
            SurfaceForm(
                "Ranking variables by the magnitude of their direct causal "
                "effect on outcome: treatment (0.5) > compliance (0.3) > "
                "biomarker (0.2) > age (0.15).",
                "hard",
                "Note: this is DIRECT effects, not total. Different ranking if total.",
            ),
        ],
    ),

    # --- CC-A8: Variance effect ---
    Fact(
        fact_id="W1_F09",
        world="w1_comparative_effectiveness",
        regime=Regime.DO,
        estimand="Effect of T on Var(Y)",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=None,
        truth_description="Treatment increases outcome variance (due to B*T interaction)",
        families=["CC-A8"],
        surface_forms=[
            SurfaceForm(
                "Treated patients show more variable outcomes than untreated "
                "patients.",
                "medium",
            ),
            SurfaceForm(
                "Treatment increases not just the mean outcome but also its "
                "spread, because patients with different biomarker levels "
                "respond differently.",
                "hard",
                "Links variance effect to heterogeneity mechanism",
            ),
        ],
        margin_note="Variance is monotone in T due to cross-term 0.2*B + 0.35*B*T. "
        "At T=-1 variance is LOWER than T=0.",
    ),

    # --- CC-B1: Edge orientation ---
    Fact(
        fact_id="W1_F10",
        world="w1_comparative_effectiveness",
        regime=Regime.DO,
        estimand="Direction: T -> Y (not Y -> T)",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=None,
        truth_description="Treatment causes outcome changes, not the reverse",
        families=["CC-B1"],
        surface_forms=[
            SurfaceForm(
                "Treatment causes changes in outcome, not the other way around.",
                "easy",
            ),
            SurfaceForm(
                "The causal direction runs from treatment to outcome; outcome "
                "does not influence treatment assignment.",
                "medium",
            ),
        ],
        hard_negative_of=["W1_F07"],
    ),

    # --- CC-C2: Negation ---
    Fact(
        fact_id="W1_F11",
        world="w1_comparative_effectiveness",
        regime=Regime.DO,
        estimand="ATE(B -> SE)",
        conditioning="none",
        truth_value=Verdict.TRUE,  # Surface forms assert NULL effect — that IS true
        truth_numerical=0.0,
        truth_description="Biomarker has NO causal effect on side effects",
        families=["CC-C2"],
        surface_forms=[
            SurfaceForm(
                "Biomarker level does not affect the risk of side effects.",
                "easy",
            ),
            SurfaceForm(
                "There is no causal relationship between biomarker and side "
                "effects.",
                "medium",
            ),
            SurfaceForm(
                "Side effects are not influenced by biomarker status; they "
                "depend only on treatment dosage and age.",
                "hard",
                "Negation + specifying what DOES cause SE",
            ),
        ],
    ),

    # --- CC-C5: Conditioning semantics ---
    Fact(
        fact_id="W1_F12",
        world="w1_comparative_effectiveness",
        regime=Regime.ADJUSTED,
        estimand="Partial association T,Y | S",
        conditioning="S (severity)",
        truth_value=Verdict.TRUE,
        truth_numerical=None,
        truth_description="After adjusting for severity, T and Y are positively associated",
        families=["CC-C5", "CC-D4"],
        surface_forms=[
            SurfaceForm(
                "Controlling for severity, treatment is positively associated "
                "with outcome.",
                "medium",
            ),
            SurfaceForm(
                "Holding severity constant, the association between treatment "
                "and outcome reflects the causal benefit of treatment.",
                "hard",
                "Links adjusted association to causal interpretation",
            ),
        ],
    ),

    # --- FALSE CLAIMS (traps) ---

    Fact(
        fact_id="W1_F13",
        world="w1_comparative_effectiveness",
        regime=Regime.DO,
        estimand="ATE(A -> Y) POSITIVE (false claim)",
        conditioning="none",
        truth_value=Verdict.FALSE,
        truth_numerical=-0.106,
        truth_description="FALSE: Age has a NEGATIVE total effect, not positive",
        families=["CC-A1", "CC-B4"],
        surface_forms=[
            SurfaceForm(
                "Older age causes better health outcomes.",
                "easy",
                "FALSE — total effect is -0.106 (direct +0.15 dominated by indirect)",
            ),
            SurfaceForm(
                "Age has a positive causal effect on outcome.",
                "medium",
                "FALSE — tricky because direct effect IS positive (+0.15)",
            ),
        ],
        hard_negative_of=["W1_F02"],
    ),
    Fact(
        fact_id="W1_F14",
        world="w1_comparative_effectiveness",
        regime=Regime.DO,
        estimand="ATE(B -> SE) POSITIVE (false claim)",
        conditioning="none",
        truth_value=Verdict.FALSE,
        truth_numerical=0.0,
        truth_description="FALSE: Biomarker has ZERO effect on side effects",
        families=["CC-C2"],
        surface_forms=[
            SurfaceForm(
                "Higher biomarker levels increase the risk of side effects.",
                "easy",
                "FALSE — B has no path to SE",
            ),
        ],
        hard_negative_of=["W1_F11"],
    ),
]


# ===================================================================
# W2 — OBSERVATIONAL EPIDEMIOLOGY
# ===================================================================

W2_FACTS: list[Fact] = [
    # --- CC-A1: Causal effect (negative!) ---
    Fact(
        fact_id="W2_F01",
        world="w2_observational_epidemiology",
        regime=Regime.DO,
        estimand="ATE(E -> D)",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=-0.20,
        truth_description="Exposure has a negative (protective) causal effect on disease",
        families=["CC-A1", "CC-B4"],
        surface_forms=[
            SurfaceForm(
                "Exposure reduces the risk of disease.",
                "easy",
            ),
            SurfaceForm(
                "The causal effect of exposure on disease is protective: "
                "increasing exposure decreases disease risk.",
                "medium",
            ),
            SurfaceForm(
                "Intervening to increase exposure by one unit reduces disease "
                "risk by approximately 0.2 units.",
                "hard",
                "Quantitative interventional claim",
            ),
        ],
        hard_negative_of=["W2_F02"],
    ),

    # --- CC-A2: Observational association (opposite sign!) ---
    Fact(
        fact_id="W2_F02",
        world="w2_observational_epidemiology",
        regime=Regime.OBSERVATIONAL,
        estimand="Crude association E, D",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=None,  # gold uses PARTIAL_CORRELATION (corr ~0.34, not cov 0.182)
        truth_description="Crude observational correlation of E and D is POSITIVE",
        families=["CC-A2", "CC-D1"],
        surface_forms=[
            SurfaceForm(
                "Exposure is positively associated with disease in the population.",
                "easy",
            ),
            SurfaceForm(
                "People with higher exposure tend to have higher disease rates.",
                "medium",
            ),
            SurfaceForm(
                "The observational correlation between exposure and disease is "
                "positive, even though the causal effect is protective.",
                "hard",
                "Explicitly states the Simpson's paradox",
            ),
        ],
        hard_negative_of=["W2_F01"],
    ),

    # --- CC-A3: Mediation with opposite signs ---
    Fact(
        fact_id="W2_F03",
        world="w2_observational_epidemiology",
        regime=Regime.DO,
        estimand="Direct effect E -> D",
        conditioning="M fixed",
        truth_value=Verdict.TRUE,
        truth_numerical=-0.40,
        truth_description="Direct effect of exposure on disease is -0.40 (harmful prevented)",
        families=["CC-A3"],
        surface_forms=[
            SurfaceForm(
                "The direct protective effect of exposure on disease is "
                "larger than the total effect.",
                "medium",
            ),
            SurfaceForm(
                "Controlling for the mediator, exposure has a stronger "
                "protective direct effect (-0.4) than its total effect (-0.2) "
                "suggests.",
                "hard",
                "Direct > total because indirect has opposite sign",
            ),
        ],
    ),
    Fact(
        fact_id="W2_F04",
        world="w2_observational_epidemiology",
        regime=Regime.DO,
        estimand="Indirect effect E -> M -> D",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=0.20,
        truth_description="Indirect effect through mediator is POSITIVE (+0.20) — opposite to direct!",
        families=["CC-A3", "CC-B4"],
        surface_forms=[
            SurfaceForm(
                "Exposure increases disease risk indirectly through the mediator.",
                "medium",
            ),
            SurfaceForm(
                "The indirect pathway (exposure -> mediator -> disease) works "
                "in the opposite direction from the direct effect: exposure "
                "increases the mediator, which increases disease.",
                "hard",
                "Opposite-sign mediation — tricky for compilers",
            ),
        ],
        hard_negative_of=["W2_F03"],
    ),

    # --- CC-A5: Confounding ---
    Fact(
        fact_id="W2_F05",
        world="w2_observational_epidemiology",
        regime=Regime.COMPARATIVE,
        estimand="Confounding of E -> D by C",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=None,
        truth_description="C confounds the exposure-disease relationship (causes both)",
        families=["CC-A5", "CC-D1"],
        surface_forms=[
            SurfaceForm(
                "The confounder drives both exposure and disease, creating a "
                "spurious positive association.",
                "medium",
            ),
            SurfaceForm(
                "Without adjusting for the confounder, the association between "
                "exposure and disease has the wrong sign.",
                "hard",
                "States the consequence: wrong sign without adjustment",
            ),
        ],
    ),

    # --- Partial correlation (Simpson's at correlation level) ---
    Fact(
        fact_id="W2_F06",
        world="w2_observational_epidemiology",
        regime=Regime.ADJUSTED,
        estimand="Partial corr(E, D | C)",
        conditioning="C (confounder)",
        truth_value=Verdict.TRUE,
        truth_numerical=None,
        truth_description="Partial correlation of E and D given C is NEGATIVE (correct sign)",
        families=["CC-A2", "CC-C5", "CC-D4"],
        surface_forms=[
            SurfaceForm(
                "After adjusting for the confounder, exposure is negatively "
                "associated with disease.",
                "medium",
            ),
            SurfaceForm(
                "Controlling for the confounder reverses the direction of the "
                "exposure-disease association: from positive (crude) to negative "
                "(adjusted).",
                "hard",
                "Simpson's reversal at correlation level",
            ),
        ],
        hard_negative_of=["W2_F02"],
    ),

    # --- Collider bias ---
    Fact(
        fact_id="W2_F07",
        world="w2_observational_epidemiology",
        regime=Regime.ADJUSTED,
        estimand="Bias from conditioning on L (collider)",
        conditioning="L (collider)",
        truth_value=Verdict.TRUE,
        truth_numerical=None,
        truth_description="Conditioning on the collider L biases the E->D estimate",
        families=["CC-D2", "CC-B2"],
        surface_forms=[
            SurfaceForm(
                "Adjusting for the collider variable introduces bias in the "
                "exposure-disease estimate.",
                "medium",
            ),
            SurfaceForm(
                "The collider is caused by both exposure and disease; "
                "conditioning on it opens a spurious path and distorts the "
                "estimate of the causal effect.",
                "hard",
                "Explains the mechanism of collider bias",
            ),
        ],
    ),

    # --- Instrument ---
    Fact(
        fact_id="W2_F08",
        world="w2_observational_epidemiology",
        regime=Regime.DO,
        estimand="I affects D only through E",
        conditioning="E fixed",
        truth_value=Verdict.TRUE,
        truth_numerical=0.0,
        truth_description="Upstream factor has zero direct effect on disease (valid instrument)",
        families=["CC-B1", "CC-C2"],
        surface_forms=[
            SurfaceForm(
                "The upstream factor does not directly affect disease.",
                "easy",
            ),
            SurfaceForm(
                "The upstream factor influences disease only through its "
                "effect on exposure.",
                "medium",
            ),
        ],
    ),

    # --- Identifiability ---
    Fact(
        fact_id="W2_F09",
        world="w2_observational_epidemiology",
        regime=Regime.IDENTIFIABILITY,
        estimand="Identifiability of ATE(E -> D)",
        conditioning="adjustment set {C}",
        truth_value=Verdict.TRUE,
        truth_numerical=None,
        truth_description="ATE(E->D) IS identifiable by adjusting for C",
        families=["SQ-A3"],
        surface_forms=[
            SurfaceForm(
                "Can we estimate the causal effect of exposure on disease?",
                "easy",
                "SQ formulation — answer is YES, adjust for C",
            ),
            SurfaceForm(
                "Is the causal effect of exposure on disease identifiable from "
                "observational data, given that we can measure the confounder?",
                "hard",
                "Explicit identifiability question",
            ),
        ],
    ),

    # --- Decision boundary: causal vs observational ---
    Fact(
        fact_id="W2_F10",
        world="w2_observational_epidemiology",
        regime=Regime.OBSERVATIONAL,
        estimand="'Exposure increases disease' (observational reading)",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=None,
        truth_description="Observationally TRUE (positive crude association)",
        families=["CC-D1"],
        surface_forms=[
            SurfaceForm(
                "People with more exposure have higher disease rates.",
                "easy",
                "TRUE if read as observational, FALSE if read as causal",
            ),
        ],
        hard_negative_of=["W2_F01"],
    ),
    Fact(
        fact_id="W2_F11",
        world="w2_observational_epidemiology",
        regime=Regime.DO,
        estimand="'Exposure increases disease' (causal reading)",
        conditioning="none",
        truth_value=Verdict.FALSE,
        truth_numerical=None,
        truth_description="Causally FALSE (ATE is negative / protective)",
        families=["CC-D1", "CC-B4"],
        surface_forms=[
            SurfaceForm(
                "Exposure causes an increase in disease.",
                "easy",
                "FALSE — causal effect is protective, not harmful",
            ),
            SurfaceForm(
                "Increasing exposure leads to higher disease risk.",
                "medium",
                "FALSE — 'leads to' implies causal",
            ),
        ],
        hard_negative_of=["W2_F10"],
    ),

    # --- FALSE: L as valid adjustment set ---
    Fact(
        fact_id="W2_F12",
        world="w2_observational_epidemiology",
        regime=Regime.IDENTIFIABILITY,
        estimand="L as valid adjustment set for E -> D (false claim)",
        conditioning="adjustment set {L}",
        truth_value=Verdict.FALSE,
        truth_numerical=None,
        truth_description="FALSE: L is a collider, not a valid adjustment variable",
        families=["CC-D2", "CC-B2"],
        surface_forms=[
            SurfaceForm(
                "Adjusting for the collider variable gives a valid estimate "
                "of the causal effect of exposure on disease.",
                "medium",
                "FALSE — conditioning on collider opens spurious path",
            ),
        ],
        hard_negative_of=["W2_F09"],
    ),
]


# ===================================================================
# W3 — ENVIRONMENTAL HEALTH
# ===================================================================

W3_FACTS: list[Fact] = [
    # --- Threshold / changepoint ---
    Fact(
        fact_id="W3_F01",
        world="w3_environmental_health",
        regime=Regime.DO,
        estimand="Effect of Temp on H (below threshold)",
        conditioning="Temp < 0",
        truth_value=Verdict.TRUE,
        truth_numerical=-0.20,
        truth_description="Below Temp=0, temperature has a mild negative effect on health (-0.20/unit)",
        families=["CC-A1"],
        surface_forms=[
            SurfaceForm(
                "At low temperatures, increasing temperature has a small "
                "negative effect on health.",
                "medium",
            ),
            SurfaceForm(
                "Below the threshold, temperature affects health only "
                "indirectly through water quality, with a slope of about -0.2.",
                "hard",
                "Specifies mechanism (indirect only) and magnitude",
            ),
        ],
    ),
    Fact(
        fact_id="W3_F02",
        world="w3_environmental_health",
        regime=Regime.DO,
        estimand="Effect of Temp on H (above threshold)",
        conditioning="Temp >= 0",
        truth_value=Verdict.TRUE,
        truth_numerical=-1.00,
        truth_description="Above Temp=0, temperature has a strong negative effect on health (-1.0/unit)",
        families=["CC-A1"],
        surface_forms=[
            SurfaceForm(
                "High temperatures are strongly harmful to health.",
                "easy",
            ),
            SurfaceForm(
                "Above the threshold, each unit increase in temperature "
                "reduces health by approximately 1.0 unit — five times the "
                "effect below the threshold.",
                "hard",
                "Quantitative comparison of slopes",
            ),
        ],
    ),
    Fact(
        fact_id="W3_F03",
        world="w3_environmental_health",
        regime=Regime.DO,
        estimand="Changepoint in Temp -> H",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=0.0,
        truth_description="There is a changepoint at Temp=0 where the slope steepens",
        families=["CC-B5"],
        margin_note="Threshold/changepoint fact. Not CC-A7 (tail risk).",
        surface_forms=[
            SurfaceForm(
                "There is a threshold in the temperature-health relationship.",
                "easy",
            ),
            SurfaceForm(
                "The effect of temperature on health changes sharply at a "
                "threshold near zero: mild below, severe above.",
                "medium",
            ),
            SurfaceForm(
                "The temperature-health dose-response curve has a changepoint "
                "at approximately zero degrees, where the slope changes from "
                "-0.2 to -1.0.",
                "hard",
                "Full quantitative changepoint description",
            ),
        ],
    ),

    # --- Tail risk ---
    Fact(
        fact_id="W3_F04",
        world="w3_environmental_health",
        regime=Regime.DO,
        estimand="P(H < -1.0 | do(Temp=high))",
        conditioning="Temp = 1.5",
        truth_value=Verdict.TRUE,
        truth_numerical=None,
        truth_description="High temperature substantially increases the probability of very poor health",
        families=["CC-A7"],
        surface_forms=[
            SurfaceForm(
                "Extreme heat creates a significant risk of very poor health "
                "outcomes.",
                "medium",
            ),
            SurfaceForm(
                "The probability of health falling below a critical threshold "
                "is much higher at elevated temperatures than at low temperatures.",
                "hard",
                "Tail risk framing",
            ),
        ],
    ),

    # --- Non-identifiability (NOT abstention — this IS expressible) ---
    # The compiler should produce an identifiability_check spec that
    # returns NOT_IDENTIFIABLE. This is a real answer, not a refusal.
    Fact(
        fact_id="W3_F05",
        world="w3_environmental_health",
        regime=Regime.IDENTIFIABILITY,
        estimand="Identifiability of ATE(P -> H)",
        conditioning="U latent",
        truth_value=Verdict.NOT_IDENTIFIABLE,
        truth_numerical=None,
        truth_description="The causal effect of pollution on health is NOT identifiable "
        "because a hidden factor confounds the relationship",
        families=["CC-E2", "SQ-A3", "SQ-C2"],
        surface_forms=[
            SurfaceForm(
                "Can we estimate the causal effect of pollution on health?",
                "easy",
                "SQ — answer is NO, hidden confounder blocks identification",
            ),
            SurfaceForm(
                "The causal effect of pollution on health cannot be determined "
                "from the available data because an unmeasured factor affects both.",
                "medium",
            ),
            SurfaceForm(
                "No set of measured variables is sufficient to block the "
                "backdoor path from pollution to health through the hidden "
                "confounding factor.",
                "hard",
                "Technical identifiability language",
            ),
        ],
        margin_note="NOT abstention. The grammar CAN express identifiability checks. "
        "The compiler should produce specs with identifiability_check measurement "
        "and not_identifiable assertion. The latent confounder U->P, U->H means "
        "no observable adjustment set blocks the backdoor path.",
    ),

    # --- True causal effect (known only via do-calculus, not from data) ---
    Fact(
        fact_id="W3_F06",
        world="w3_environmental_health",
        regime=Regime.DO,
        estimand="ATE(P -> H) (true, via intervention)",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=-0.32,
        truth_description="True causal effect of pollution on health is -0.32 (harmful)",
        families=["CC-A1"],
        surface_forms=[
            SurfaceForm(
                "Pollution harms health.",
                "easy",
            ),
            SurfaceForm(
                "If we could intervene to reduce pollution, health would "
                "improve by approximately 0.32 units per unit decrease.",
                "hard",
                "Interventional framing — requires knowing the true SCM",
            ),
        ],
        hard_negative_of=["W3_F05"],
        margin_note="This fact is TRUE at the SCM level but NOT identifiable "
        "from observational data. The compiler should handle this carefully.",
    ),

    # --- Confounded observational estimate ---
    Fact(
        fact_id="W3_F07",
        world="w3_environmental_health",
        regime=Regime.OBSERVATIONAL,
        estimand="Crude association P, H",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=None,
        truth_description="Crude association of P and H is less negative than the true "
        "causal effect (positive confounding by U)",
        families=["CC-A2", "CC-A5", "CC-D1"],
        surface_forms=[
            SurfaceForm(
                "The observed association between pollution and health "
                "underestimates the true harmful effect of pollution.",
                "hard",
                "Describes confounding bias direction",
            ),
        ],
    ),

    # --- Null relationship (WindSpeed) ---
    Fact(
        fact_id="W3_F08",
        world="w3_environmental_health",
        regime=Regime.DO,
        estimand="ATE(WindSpeed -> H)",
        conditioning="none",
        truth_value=Verdict.TRUE,  # Surface forms assert NULL effect — that IS true
        truth_numerical=0.0,
        truth_description="Wind speed has NO effect on health whatsoever",
        families=["CC-C2", "CC-B4"],
        surface_forms=[
            SurfaceForm(
                "Wind speed does not affect health.",
                "easy",
            ),
            SurfaceForm(
                "There is no causal relationship between wind speed and health "
                "outcomes.",
                "medium",
            ),
            SurfaceForm(
                "Wind speed is not associated with health, neither causally "
                "nor observationally.",
                "hard",
                "Null in BOTH regimes — no path at all",
            ),
        ],
    ),

    # --- Indirect-only effect (R -> H) ---
    Fact(
        fact_id="W3_F09",
        world="w3_environmental_health",
        regime=Regime.DO,
        estimand="Direct effect R -> H",
        conditioning="Temp, P fixed",
        truth_value=Verdict.TRUE,  # Surface forms assert NULL direct effect — that IS true
        truth_numerical=0.0,
        truth_description="Region has NO direct effect on health (only indirect via Temp and P)",
        families=["CC-B1", "CC-C2"],
        surface_forms=[
            SurfaceForm(
                "Region does not directly affect health.",
                "easy",
            ),
            SurfaceForm(
                "Region affects health only through its influence on "
                "temperature and pollution.",
                "medium",
            ),
            SurfaceForm(
                "Holding temperature and pollution constant, regional "
                "differences in health disappear.",
                "hard",
                "Conditional independence framing",
            ),
        ],
    ),

    # --- FALSE CLAIMS (traps) ---

    Fact(
        fact_id="W3_F13",
        world="w3_environmental_health",
        regime=Regime.IDENTIFIABILITY,
        estimand="ATE(P -> H) identifiable (false claim)",
        conditioning="none",
        truth_value=Verdict.FALSE,
        truth_numerical=None,
        truth_description="FALSE: P->H is NOT identifiable due to latent confounder U",
        families=["CC-E2"],
        surface_forms=[
            SurfaceForm(
                "The causal effect of pollution on health can be estimated "
                "from the available data.",
                "medium",
                "FALSE — U confounds P and H, and U is latent",
            ),
        ],
        hard_negative_of=["W3_F05"],
    ),
    Fact(
        fact_id="W3_F14",
        world="w3_environmental_health",
        regime=Regime.DO,
        estimand="ATE(WindSpeed -> H) POSITIVE (false claim)",
        conditioning="none",
        truth_value=Verdict.FALSE,
        truth_numerical=0.0,
        truth_description="FALSE: Wind speed has zero effect on health",
        families=["CC-C2"],
        surface_forms=[
            SurfaceForm(
                "Higher wind speeds improve health outcomes.",
                "easy",
                "FALSE — WindSpeed is completely disconnected from H",
            ),
            SurfaceForm(
                "Wind speed is positively correlated with health.",
                "medium",
                "FALSE — zero correlation (no path at all)",
            ),
        ],
        hard_negative_of=["W3_F08"],
    ),

    # W3_F10 REMOVED: Codex review found that under do(Temp=t), the
    # piecewise term shifts the MEAN, not the VARIANCE. Var(H|do(Temp))
    # is approximately constant (~0.152) across all Temp values. The
    # variance-effect fact was incorrect.

    # --- Abstention: temporal claim ---
    Fact(
        fact_id="W3_F11",
        world="w3_environmental_health",
        regime=Regime.DO,
        estimand="N/A (temporal claim)",
        conditioning="none",
        expected_status=ExpectedStatus.ABSTAIN,
        truth_value=None,
        truth_numerical=None,
        truth_description="ABSTENTION: temporal claims cannot be evaluated in SCM",
        families=["CC-E1"],
        surface_forms=[
            SurfaceForm(
                "Temperature changes precede health effects by several days.",
                "medium",
                "Temporal claim — compiler should ABSTAIN (not expressible)",
            ),
        ],
        abstain_reason="Temporal ordering is not represented in the SCM. "
        "The SCM captures structural relationships, not time dynamics.",
    ),

    # --- Abstention: methodological claim ---
    Fact(
        fact_id="W3_F12",
        world="w3_environmental_health",
        regime=Regime.DO,
        estimand="N/A (methodological claim)",
        conditioning="none",
        expected_status=ExpectedStatus.ABSTAIN,
        truth_value=None,
        truth_numerical=None,
        truth_description="ABSTENTION: methodological claims cannot be compiled",
        families=["CC-E3"],
        surface_forms=[
            SurfaceForm(
                "A randomized controlled trial would be needed to establish "
                "the causal effect of pollution on health.",
                "medium",
                "Methodological claim — compiler should ABSTAIN",
            ),
            SurfaceForm(
                "The sample size is insufficient to detect a small effect "
                "of wind speed on health.",
                "hard",
                "Statistical power claim — not expressible in grammar",
            ),
        ],
        abstain_reason="Methodological and statistical claims are outside "
        "the scope of the AtomicSpec grammar.",
    ),
]


# -------------------------------------------------------------------
# SQ (Sub-Question) facts — formulated as questions, not claims
# -------------------------------------------------------------------

SQ_FACTS: list[Fact] = [
    # --- SQ-A1: Direct causal question ---
    Fact(
        fact_id="SQ_F01",
        world="w1_comparative_effectiveness",
        regime=Regime.DO,
        estimand="SQ: Does T affect Y?",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=0.68,
        truth_description="Yes, treatment causally affects outcome (ATE=0.68)",
        families=["SQ-A1"],
        surface_forms=[
            SurfaceForm(
                "Does treatment affect outcome?",
                "easy",
            ),
            SurfaceForm(
                "What is the causal effect of treatment on patient outcomes?",
                "medium",
            ),
            SurfaceForm(
                "If we were to intervene and change the treatment level, "
                "would we observe a change in outcome?",
                "hard",
                "Interventional question phrasing",
            ),
        ],
    ),

    # --- SQ-A2: Observational / associative ---
    Fact(
        fact_id="SQ_F02",
        world="w2_observational_epidemiology",
        regime=Regime.OBSERVATIONAL,
        estimand="SQ: Is E associated with D?",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=None,
        truth_description="Yes, E and D are positively associated (but causally protective!)",
        families=["SQ-A2"],
        surface_forms=[
            SurfaceForm(
                "Is exposure associated with disease?",
                "easy",
            ),
            SurfaceForm(
                "Is there an observational relationship between exposure "
                "and disease in the population?",
                "medium",
            ),
        ],
    ),

    # --- SQ-A3: Identifiability question ---
    Fact(
        fact_id="SQ_F03",
        world="w3_environmental_health",
        regime=Regime.IDENTIFIABILITY,
        estimand="SQ: Can we identify ATE(P -> H)?",
        conditioning="U latent",
        truth_value=Verdict.NOT_IDENTIFIABLE,
        truth_numerical=None,
        truth_description="No — hidden confounder prevents identification",
        families=["SQ-A3"],
        surface_forms=[
            SurfaceForm(
                "Can we estimate the causal effect of pollution on health?",
                "easy",
            ),
            SurfaceForm(
                "Is the causal effect of pollution on health identifiable "
                "from the measured variables?",
                "hard",
            ),
        ],
    ),

    # --- SQ-A4: Compound question ---
    Fact(
        fact_id="SQ_F04",
        world="w1_comparative_effectiveness",
        regime=Regime.DO,
        estimand="SQ: Does T affect Y, and if so, through what pathway?",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=None,
        truth_description="Yes (ATE=0.68), through both direct (0.50) and via compliance (0.18)",
        families=["SQ-A4"],
        surface_forms=[
            SurfaceForm(
                "Does treatment affect outcome, and if so, through what "
                "pathway?",
                "medium",
            ),
            SurfaceForm(
                "Is the treatment effect entirely direct, or does part of "
                "it operate through compliance?",
                "hard",
                "Compound: causal question + mediation decomposition",
            ),
        ],
    ),

    # --- SQ-B1: Causal-adjust vs observational-partial-correlation ---
    Fact(
        fact_id="SQ_F05",
        world="w2_observational_epidemiology",
        regime=Regime.ADJUSTED,
        estimand="SQ: After adjusting for C, what is E-D relationship?",
        conditioning="C (confounder)",
        truth_value=Verdict.TRUE,
        truth_numerical=None,
        truth_description="Adjusted association is negative (correct sign)",
        families=["SQ-B1"],
        surface_forms=[
            SurfaceForm(
                "What is the relationship between exposure and disease "
                "after adjusting for the confounder?",
                "medium",
            ),
            SurfaceForm(
                "After controlling for the confounder, is exposure still "
                "associated with increased disease?",
                "hard",
                "Answer: NO, association reverses (Simpson's)",
            ),
        ],
    ),

    # --- SQ-B2: Effect question vs mechanism question ---
    Fact(
        fact_id="SQ_F06",
        world="w1_comparative_effectiveness",
        regime=Regime.DO,
        estimand="SQ: How does treatment affect outcome? (mechanism)",
        conditioning="none",
        truth_value=Verdict.TRUE,
        truth_numerical=None,
        truth_description="Through direct effect and mediation via compliance",
        families=["SQ-B2"],
        surface_forms=[
            SurfaceForm(
                "How does treatment affect outcome?",
                "easy",
                "Mechanism question, not just 'does it?'",
            ),
            SurfaceForm(
                "What are the pathways through which treatment influences "
                "patient outcomes?",
                "medium",
            ),
        ],
    ),

    # --- SQ-C1: Non-expressible optimization question ---
    Fact(
        fact_id="SQ_F07",
        world="w1_comparative_effectiveness",
        regime=Regime.DO,
        estimand="N/A (optimization question)",
        conditioning="none",
        expected_status=ExpectedStatus.ABSTAIN,
        truth_value=None,
        truth_numerical=None,
        truth_description="ABSTENTION: optimization questions not expressible",
        families=["SQ-C1"],
        surface_forms=[
            SurfaceForm(
                "What is the optimal treatment dose?",
                "easy",
                "Optimization — compiler should ABSTAIN",
            ),
            SurfaceForm(
                "What treatment level maximizes outcome while minimizing "
                "side effects?",
                "hard",
                "Multi-objective optimization — not expressible",
            ),
        ],
        abstain_reason="Optimization questions require searching over intervention "
        "values, which is not supported by the AtomicSpec grammar.",
    ),
]


# -------------------------------------------------------------------
# All facts combined
# -------------------------------------------------------------------

ALL_FACTS: list[Fact] = W1_FACTS + W2_FACTS + W3_FACTS + SQ_FACTS

# Summary statistics
FACT_COUNT = len(ALL_FACTS)
SURFACE_FORM_COUNT = sum(len(f.surface_forms) for f in ALL_FACTS)
FAMILY_COVERAGE = sorted(set(
    fam for f in ALL_FACTS for fam in f.families
))
