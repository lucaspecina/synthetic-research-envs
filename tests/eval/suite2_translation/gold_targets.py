"""Suite 2 — Gold targets: expected compiler output per surface form.

Each gold target defines what the compiler SHOULD produce for a given
natural language claim or SQ. Evaluation is 3-stage:

  1. Compile/abstain decision (binary)
  2. Structural contract (regime, variables, measurement kind)
  3. Verdict equivalence (same result when run against SCM)

Gold targets attach to SURFACE FORMS, not facts. Different surface forms
of the same fact may require different gold specs.

Design decisions documented in: research/synthesis/eval_suite_translation.md
(section "Gold target design", 2026-04-13)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sreg.models.open_investigation import (
    Assertion,
    AssertionKind,
    AtomicSpec,
    Comparison,
    ComparisonKind,
    Measurement,
    MeasurementKind,
    QueryArm,
    QueryKind,
)


# -------------------------------------------------------------------
# GoldTarget structure
# -------------------------------------------------------------------

@dataclass
class StructuralContract:
    """What the compiler's output must satisfy structurally.

    This catches "right answer, wrong reason" — e.g., using BASELINE
    (observational) when the claim is causal (should use INTERVENE).

    Fields are checked in order from coarsest to finest:
      1. allowed_arm_kinds + required_role_vars (regime + variables)
      2. measurement/comparison/assertion kinds (operation)
      3. mediator/modifier/condition roles (causal structure)
    """
    allowed_arm_kinds: set[str]
    required_role_vars: dict[str, str]  # e.g. {"treatment": "T", "outcome": "Y"}
    required_measurement_kind: str
    required_comparison_kind: str
    required_assertion_polarity: str  # assertion kind or polarity class
    n_atoms: int | tuple[int, int] = 1  # exact or (min, max)
    # --- Causal structure roles (Phase 1 enrichment) ---
    required_mediator: str | None = None       # variable held fixed for CDE
    required_modifier: str | None = None       # effect modifier (heterogeneity)
    required_condition_vars: set[str] = field(default_factory=set)  # vars in condition_on
    required_cond_set: tuple[str, ...] | None = None  # adjustment/conditioning set


@dataclass
class GoldTarget:
    """Expected compiler output for a single surface form."""
    fact_id: str
    surface_form_index: int  # index into fact.surface_forms
    status: str  # "compile" | "abstain"

    # --- If status == "compile" ---
    atoms: list[AtomicSpec] = field(default_factory=list)
    acceptance_rule: str = "all_of"  # "all_of" | "any_of"
    structural_contract: StructuralContract | None = None
    # Alternative valid spec sets — compiler output matches if it equals
    # ANY of: [atoms] or any entry in alternative_atoms.
    alternative_atoms: list[list[AtomicSpec]] = field(default_factory=list)

    # --- If status == "abstain" ---
    abstain_reason_code: str | None = None


# ===================================================================
# BATCH 1: Priority gold targets
# ===================================================================

# -------------------------------------------------------------------
# W1_F01: "Treatment has a positive causal effect on outcome"
# ATE(T->Y) = 0.68. All surface forms use INTERVENE + DIFFERENCE.
# -------------------------------------------------------------------

W1_F01_GOLDS = [
    GoldTarget(
        fact_id="W1_F01",
        surface_form_index=0,  # "Treatment has a positive causal effect on outcome."
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id="W1_F01_s0_gold",
                arms=(
                    QueryArm(label="treated", kind=QueryKind.INTERVENE,
                             values={"T": 1.0}),
                    QueryArm(label="control", kind=QueryKind.INTERVENE,
                             values={"T": 0.0}),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE,
                                      ref_arm="control"),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "T", "outcome": "Y"},
            required_measurement_kind="mean",
            required_comparison_kind="difference",
            required_assertion_polarity="positive",
        ),
    ),
    GoldTarget(
        fact_id="W1_F01",
        surface_form_index=1,  # "Intervening to increase treatment dosage..."
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id="W1_F01_s1_gold",
                arms=(
                    QueryArm(label="treated", kind=QueryKind.INTERVENE,
                             values={"T": 1.0}),
                    QueryArm(label="control", kind=QueryKind.INTERVENE,
                             values={"T": 0.0}),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE,
                                      ref_arm="control"),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "T", "outcome": "Y"},
            required_measurement_kind="mean",
            required_comparison_kind="difference",
            required_assertion_polarity="positive",
        ),
    ),
    # surface_form_index=2 specifies "approximately 0.7" — same spec structure
    GoldTarget(
        fact_id="W1_F01",
        surface_form_index=2,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id="W1_F01_s2_gold",
                arms=(
                    QueryArm(label="treated", kind=QueryKind.INTERVENE,
                             values={"T": 1.0}),
                    QueryArm(label="control", kind=QueryKind.INTERVENE,
                             values={"T": 0.0}),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE,
                                      ref_arm="control"),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "T", "outcome": "Y"},
            required_measurement_kind="mean",
            required_comparison_kind="difference",
            required_assertion_polarity="positive",
        ),
    ),
]

# -------------------------------------------------------------------
# W1_F04: Direct effect T->Y (fixing M) = 0.50
# Controlled direct effect: fix mediator at reference value.
# -------------------------------------------------------------------

W1_F04_GOLDS = [
    GoldTarget(
        fact_id="W1_F04",
        surface_form_index=i,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id=f"W1_F04_s{i}_gold",
                arms=(
                    QueryArm(label="hi", kind=QueryKind.INTERVENE,
                             values={"T": 1.0, "M": 0.0}),
                    QueryArm(label="lo", kind=QueryKind.INTERVENE,
                             values={"T": 0.0, "M": 0.0}),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE,
                                      ref_arm="lo"),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "T", "outcome": "Y"},
            required_measurement_kind="mean",
            required_comparison_kind="difference",
            required_assertion_polarity="positive",
            required_mediator="M",
        ),
    )
    for i in range(3)
]

# -------------------------------------------------------------------
# W1_F05: Indirect effect T->M->Y = 0.18 (CONTRAST_DIFF)
# 4 arms: total_hi, total_lo, direct_hi, direct_lo
# -------------------------------------------------------------------

_W1_F05_indirect_positive = AtomicSpec(
    spec_id="W1_F05_indirect_gold",
    arms=(
        QueryArm(label="total_hi", kind=QueryKind.INTERVENE,
                 values={"T": 1.0}),
        QueryArm(label="total_lo", kind=QueryKind.INTERVENE,
                 values={"T": 0.0}),
        QueryArm(label="direct_hi", kind=QueryKind.INTERVENE,
                 values={"T": 1.0, "M": 0.0}),
        QueryArm(label="direct_lo", kind=QueryKind.INTERVENE,
                 values={"T": 0.0, "M": 0.0}),
    ),
    measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
    comparison=Comparison(kind=ComparisonKind.CONTRAST_DIFF),
    assertion=Assertion(kind=AssertionKind.POSITIVE),
)

_W1_F05_indirect_lt_direct = AtomicSpec(
    spec_id="W1_F05_lt_direct_gold",
    arms=(
        QueryArm(label="total_hi", kind=QueryKind.INTERVENE,
                 values={"T": 1.0}),
        QueryArm(label="total_lo", kind=QueryKind.INTERVENE,
                 values={"T": 0.0}),
        QueryArm(label="direct_hi", kind=QueryKind.INTERVENE,
                 values={"T": 1.0, "M": 0.0}),
        QueryArm(label="direct_lo", kind=QueryKind.INTERVENE,
                 values={"T": 0.0, "M": 0.0}),
    ),
    measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
    comparison=Comparison(kind=ComparisonKind.CONTRAST_DIFF),
    assertion=Assertion(kind=AssertionKind.LESS_THAN, threshold=0.50),
)

_w1f05_contract = StructuralContract(
    allowed_arm_kinds={"intervene"},
    required_role_vars={"treatment": "T", "outcome": "Y"},
    required_measurement_kind="mean",
    required_comparison_kind="contrast_diff",
    required_assertion_polarity="positive",
    required_mediator="M",
)

W1_F05_GOLDS = [
    # surface 0: "Part of treatment's benefit comes through compliance" — just positive
    GoldTarget(
        fact_id="W1_F05",
        surface_form_index=0,
        status="compile",
        atoms=[_W1_F05_indirect_positive],
        structural_contract=_w1f05_contract,
    ),
    # surface 1: "mediates the relationship" — just positive
    GoldTarget(
        fact_id="W1_F05",
        surface_form_index=1,
        status="compile",
        atoms=[_W1_F05_indirect_positive],
        structural_contract=_w1f05_contract,
    ),
    # surface 2: "positive but smaller than direct" — compound (positive + < 0.50)
    GoldTarget(
        fact_id="W1_F05",
        surface_form_index=2,
        status="compile",
        atoms=[_W1_F05_indirect_positive, _W1_F05_indirect_lt_direct],
        acceptance_rule="all_of",
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "T", "outcome": "Y"},
            required_measurement_kind="mean",
            required_comparison_kind="contrast_diff",
            required_assertion_polarity="positive",
            required_mediator="M",
            n_atoms=2,
        ),
    ),
]

# -------------------------------------------------------------------
# W1_F06: Heterogeneity — effect of T on Y depends on B
# 4 arms conditioned on B high/low + CONTRAST_DIFF
# -------------------------------------------------------------------

_w1f06_arms = (
    QueryArm(label="hi_bhi", kind=QueryKind.INTERVENE,
             values={"T": 1.0},
             condition_on={"B": {"kind": "approx_eq", "value": 1.0}}),
    QueryArm(label="lo_bhi", kind=QueryKind.INTERVENE,
             values={"T": 0.0},
             condition_on={"B": {"kind": "approx_eq", "value": 1.0}}),
    QueryArm(label="hi_blo", kind=QueryKind.INTERVENE,
             values={"T": 1.0},
             condition_on={"B": {"kind": "approx_eq", "value": -1.0}}),
    QueryArm(label="lo_blo", kind=QueryKind.INTERVENE,
             values={"T": 0.0},
             condition_on={"B": {"kind": "approx_eq", "value": -1.0}}),
)

W1_F06_GOLDS = [
    # surface_form 0: "depends on biomarker" (generic heterogeneity)
    GoldTarget(
        fact_id="W1_F06",
        surface_form_index=0,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id="W1_F06_s0_gold",
                arms=_w1f06_arms,
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.CONTRAST_DIFF),
                assertion=Assertion(kind=AssertionKind.GAP_MATERIAL),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "T", "outcome": "Y"},
            required_measurement_kind="mean",
            required_comparison_kind="contrast_diff",
            required_assertion_polarity="gap_material",
            required_modifier="B",
            required_condition_vars={"B"},
        ),
    ),
    # surface_form 1: "high B benefits more" (directional)
    GoldTarget(
        fact_id="W1_F06",
        surface_form_index=1,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id="W1_F06_s1_gold",
                arms=_w1f06_arms,
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.CONTRAST_DIFF),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "T", "outcome": "Y"},
            required_measurement_kind="mean",
            required_comparison_kind="contrast_diff",
            required_assertion_polarity="positive",
            required_modifier="B",
            required_condition_vars={"B"},
        ),
    ),
    # surface_form 2: quantified strata (B=+1 ~1.0, B=-1 ~0.3)
    GoldTarget(
        fact_id="W1_F06",
        surface_form_index=2,
        status="compile",
        atoms=[
            # Atom 1: effect at B=+1 is positive (~1.03)
            AtomicSpec(
                spec_id="W1_F06_s2_bhi_gold",
                arms=(
                    QueryArm(label="hi_bhi", kind=QueryKind.INTERVENE,
                             values={"T": 1.0},
                             condition_on={"B": {"kind": "approx_eq", "value": 1.0}}),
                    QueryArm(label="lo_bhi", kind=QueryKind.INTERVENE,
                             values={"T": 0.0},
                             condition_on={"B": {"kind": "approx_eq", "value": 1.0}}),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE,
                                      ref_arm="lo_bhi"),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
            # Atom 2: effect at B=-1 is positive but smaller (~0.33)
            AtomicSpec(
                spec_id="W1_F06_s2_blo_gold",
                arms=(
                    QueryArm(label="hi_blo", kind=QueryKind.INTERVENE,
                             values={"T": 1.0},
                             condition_on={"B": {"kind": "approx_eq", "value": -1.0}}),
                    QueryArm(label="lo_blo", kind=QueryKind.INTERVENE,
                             values={"T": 0.0},
                             condition_on={"B": {"kind": "approx_eq", "value": -1.0}}),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE,
                                      ref_arm="lo_blo"),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
        ],
        acceptance_rule="all_of",
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "T", "outcome": "Y"},
            required_measurement_kind="mean",
            required_comparison_kind="difference",
            required_assertion_polarity="positive",
            required_modifier="B",
            required_condition_vars={"B"},
            n_atoms=2,
        ),
    ),
]

# -------------------------------------------------------------------
# W1_F03: Compound — "Treatment improves Y AND causes SE"
# surface_form 0 = just T->SE (1 spec)
# surface_form 1-2 = compound T->Y + T->SE (2 specs, all_of)
# -------------------------------------------------------------------

_spec_T_to_Y_positive = AtomicSpec(
    spec_id="W1_F03_TY_gold",
    arms=(
        QueryArm(label="treated", kind=QueryKind.INTERVENE, values={"T": 1.0}),
        QueryArm(label="control", kind=QueryKind.INTERVENE, values={"T": 0.0}),
    ),
    measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
    comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="control"),
    assertion=Assertion(kind=AssertionKind.POSITIVE),
)

_spec_T_to_SE_positive = AtomicSpec(
    spec_id="W1_F03_TSE_gold",
    arms=(
        QueryArm(label="treated", kind=QueryKind.INTERVENE, values={"T": 1.0}),
        QueryArm(label="control", kind=QueryKind.INTERVENE, values={"T": 0.0}),
    ),
    measurement=Measurement(kind=MeasurementKind.MEAN, target="SE"),
    comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="control"),
    assertion=Assertion(kind=AssertionKind.POSITIVE),
)

W1_F03_GOLDS = [
    # surface 0: "Treatment causes side effects" — just T->SE
    GoldTarget(
        fact_id="W1_F03",
        surface_form_index=0,
        status="compile",
        atoms=[_spec_T_to_SE_positive],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "T", "outcome": "SE"},
            required_measurement_kind="mean",
            required_comparison_kind="difference",
            required_assertion_polarity="positive",
        ),
    ),
    # surface 1: "improves outcome but increases side effects" — compound
    GoldTarget(
        fact_id="W1_F03",
        surface_form_index=1,
        status="compile",
        atoms=[_spec_T_to_Y_positive, _spec_T_to_SE_positive],
        acceptance_rule="all_of",
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "T"},
            required_measurement_kind="mean",
            required_comparison_kind="difference",
            required_assertion_polarity="positive",
            n_atoms=2,
        ),
    ),
    # surface 2: same compound structure as surface 1
    GoldTarget(
        fact_id="W1_F03",
        surface_form_index=2,
        status="compile",
        atoms=[_spec_T_to_Y_positive, _spec_T_to_SE_positive],
        acceptance_rule="all_of",
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "T"},
            required_measurement_kind="mean",
            required_comparison_kind="difference",
            required_assertion_polarity="positive",
            n_atoms=2,
        ),
    ),
]

# -------------------------------------------------------------------
# W2_F01: ATE(E->D) = -0.20 (protective)
# -------------------------------------------------------------------

W2_F01_GOLDS = [
    GoldTarget(
        fact_id="W2_F01",
        surface_form_index=i,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id=f"W2_F01_s{i}_gold",
                arms=(
                    QueryArm(label="exposed", kind=QueryKind.INTERVENE,
                             values={"E": 1.0}),
                    QueryArm(label="unexposed", kind=QueryKind.INTERVENE,
                             values={"E": 0.0}),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="D"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE,
                                      ref_arm="unexposed"),
                assertion=Assertion(kind=AssertionKind.NEGATIVE),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "E", "outcome": "D"},
            required_measurement_kind="mean",
            required_comparison_kind="difference",
            required_assertion_polarity="negative",
        ),
    )
    for i in range(3)
]

# -------------------------------------------------------------------
# W2_F02: Crude positive association E,D (observational)
# -------------------------------------------------------------------

W2_F02_GOLDS = [
    GoldTarget(
        fact_id="W2_F02",
        surface_form_index=i,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id=f"W2_F02_s{i}_gold",
                arms=(
                    QueryArm(label="base", kind=QueryKind.BASELINE),
                ),
                measurement=Measurement(
                    kind=MeasurementKind.PARTIAL_CORRELATION,
                    lhs="E",
                    rhs="D",
                    cond_set=(),
                ),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"baseline"},
            required_role_vars={"lhs": "E", "rhs": "D"},
            required_measurement_kind="partial_correlation",
            required_comparison_kind="identity",
            required_assertion_polarity="positive",
        ),
    )
    for i in range(3)
]

# -------------------------------------------------------------------
# W2_F06: Partial corr(E,D|C) is NEGATIVE (Simpson's at corr level)
# -------------------------------------------------------------------

W2_F06_GOLDS = [
    GoldTarget(
        fact_id="W2_F06",
        surface_form_index=i,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id=f"W2_F06_s{i}_gold",
                arms=(
                    QueryArm(label="base", kind=QueryKind.BASELINE),
                ),
                measurement=Measurement(
                    kind=MeasurementKind.PARTIAL_CORRELATION,
                    lhs="E",
                    rhs="D",
                    cond_set=("C",),
                ),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.NEGATIVE),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"baseline"},
            required_role_vars={"lhs": "E", "rhs": "D"},
            required_measurement_kind="partial_correlation",
            required_comparison_kind="identity",
            required_assertion_polarity="negative",
            required_cond_set=("C",),
        ),
    )
    for i in range(2)
]

# -------------------------------------------------------------------
# W2_F11: "Exposure causes disease increase" — FALSE
# Same spec as W2_F01 but assertion=POSITIVE → verdict FALSE
# -------------------------------------------------------------------

W2_F11_GOLDS = [
    GoldTarget(
        fact_id="W2_F11",
        surface_form_index=i,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id=f"W2_F11_s{i}_gold",
                arms=(
                    QueryArm(label="exposed", kind=QueryKind.INTERVENE,
                             values={"E": 1.0}),
                    QueryArm(label="unexposed", kind=QueryKind.INTERVENE,
                             values={"E": 0.0}),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="D"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE,
                                      ref_arm="unexposed"),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "E", "outcome": "D"},
            required_measurement_kind="mean",
            required_comparison_kind="difference",
            required_assertion_polarity="positive",
        ),
    )
    for i in range(2)
]

# -------------------------------------------------------------------
# W3_F05: P->H NOT identifiable (identifiability check)
# -------------------------------------------------------------------

W3_F05_GOLDS = [
    GoldTarget(
        fact_id="W3_F05",
        surface_form_index=i,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id=f"W3_F05_s{i}_gold",
                arms=(
                    QueryArm(label="base", kind=QueryKind.BASELINE),
                ),
                measurement=Measurement(
                    kind=MeasurementKind.IDENTIFIABILITY_CHECK,
                    treatment="P",
                    outcome="H",
                ),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.NOT_IDENTIFIABLE),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"baseline"},
            required_role_vars={"treatment": "P", "outcome": "H"},
            required_measurement_kind="identifiability_check",
            required_comparison_kind="identity",
            required_assertion_polarity="not_identifiable",
        ),
    )
    for i in range(3)
]

# -------------------------------------------------------------------
# W3_F03: Changepoint in Temp->H (SWEEP + PIECEWISE_FIT)
# -------------------------------------------------------------------

W3_F03_GOLDS = [
    GoldTarget(
        fact_id="W3_F03",
        surface_form_index=i,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id=f"W3_F03_s{i}_gold",
                arms=(
                    QueryArm(
                        label="temp_sweep",
                        kind=QueryKind.SWEEP,
                        sweep_var="Temp",
                        sweep_values=(-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5),
                        sweep_base=QueryKind.INTERVENE,
                    ),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="H"),
                comparison=Comparison(kind=ComparisonKind.PIECEWISE_FIT),
                assertion=Assertion(kind=AssertionKind.CHANGEPOINT_EXISTS),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"sweep"},
            required_role_vars={"sweep_var": "Temp", "outcome": "H"},
            required_measurement_kind="mean",
            required_comparison_kind="piecewise_fit",
            required_assertion_polarity="changepoint_exists",
        ),
    )
    for i in range(3)
]

# -------------------------------------------------------------------
# W3_F08: WindSpeed -> H = NULL
# -------------------------------------------------------------------

W3_F08_GOLDS = [
    GoldTarget(
        fact_id="W3_F08",
        surface_form_index=i,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id=f"W3_F08_s{i}_gold",
                arms=(
                    QueryArm(label="hi", kind=QueryKind.INTERVENE,
                             values={"WindSpeed": 1.0}),
                    QueryArm(label="lo", kind=QueryKind.INTERVENE,
                             values={"WindSpeed": -1.0}),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="H"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE,
                                      ref_arm="lo"),
                assertion=Assertion(kind=AssertionKind.NEAR_ZERO),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "WindSpeed", "outcome": "H"},
            required_measurement_kind="mean",
            required_comparison_kind="difference",
            required_assertion_polarity="near_zero",
        ),
    )
    for i in range(3)
]

# ===================================================================
# BATCH 2: Coverage gap targets (new measurement/comparison kinds)
# ===================================================================

# -------------------------------------------------------------------
# W2_F09: ATE(E->D) IS identifiable (positive identifiability)
# Mirrors W3_F05 but with IDENTIFIABLE assertion.
# -------------------------------------------------------------------

W2_F09_GOLDS = [
    GoldTarget(
        fact_id="W2_F09",
        surface_form_index=i,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id=f"W2_F09_s{i}_gold",
                arms=(
                    QueryArm(label="base", kind=QueryKind.BASELINE),
                ),
                measurement=Measurement(
                    kind=MeasurementKind.IDENTIFIABILITY_CHECK,
                    treatment="E",
                    outcome="D",
                ),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.IDENTIFIABLE),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"baseline"},
            required_role_vars={"treatment": "E", "outcome": "D"},
            required_measurement_kind="identifiability_check",
            required_comparison_kind="identity",
            required_assertion_polarity="identifiable",
        ),
    )
    for i in range(2)
]

# -------------------------------------------------------------------
# W1_F09: Treatment increases Var(Y) (VARIANCE measurement)
# Var(Y|do(T=1)) > Var(Y|do(T=0)) due to B*T interaction.
# -------------------------------------------------------------------

W1_F09_GOLDS = [
    GoldTarget(
        fact_id="W1_F09",
        surface_form_index=i,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id=f"W1_F09_s{i}_gold",
                arms=(
                    QueryArm(label="treated", kind=QueryKind.INTERVENE,
                             values={"T": 1.0}),
                    QueryArm(label="control", kind=QueryKind.INTERVENE,
                             values={"T": 0.0}),
                ),
                measurement=Measurement(kind=MeasurementKind.VARIANCE, target="Y"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE,
                                      ref_arm="control"),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "T", "outcome": "Y"},
            required_measurement_kind="variance",
            required_comparison_kind="difference",
            required_assertion_polarity="positive",
        ),
    )
    for i in range(2)  # W1_F09 has 2 surface forms
]

# -------------------------------------------------------------------
# W3_F04: Tail risk — P(H < -1.0 | do(Temp=high)) >> P(H < -1.0 | do(Temp=low))
# TAIL_PROB measurement — first test of this kind.
# -------------------------------------------------------------------

W3_F04_GOLDS = [
    GoldTarget(
        fact_id="W3_F04",
        surface_form_index=i,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id=f"W3_F04_s{i}_gold",
                arms=(
                    QueryArm(label="hi_temp", kind=QueryKind.INTERVENE,
                             values={"Temp": 1.5}),
                    QueryArm(label="lo_temp", kind=QueryKind.INTERVENE,
                             values={"Temp": -1.5}),
                ),
                measurement=Measurement(
                    kind=MeasurementKind.TAIL_PROB,
                    target="H",
                    threshold=-1.0,
                ),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE,
                                      ref_arm="lo_temp"),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "Temp", "outcome": "H"},
            required_measurement_kind="tail_prob",
            required_comparison_kind="difference",
            required_assertion_polarity="positive",
        ),
    )
    for i in range(2)  # W3_F04 has 2 surface forms
]

# -------------------------------------------------------------------
# W2_F04: Indirect effect E->M->D = +0.20 (POSITIVE — opposite sign!)
# Opposite-sign mediation: direct is -0.40, indirect is +0.20.
# Same CONTRAST_DIFF structure as W1_F05 but different world/sign.
# -------------------------------------------------------------------

W2_F04_GOLDS = [
    GoldTarget(
        fact_id="W2_F04",
        surface_form_index=i,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id=f"W2_F04_s{i}_gold",
                arms=(
                    QueryArm(label="total_hi", kind=QueryKind.INTERVENE,
                             values={"E": 1.0}),
                    QueryArm(label="total_lo", kind=QueryKind.INTERVENE,
                             values={"E": 0.0}),
                    QueryArm(label="direct_hi", kind=QueryKind.INTERVENE,
                             values={"E": 1.0, "M": 0.0}),
                    QueryArm(label="direct_lo", kind=QueryKind.INTERVENE,
                             values={"E": 0.0, "M": 0.0}),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="D"),
                comparison=Comparison(kind=ComparisonKind.CONTRAST_DIFF),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "E", "outcome": "D"},
            required_measurement_kind="mean",
            required_comparison_kind="contrast_diff",
            required_assertion_polarity="positive",
            required_mediator="M",
        ),
    )
    for i in range(2)  # W2_F04 has 2 surface forms
]

# -------------------------------------------------------------------
# W1_F07: Severity confounds T->Y (OBSERVE vs INTERVENE)
# Confounding = observational effect ≠ causal effect.
# CONTRAST_DIFF: (E[Y|T=1] - E[Y|T=-1]) - (E[Y|do(T=1)] - E[Y|do(T=-1)])
# Symmetric ±1 values to widen the confounding gap.
# -------------------------------------------------------------------

W1_F07_GOLDS = [
    GoldTarget(
        fact_id="W1_F07",
        surface_form_index=i,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id=f"W1_F07_s{i}_gold",
                arms=(
                    QueryArm(label="obs_hi", kind=QueryKind.OBSERVE,
                             values={"T": 1.0}),
                    QueryArm(label="obs_lo", kind=QueryKind.OBSERVE,
                             values={"T": -1.0}),
                    QueryArm(label="causal_hi", kind=QueryKind.INTERVENE,
                             values={"T": 1.0}),
                    QueryArm(label="causal_lo", kind=QueryKind.INTERVENE,
                             values={"T": -1.0}),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.CONTRAST_DIFF),
                assertion=Assertion(kind=AssertionKind.GAP_MATERIAL),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"observe", "intervene"},
            required_role_vars={"treatment": "T", "outcome": "Y"},
            required_measurement_kind="mean",
            required_comparison_kind="contrast_diff",
            required_assertion_polarity="gap_material",
        ),
    )
    for i in range(3)  # W1_F07 has 3 surface forms
]

# -------------------------------------------------------------------
# W2_F07: Collider bias — {L} is NOT a valid adjustment set for E->D
# IDENTIFIABILITY_CHECK with candidate_adjust_set=("L",).
# L is a collider (E->L<-D); conditioning on it opens a spurious path.
# -------------------------------------------------------------------

W2_F07_GOLDS = [
    GoldTarget(
        fact_id="W2_F07",
        surface_form_index=i,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id=f"W2_F07_s{i}_gold",
                arms=(
                    QueryArm(label="base", kind=QueryKind.BASELINE),
                ),
                measurement=Measurement(
                    kind=MeasurementKind.IDENTIFIABILITY_CHECK,
                    treatment="E",
                    outcome="D",
                    candidate_adjust_set=("L",),
                ),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.NOT_IDENTIFIABLE),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"baseline"},
            required_role_vars={"treatment": "E", "outcome": "D"},
            required_measurement_kind="identifiability_check",
            required_comparison_kind="identity",
            required_assertion_polarity="not_identifiable",
        ),
    )
    for i in range(2)  # W2_F07 has 2 surface forms
]

# -------------------------------------------------------------------
# SQ_F01: "Does treatment affect outcome?" — compileable SQ
# Structurally identical to W1_F01 but formulated as a question.
# First compileable SQ gold (all prior SQ golds are abstention).
# -------------------------------------------------------------------

SQ_F01_GOLDS = [
    GoldTarget(
        fact_id="SQ_F01",
        surface_form_index=i,
        status="compile",
        atoms=[
            AtomicSpec(
                spec_id=f"SQ_F01_s{i}_gold",
                arms=(
                    QueryArm(label="treated", kind=QueryKind.INTERVENE,
                             values={"T": 1.0}),
                    QueryArm(label="control", kind=QueryKind.INTERVENE,
                             values={"T": 0.0}),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE,
                                      ref_arm="control"),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
        ],
        structural_contract=StructuralContract(
            allowed_arm_kinds={"intervene"},
            required_role_vars={"treatment": "T", "outcome": "Y"},
            required_measurement_kind="mean",
            required_comparison_kind="difference",
            required_assertion_polarity="positive",
        ),
    )
    for i in range(3)  # SQ_F01 has 3 surface forms
]

# -------------------------------------------------------------------
# Abstention targets
# -------------------------------------------------------------------

ABSTENTION_GOLDS = [
    # W3_F11: temporal claim
    GoldTarget(
        fact_id="W3_F11",
        surface_form_index=0,
        status="abstain",
        abstain_reason_code="temporal_nonexpressible",
    ),
    # W3_F12: methodological claims
    GoldTarget(
        fact_id="W3_F12",
        surface_form_index=0,
        status="abstain",
        abstain_reason_code="methodological_nonexpressible",
    ),
    GoldTarget(
        fact_id="W3_F12",
        surface_form_index=1,
        status="abstain",
        abstain_reason_code="statistical_nonexpressible",
    ),
    # SQ_F07: optimization questions
    GoldTarget(
        fact_id="SQ_F07",
        surface_form_index=0,
        status="abstain",
        abstain_reason_code="optimization_nonexpressible",
    ),
    GoldTarget(
        fact_id="SQ_F07",
        surface_form_index=1,
        status="abstain",
        abstain_reason_code="optimization_nonexpressible",
    ),
]

# -------------------------------------------------------------------
# All gold targets — registry
# -------------------------------------------------------------------

ALL_GOLD_TARGETS: list[GoldTarget] = (
    # Batch 1: priority targets
    W1_F01_GOLDS
    + W1_F03_GOLDS
    + W1_F04_GOLDS
    + W1_F05_GOLDS
    + W1_F06_GOLDS
    + W2_F01_GOLDS
    + W2_F02_GOLDS
    + W2_F06_GOLDS
    + W2_F11_GOLDS
    + W3_F03_GOLDS
    + W3_F05_GOLDS
    + W3_F08_GOLDS
    # Batch 2: coverage gaps
    + W2_F09_GOLDS
    + W1_F09_GOLDS
    + W3_F04_GOLDS
    + W2_F04_GOLDS
    + W1_F07_GOLDS
    + W2_F07_GOLDS
    + SQ_F01_GOLDS
    # Abstention
    + ABSTENTION_GOLDS
)

# Stats
GOLD_TARGET_COUNT = len(ALL_GOLD_TARGETS)
COMPILE_COUNT = sum(1 for g in ALL_GOLD_TARGETS if g.status == "compile")
ABSTAIN_COUNT = sum(1 for g in ALL_GOLD_TARGETS if g.status == "abstain")
TOTAL_ATOMS = sum(len(g.atoms) for g in ALL_GOLD_TARGETS)
