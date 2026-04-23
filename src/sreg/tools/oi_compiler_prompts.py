"""Shared LLM prompt building blocks for the OI compiler (Flow A and Flow B).

Both compilers (claim-direct via `oi_extraction.compile_claim_direct` and
sub-question via `oi_sq_compiler.compile_sq_to_specs`) share the same
AtomicSpec grammar, the same worked exemplars for the
"controlled regression" ambiguity, and the same abstention contract for
model-dependent claims.

This module centralizes those building blocks so a fix to the grammar or
exemplars propagates to both flows. The blocks here are text-only (no SCM
access), which preserves the Flow A invariant "blind to SCM" — see memory
`project_flow_a_vs_flow_b`.

Flow A and Flow B assemble their *own* system prompts; we do NOT unify
the prompt headers, because Flow A compiles a ClaimCard (verify-truth) and
Flow B compiles a SubQuestionIntent (verify-need). The reusable parts are
the grammar, the exemplars, and the abstention helpers.
"""

from __future__ import annotations

__all__ = [
    "GRAMMAR_REF",
    "CONTROLLED_REGRESSION_EXEMPLARS",
    "TARGETED_RECIPE_EXEMPLARS",
    "ABSTENTION_EXEMPLARS",
    "strip_json_fences",
    "is_explicit_abstention",
]


# ---------------------------------------------------------------------------
# Grammar reference — single source of truth for the AtomicSpec grammar
# ---------------------------------------------------------------------------

GRAMMAR_REF = """
You have a composable verification grammar with 4 pieces:

## QueryArm
Each spec has 1+ arms. Each arm generates data from the SCM.

### Choosing `kind` — what the arm does

Each arm has exactly ONE kind. Pick by answering "what data do I need?":

| kind        | What happens                                       | Uses `values`?        | Uses `condition_on`? | When to pick                          |
|-------------|----------------------------------------------------|-----------------------|----------------------|---------------------------------------|
| `baseline`  | Sample the natural joint distribution              | FORBIDDEN             | FORBIDDEN            | You want the raw joint. No filtering. |
| `condition` | Sample joint + filter by `condition_on`            | FORBIDDEN             | REQUIRED             | Subpopulation / observational filter. |
| `intervene` | do-calculus: sample joint with `values` forced     | REQUIRED (the do set) | optional (post-do filter) | "What if we set X to this value?"   |
| `adjust`    | do-calculus on `treatment`, marginal over backdoor | REQUIRED (the do set) | forbidden            | Causal effect of `treatment` on `outcome`. |
| `observe`   | LEGACY — sample joint + filter by values OR cond   | legacy conditioning   | optional             | DEPRECATED. Use `condition` instead.  |
| `sweep`     | Repeat `sweep_base` across a range of values       | n/a (uses sweep_*)    | optional             | Dose-response / continuous variation. |

### Field reference

- `label`: unique name for this arm within the spec (e.g. "baseline",
  "treated", "control"). Used by `comparison.ref_arm`.
- `values`: dict of variable→value. Semantics depend on `kind`:
  * `intervene` / `adjust` / `sweep_base=intervene`: the do-intervention
    set (e.g. {"X": 1.0} means `do(X=1.0)`).
  * `observe` (LEGACY ONLY): acts as approx-equal conditioning. Do NOT
    use on new specs — use `condition_on` for clarity.
  * `baseline` / `condition`: FORBIDDEN. The validator rejects these
    combinations because they used to be silently dropped. To filter a
    baseline, use `kind=condition` with `condition_on`.
- `condition_on`: dict mapping variable name to a condition predicate.
  Available predicates:
  * Point value (shorthand): just a number, e.g. {"X": 5.0}
    Matches rows where X is approximately 5.0 (within 15% of std).
  * range: {"kind": "range", "lo": <number>, "hi": <number>}
    Matches rows where lo <= variable <= hi.
    Example: near a cutoff: {"eligibility_gap": {"kind": "range", "lo": -1000, "hi": 1000}}
  * quantile_range: {"kind": "quantile_range", "q_lo": <0-1>, "q_hi": <0-1>}
    Matches rows in the given quantile range of the variable's distribution.
    Example: bottom quartile: {"income": {"kind": "quantile_range", "q_lo": 0.0, "q_hi": 0.25}}
  * in_set: {"kind": "in_set", "values": [<value>, ...]}
    Matches rows where variable equals any listed value.
    Example: categorical: {"region": {"kind": "in_set", "values": ["urban", "suburban"]}}
- `treatment`: variable to intervene on (REQUIRED for `adjust` kind).
- `outcome`: variable whose post-intervention distribution is sampled
  (REQUIRED for `adjust` kind).
- `adjust_set`: DO NOT specify. The verifier auto-computes a valid
  backdoor adjustment set from the SCM DAG whenever `adjust_set` is
  omitted or empty. Your job for adjust arms is only to pick
  `treatment`, `outcome`, the intervention `values`, and the arm count
  (2 arms for causal differences). If no valid backdoor set exists in
  the DAG for your chosen (`treatment`, `outcome`) pair, the verifier
  reports that cleanly — you do not need to pre-check identifiability.

### Decision rule: baseline vs condition vs intervene vs adjust

- Does the claim describe an intervention (do-calculus, "if we set X",
  "raising X"), a counterfactual, or a causal effect? → `intervene` or
  `adjust`. Use `adjust` when you need to block backdoor paths (causal
  effect estimation); use `intervene` when you want the post-intervention
  joint for further measurement (e.g. `tail_prob` after do).
- Does the claim describe the natural joint with NO filter (a raw mean,
  a marginal correlation)? → `baseline`.
- Does the claim describe a subpopulation in the natural joint
  ("among patients with X in range R", "for the bottom quartile of Z")?
  → `condition` with `condition_on`.
- Never pick `observe` for new specs. It is retained for legacy tests;
  the same semantics are expressible via `condition` with `condition_on`.

## Adjust arm semantics — read this carefully

`adjust` is NOT observational regression with controls. It is do-calculus.
The verifier asks the SCM oracle for the post-intervention distribution
of `outcome` under `do(treatment=value)`. Back-door paths are blocked by
a backdoor set that the verifier computes from the SCM DAG — you do not
specify it. The arm emits a **1-D array of `outcome` samples only**.
The joint distribution is collapsed to the marginal-under-intervention,
so multivariate quantities cannot be recomputed from it.

What this means for measurements paired with an adjust arm:
- ALLOWED: `mean`, `variance`, `quantile`, `tail_prob` on `outcome` —
  anything that operates on a single 1-D series.
- FORBIDDEN: `correlation`, `partial_correlation` — these need multiple
  variables or the joint distribution, which the adjust arm has thrown
  away. The validator will reject the spec.

**Common phrasings that look like they need `adjust + partial_correlation`
but actually do not:**
- "the effect of T on Y after adjusting for W" → causal claim. Use TWO
  adjust arms (e.g. `do(T=0)` and `do(T=1)`) + `measurement.kind=mean`
  on `outcome=Y` + `comparison.kind=difference` with `ref_arm=` the
  control arm. Do NOT specify `adjust_set` — the verifier computes the
  backdoor set from the SCM DAG.
- "T is associated with Y controlling for W" → observational claim. Do
  NOT use `adjust`. Use a single `baseline` arm +
  `measurement.kind=partial_correlation` with `lhs=T`, `rhs=Y`,
  `cond_set=(W,)` + `comparison.kind=identity`.
- The same surface phrase ("after controlling for W") can map to either
  pattern. Pick based on whether the claim is about `do(T)` (causal,
  use adjust+mean+difference) or about correlation in the natural joint
  distribution (observational, use baseline+partial_correlation).

## Measurement
What to compute from the sampled data.
- kind: "mean", "variance", "correlation", "partial_correlation",
  "tail_prob", "prob", "quantile", "identifiability_check"
- target: variable name for mean/variance/quantile/tail_prob
- lhs, rhs: variable names for correlation/partial_correlation
- cond_set: tuple of variables to condition on (for partial_correlation)
- treatment, outcome: for identifiability_check
- threshold: for tail_prob
- q: quantile level (0-1) for quantile
- COMPATIBILITY: `correlation` and `partial_correlation` cannot be paired
  with arms of `kind=adjust` (adjust arms only carry 1-D outcome samples
  — see "Adjust arm semantics" above).

## Comparison
How to relate measurements across arms.
- kind: "identity" (single arm, just check the value),
  "difference", "ratio", "ranking" (rank multiple arms),
  "gap" (check minimum gap), "contrast_diff"
- ref_arm: REQUIRED for difference/ratio. The reference (baseline/control) arm.
  Formula: difference = other_arm - ref_arm. ratio = other_arm / ref_arm.
  Example: to test "treatment increases Y", set ref_arm to the control arm.
  If other_arm > ref_arm, difference is positive.
- order: tuple of arm labels for ranking
- tolerance: float (default 0.05)
- RULE: difference and ratio require EXACTLY 2 arms and ref_arm must be set.

## Assertion
What should be true about the comparison result.
- kind: "positive", "negative", "near_zero", "greater_than", "less_than",
  "rank_order", "identifiable", "not_identifiable",
  "changepoint_exists", "sign_flip", "gap_material",
  "distinguishable", "not_distinguishable"
- threshold: numeric threshold (default 0.0)
- tolerance: float (default 0.05)
- order: tuple of arm labels for rank_order

## AtomicSpec structure
{
  "spec_id": "unique_id",
  "arms": [{"label": "...", "kind": "...", ...}],
  "measurement": {"kind": "...", ...},
  "comparison": {"kind": "...", ...},
  "assertion": {"kind": "...", ...}
}

IMPORTANT RULES:
- ALL variable names must come from the provided Variables list.
- Do NOT reference derived or constructed variables. Use predicates on existing
  world variables instead. E.g., instead of a variable "eligible", use
  {"eligibility_gap": {"kind": "range", "lo": -1000, "hi": 1000}}.
- Each spec checks ONE atomic fact.
- For partial_correlation with empty cond_set, it computes raw correlation.
- "baseline" arms sample from the joint distribution (no intervention);
  they must NOT set `values` or `condition_on`.
- "condition" arms filter the joint and must use `condition_on` ONLY
  (not `values`). The validator rejects `kind=condition` with `values`.
- ONE condition predicate per variable in condition_on.
- Do NOT condition on a variable already set in `values` on the same arm
  (intervening on X and then conditioning on X is self-contradictory).
- Return a JSON array of spec objects.
"""


# ---------------------------------------------------------------------------
# Controlled-regression exemplars — route A (causal) vs route B (observational)
# ---------------------------------------------------------------------------
#
# The single most common compiler failure mode: the surface phrase "after
# adjusting for W" / "controlling for W" maps to two semantically distinct
# routes (causal-via-do-calculus vs observational-via-partial-correlation),
# and without this exemplar block the compiler historically collapsed both
# into the invalid `adjust + partial_correlation` hybrid. Each exemplar
# shows ONE valid route end-to-end.

CONTROLLED_REGRESSION_EXEMPLARS = """
## Worked examples — "controlled regression" phrasings

These two examples cover the single most common ambiguity. The same
surface phrase ("adjusting for W", "controlling for W") can mean two
different things. Pick the route by asking: is the claim about a
do-intervention on T, or about a correlation in the natural joint?

### Example A — causal claim ("does T causally raise Y after adjusting for W?")

Pattern: TWO `adjust` arms (one per treatment level) +
`measurement.kind=mean` on the outcome + `comparison.kind=difference`
with `ref_arm` set to the control arm.

Example sub-question: "After adjusting for confounder W, does increasing
T raise Y?"

Spec:
[
  {
    "spec": {
      "spec_id": "causal_T_on_Y_adjusted_W",
      "arms": [
        {
          "label": "treated",
          "kind": "adjust",
          "treatment": "T",
          "outcome": "Y",
          "values": {"T": 1.0}
        },
        {
          "label": "control",
          "kind": "adjust",
          "treatment": "T",
          "outcome": "Y",
          "values": {"T": 0.0}
        }
      ],
      "measurement": {"kind": "mean", "target": "Y"},
      "comparison": {"kind": "difference", "ref_arm": "control"},
      "assertion": {"kind": "positive"}
    },
    "role": "required"
  }
]

Why this works: each adjust arm asks the SCM oracle for `E[Y | do(T=t)]`.
The verifier computes a valid backdoor adjustment set from the SCM DAG
(W in this case) — you do not specify it. The means are scalars; the
difference compares two scalars. The validator accepts `adjust + mean`.

### Example B — observational claim ("is T associated with Y controlling for W?")

Pattern: ONE `baseline` arm +
`measurement.kind=partial_correlation` with `lhs=T`, `rhs=Y`,
`cond_set=(W,)` + `comparison.kind=identity`.

Example sub-question: "Holding W constant, is T positively correlated
with Y in the natural joint distribution?"

Spec:
[
  {
    "spec": {
      "spec_id": "obs_pcor_T_Y_given_W",
      "arms": [
        {
          "label": "joint",
          "kind": "baseline"
        }
      ],
      "measurement": {
        "kind": "partial_correlation",
        "lhs": "T",
        "rhs": "Y",
        "cond_set": ["W"]
      },
      "comparison": {"kind": "identity"},
      "assertion": {"kind": "positive"}
    },
    "role": "required"
  }
]

Why this works: the baseline arm samples the natural joint distribution
(no intervention). `partial_correlation` reads multiple variables from
that joint, conditioning on W. The validator accepts
`baseline + partial_correlation`.

### Disambiguation rule

- Words signaling causation (causes, effect of, raises, reduces,
  intervention, would happen if, even after intervening): use route A.
- Words signaling association in the natural distribution (associated
  with, correlated with, partial correlation, residual association):
  use route B.
- If the surface phrase does NOT clearly signal causation, do not
  assume causal by default. Lean toward route B (observational) — it
  is the safer interpretation for descriptive or associational
  language. Pick route A only when the wording explicitly references
  intervention, effect-of, or counterfactual reasoning.
- If neither route fits cleanly — e.g. the claim is about a
  model-output number rather than a world-defined quantity — abstain
  by returning [] per the abstention contract above.
- NEVER mix `adjust` arms with `partial_correlation` measurements.
"""


# ---------------------------------------------------------------------------
# Targeted recipe exemplars — patterns with the highest failure rate in Suite 2
# ---------------------------------------------------------------------------
#
# These recipes target the next three biggest failure modes after the
# adjust/partial_correlation split:
#   1. Confounding detection (CC-A5) — gap between do(T) and observe(T=t).
#   2. Anti-adjust-swap (CC-A1, CC-D1) — do-calculus is `intervene`, not
#      `adjust`, unless the claim explicitly needs backdoor blocking.
#   3. Assertion polarity (CC-A7, SQ-A1) — "reduces" → negative,
#      "increases" → positive, "no effect" → near_zero, paired with the
#      correct `ref_arm`.
# Strategy evidence: `research/synthesis/suite2_compiler_improvement_strategy.md`
# §8.3 and §7.11 estimate these three recipes target 37/55 (67%) of Suite 2.

TARGETED_RECIPE_EXEMPLARS = """
## Targeted recipes — high-impact patterns

Three recipes that cover the most frequent compile errors in Suite 2.
Use them as a lookup when the claim surface matches.

### Recipe C — Confounding detection (gap between causal and observational)

When to use: the claim names a confounder or asks about "how much of the
association between T and Y is due to confounder W", "the observed
association is inflated by W", "does adjusting for W move the estimate".

Shape: TWO arms at the same treatment level — one `condition` (the
naive observational estimate), one `intervene` (the causal estimate) —
plus `measurement.kind=mean` on the outcome, plus
`comparison.kind=difference`. The difference between the arms IS the
confounding bias. Assertion is `positive`/`negative` when the claim
gives a direction, or `near_zero` if the claim is "no confounding".

Example claim: "The observed association between T and Y is inflated
upward by confounder W — without adjustment, we overestimate the effect."

Spec:
[
  {
    "spec_id": "confounding_gap_T_Y",
    "arms": [
      {"label": "obs",    "kind": "condition", "condition_on": {"T": 1.0}},
      {"label": "causal", "kind": "intervene", "values":       {"T": 1.0}}
    ],
    "measurement": {"kind": "mean", "target": "Y"},
    "comparison": {"kind": "difference", "ref_arm": "causal"},
    "assertion": {"kind": "positive"}
  }
]

Why this works: `condition_on: {"T": 1.0}` filters the natural joint
to rows where T ≈ 1.0 (auto-promoted to an `approx_eq` predicate) —
this is the naive "observed when T=1" estimate that is biased by
confounders. `intervene` forces `do(T=1.0)` (the causal mean, free of
backdoor bias). Their difference is exactly the confounding bias.
If the claim says the naive estimate is inflated upward, the
difference `obs - causal` is positive, so assertion = `positive`.

### Disambiguation — Example A vs Example B vs Recipe C

All three routes handle "control for W" phrasings and must not be
confused with each other. The claim language picks the route:

- "residual association of T with Y holding W constant" or
  "T is correlated with Y controlling for W" → **Example B** (baseline
  + `partial_correlation` with `cond_set=(W,)` + `identity`). This
  tests association in the natural joint after partialling out W.
- "causal effect of T on Y after adjusting for W" or "the do-effect of
  T on Y net of W" → **Example A** (two `adjust` arms + `mean` +
  `difference`). This tests the SCM-level causal effect using the
  verifier-derived backdoor adjustment.
- "the observed association is inflated by W" or "without adjusting we
  overestimate the effect" or "the naive estimate differs from the
  causal one" → **Recipe C** (`condition` + `intervene` at the same
  level + `mean` + `difference`). This tests the gap between naive
  and causal at one treatment level — i.e. the confounding bias
  itself, not the corrected effect.

For "the association/effect is inflated by W across all treatment
levels", Recipe C is too narrow (it tests one level). Use either
Example B (if the claim is about the *residual* post-W association) or
extend Recipe C to 4 arms with `comparison.kind=contrast_diff` (naive
vs causal at two treatment levels). Prefer Example B when the text is
purely associational; prefer the extended Recipe C only when the
claim explicitly pits observed against causal.

### Recipe D — Do-calculus is `intervene`, not `adjust`

When to use: the claim says "do(T)", "if we set T to a value",
"intervening on T", "raising T to level X". This is a simple
do-intervention, not a backdoor adjustment problem.

Shape: ONE or TWO `intervene` arms (never `adjust`), plus the
corresponding measurement. For causal effects between two levels, use
two `intervene` arms + `difference`. For a single intervention's
tail/quantile/probability, use one `intervene` arm + `identity`.

Use `adjust` ONLY when ALL THREE hold:
- The claim explicitly requires blocking backdoor paths to isolate the
  causal effect (e.g. "causal effect after controlling for W on the
  data-generating process", or the SCM has a known confounder the
  claim is reasoning around).
- The measurement is a 1-D summary of the outcome (`mean`,
  `variance`, `quantile`, `tail_prob`) — `adjust` emits only outcome
  samples, never the joint.
- The claim is about the SCM-level causal effect, not a correlation
  or a distribution comparison.

When in doubt, pick `intervene`. Default to `adjust` only when the
text makes backdoor adjustment explicit.

### Recipe E — Assertion polarity: match the claim direction

The `assertion.kind` and the `ref_arm` choice together encode the
direction of the claim. Get either wrong and a claim that SHOULD pass
will fail.

Rules:
- "X increases Y", "X raises Y", "higher X leads to more Y" → arms
  are (high_X, low_X); `ref_arm = low_X`; assertion = `positive`.
- "X decreases Y", "X reduces Y", "higher X means less Y" → arms are
  (high_X, low_X); `ref_arm = low_X`; assertion = `negative`.
- "X has no effect on Y", "X does not affect Y", "null association" →
  assertion = `near_zero` regardless of arm ordering.
- "X produces at least K units more Y than baseline" → assertion =
  `greater_than` with `threshold=K`.

Formula to remember: `difference = other_arm - ref_arm`. If the claim
says "the treatment arm has MORE Y than control", then with
`ref_arm=control` the difference is positive, so assertion=`positive`.

Contra-intuitive claim example: "Doubling T actually reduces Y (the
effect is negative despite the common assumption)." Arms are
(T_double, T_base); `ref_arm = T_base`; assertion = `negative`. Do NOT
default to positive — the claim text overrides the "more is more"
prior.

### Recipe F — Quantitative-magnitude commitments

When a claim asserts a specific effect size or ratio ("T doubles Y",
"halves the risk", "at least a 20% increase", "changes Y by a factor of
two"), the assertion must bind that magnitude. A generic `positive`
assertion passes even when Y moves by 0.1% — which does not verify
"doubling".

Use:
- "X doubles Y" / "X halves Y" → `comparison.kind=ratio` + assertion
  `greater_than` / `less_than` with a numeric `threshold` (e.g. 1.8 or
  0.6, leaving a tolerance band). Never `positive` alone.
- "X increases Y by at least K units" → `comparison.kind=difference`
  + assertion `greater_than` with `threshold=K`.
- "X reduces Y by at least K%" → `comparison.kind=ratio` + assertion
  `less_than` with `threshold=1 - K/100`.
- "X has a large effect on Y" (unquantified) → prefer
  `difference` + `greater_than` with an SCM-reasonable `threshold` if
  you can pick one from the variable anchors; otherwise abstain.

### Recipe G — Mediation: total vs direct effect via contrast_diff

**Scope first — which of two sub-patterns does the claim need?**

The contrast_diff 4-arm pattern below is ONLY correct when the claim
asks about INDIRECT effect magnitude OR explicitly COMPARES total to
direct (e.g. "indirect is smaller than direct", "most of the effect is
indirect", "direct effect dwarfs indirect"). For those, you need two
contrasts and a contrast_diff comparison — see the 4-arm pattern below.

For the SIMPLER claim "T has a direct effect on Y beyond (its effect
through) M" / "the direct causal effect of T on Y holding M constant"
/ "the controlled direct effect of T on Y at M=m is X", use the
**Recipe G-simple** 2-arm pattern:

```json
{
  "spec_id": "direct_effect_T_on_Y_at_M_fixed",
  "arms": [
    {"label": "treated_fixed_M", "kind": "intervene",
     "values": {"T": 1.0, "M": 0.0}},
    {"label": "control_fixed_M", "kind": "intervene",
     "values": {"T": 0.0, "M": 0.0}}
  ],
  "measurement": {"kind": "mean", "target": "Y"},
  "comparison": {"kind": "difference", "ref_arm": "control_fixed_M"},
  "assertion": {"kind": "positive"}
}
```

This is literally the controlled direct effect (CDE) at M=m, and it
answers the claim without needing the 4-arm contrast. Do NOT reach for
4-arm contrast_diff when a simple 2-arm with M clamped is enough.

**4-arm contrast_diff pattern (Recipe G proper):**

Use this ONLY when the claim makes an explicit total-vs-direct or
total-vs-indirect comparison.

Pattern:
- Arms: 4 arms.
  * `intervene[total_hi]`: `values={T: hi}` (no mediator constraint).
  * `intervene[total_lo]`: `values={T: lo}`.
  * `intervene[direct_hi]`: `values={T: hi, M: m_star}` (clamp mediator).
  * `intervene[direct_lo]`: `values={T: lo, M: m_star}` (same clamp).
- `measurement.kind = mean` on the outcome Y.
- `comparison.kind = contrast_diff` with `order=[total_hi, total_lo,
  direct_hi, direct_lo]` and `min_gap` left at default unless the claim
  quantifies the gap.
- Assertion picks the claim direction: `positive` if indirect effect is
  positive; `less_than` if "indirect effect is smaller than direct"; etc.

Example — "The indirect effect of T on Y through M is positive but
smaller than the direct effect":

```json
{
  "spec_id": "indirect_effect_T_on_Y_via_M",
  "arms": [
    {"label": "total_hi", "kind": "intervene", "values": {"T": 1.0}},
    {"label": "total_lo", "kind": "intervene", "values": {"T": 0.0}},
    {"label": "direct_hi", "kind": "intervene",
     "values": {"T": 1.0, "M": 0.5}},
    {"label": "direct_lo", "kind": "intervene",
     "values": {"T": 0.0, "M": 0.5}}
  ],
  "measurement": {"kind": "mean", "target": "Y"},
  "comparison": {"kind": "contrast_diff",
                 "order": ["total_hi", "total_lo", "direct_hi", "direct_lo"]},
  "assertion": {"kind": "less_than", "threshold": 0.0}
}
```

Emit two specs if the claim makes two assertions ("indirect is positive
AND smaller than direct"): one with `assertion=positive` and another
with `assertion=less_than`.

When to use Recipe G: any claim with "direct effect", "indirect effect",
"effect through M", "controlling for the mediator M", "the part of the
effect that goes via M", or "the effect not mediated by M".

When NOT to use Recipe G: if the claim just says "causal effect of T on
Y controlling for W" where W is a CONFOUNDER (not a mediator), use
Example A (intervene + adjust_set=[W], NOT contrast_diff). Confounders
are adjusted away; mediators are clamped and contrasted.

### Recipe J — Changepoint / threshold / piecewise dose-response

When a claim asserts a THRESHOLD, a CHANGEPOINT, a KINK, a SHARP
CHANGE, or that the dose-response slope changes at some value, do NOT
try to verify with two `intervene` arms. You need a continuous sweep
across the treatment range and a piecewise-fit comparison.

Pattern:
- Arms: exactly 1 arm with `kind=sweep`.
  * `sweep_var`: the continuous treatment / input variable.
  * `sweep_values`: a grid spanning the claim's region of interest
    (e.g. `[-2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0]` for a
    threshold near zero). Include values on BOTH sides of the
    hypothesized changepoint.
  * `sweep_base`: `intervene` (we want the causal dose-response, not
    the observational one) unless the claim is explicitly
    observational.
- `measurement.kind`: `mean` on the outcome variable.
- `comparison.kind`: `piecewise_fit`. (Piecewise_fit lives on
  `Comparison`, NOT on `Measurement`. The verifier fits a two-segment
  piecewise linear model across the sweep and reports detected
  changepoint + per-segment slopes.)
- `assertion.kind`: `changepoint_exists`. The assertion passes iff the
  piecewise fit detects a significant changepoint in the sweep range.

Example — "The effect of temperature on health changes sharply at a
threshold near zero: mild below, severe above":

```json
{
  "spec_id": "temperature_health_changepoint_near_zero",
  "arms": [
    {"label": "temp_sweep",
     "kind": "sweep",
     "sweep_var": "Temp",
     "sweep_values": [-2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0],
     "sweep_base": "intervene"}
  ],
  "measurement": {"kind": "mean", "target": "H"},
  "comparison": {"kind": "piecewise_fit"},
  "assertion": {"kind": "changepoint_exists"}
}
```

When to use Recipe J: any claim mentioning "threshold", "changepoint",
"kink", "sharp change", "turns severe above X", "dose-response curve
bends", "effect changes at [value]", or a piecewise / segmented
functional form.

When NOT to use Recipe J: if the claim just says "T has a larger
effect when Z is high" (heterogeneity, not a changepoint in T itself),
use 2+ `intervene` arms with `condition_on={Z: ...}` and a `difference`
/ `gap` comparison. Recipe J is specifically for a changepoint in the
sweep variable itself, not conditional heterogeneity.

### Escape hatches to avoid — wrong → right exemplars

This section names three escape hatches the compiler keeps reaching for
when a claim is genuinely causal. Each row shows a failing example and
the replacement that verifies.

**1. `condition` is NOT a drop-in for `intervene` on treatment labels.**

A claim like "treated patients show more variable outcomes than
untreated patients" sounds observational because of "patients show",
but the causal quantity is interventional (variance of the potential
outcome under do(T=1) vs do(T=0)). Conditioning on T leaks confounder
selection.

```text
Claim: "Treated patients show more variable outcomes than untreated."

WRONG:
  arms: [condition{T: 1.0}, condition{T: 0.0}]  # leaks selection
  measurement: variance(Y)
  comparison: difference
  assertion: positive

RIGHT:
  arms: [intervene{T: 1.0} as "treated",
         intervene{T: 0.0} as "control"]
  measurement: variance(Y)
  comparison: difference (ref_arm=control)
  assertion: positive
```

Rule: if the claim uses "treated/untreated", "dosed/undosed",
"exposed/unexposed" and there is a clear treatment variable in the
world anchors, use `intervene`. Use `condition` only when the claim
says "among X-level patients", "in the subgroup with Z", or other
subgroup language that does NOT equate to a causal contrast.

**2. `distinguishable` is NEVER the assertion for "X causes Y".**

Claims like "treatment causes side effects", "exposure raises disease
risk", "T reduces Y" have a definite sign. Falling back to
`distinguishable` passes accidentally whenever the effect is non-zero,
losing the polarity check.

```text
Claim: "Treatment causes side effects."

WRONG:
  arms: [intervene{T: 1.0}, intervene{T: 0.0}]
  measurement: mean(SE)
  comparison: difference
  assertion: distinguishable  # passes if |diff| > eps regardless of sign

RIGHT:
  arms: [intervene{T: 1.0} as "treated",
         intervene{T: 0.0} as "control"]
  measurement: mean(SE)
  comparison: difference (ref_arm=control)
  assertion: positive  # side-effects claim implies MORE, not just different
```

Rule: "causes", "produces", "raises", "reduces", "increases", "decreases",
"leads to" all imply a sign. Use `positive`/`negative`. Reserve
`distinguishable` for explicit identifiability language like "can we
distinguish effect A from effect B".

**3. `partial_correlation` is NOT the tool for collider-bias or
identifiability claims.**

Claims like "adjusting for the collider introduces bias", "the effect
is identifiable from observational data", "conditioning on Z unblocks a
non-causal path" are about the *structure* of identifiability, not
about a numerical partial correlation on one sample.

```text
Claim: "Adjusting for the collider variable introduces bias in the
        exposure-disease estimate."

WRONG:
  arms: [baseline]
  measurement: partial_correlation(E, D | Z)
  comparison: identity
  assertion: not_distinguishable  # conflates sign with identification

RIGHT:
  arms: [baseline]
  measurement: identifiability_check(
                 treatment=E, outcome=D,
                 candidate_adjust_set=[Z])
  comparison: identity
  assertion: not_identifiable  # adjusting on a collider breaks id
```

```text
Claim: "The causal effect of exposure on disease is identifiable from
        observational data, given that we can measure the confounder W."

WRONG:
  arms: [baseline]
  measurement: partial_correlation(E, D | W)
  comparison: identity
  assertion: distinguishable

RIGHT:
  arms: [baseline]
  measurement: identifiability_check(
                 treatment=E, outcome=D,
                 candidate_adjust_set=[W])
  comparison: identity
  assertion: identifiable
```

Rule: if the claim names "identifiable", "identification",
"observational data", "backdoor", "collider", or asks whether an effect
can be recovered at all, use `identifiability_check` +
`identifiable`/`not_identifiable`. Do NOT substitute `partial_correlation`
+ `distinguishable`; they answer different questions and lose the
structural content.

**4. "What is the causal effect?" asks for ATE magnitude, not identifiability.**

A question like "What is the causal effect of X on Y?" is asking for
the average treatment effect E[Y|do(X=hi)] - E[Y|do(X=lo)], NOT whether
it's identifiable. The identifiability question uses the word
"identifiable" or "can we estimate / recover" — not "what is".

```text
Claim: "What is the causal effect of treatment on patient outcomes?"

WRONG:
  arms: [baseline]
  measurement: identifiability_check(treatment=T, outcome=Y)
  comparison: identity
  assertion: identifiable  # wrong: the question asks MAGNITUDE

RIGHT:
  arms: [intervene{T: 1.0} as "treated",
         intervene{T: 0.0} as "control"]
  measurement: mean(Y)
  comparison: difference (ref_arm=control)
  assertion: distinguishable  # sign unspecified; existence-only check
```

Rule: "what is the causal effect" / "what is the ATE" / "how much does
X affect Y" all ask for magnitude. Use 2-arm intervene + mean +
difference + `distinguishable` (if sign not committed in claim) or
`positive`/`negative` (if claim commits to sign).

**4b. Per-unit effect claims need UNIT intervention, not sub-unit.**

Claims like "the causal effect of T on Y is approximately 0.5" or "per
unit increase in X, Y rises by 0.3" specify an effect size PER UNIT of
the treatment. To test against a per-unit coefficient, the intervention
contrast must span ONE UNIT of the treatment: `T=1.0` vs `T=0.0`, or
equivalently `T=0.5` vs `T=-0.5`. Using `T=0.5` vs `T=0.0` measures a
HALF-UNIT effect and will report half the claimed magnitude.

```text
Claim: "The direct causal effect of treatment on outcome, controlling
        for compliance, is approximately 0.5."

WRONG:
  arms: [intervene{T: 0.5, M: 0.0}, intervene{T: 0.0, M: 0.0}]
  measurement: mean(Y)
  comparison: difference
  assertion: greater_than threshold=0.45  # measures 0.5 * 0.5 = 0.25, fails

RIGHT:
  arms: [intervene{T: 1.0, M: 0.0}, intervene{T: 0.0, M: 0.0}]
  measurement: mean(Y)
  comparison: difference (ref_arm=control_fixed_M)
  assertion: greater_than threshold=0.45  # measures a full unit change
```

Rule: when the claim names a specific effect magnitude ("~X", "by X
units", "per unit"), the intervention contrast span MUST be 1 unit
(not 0.5, not a partial step). Default to `hi=1.0, lo=0.0` or
`hi=0.5, lo=-0.5` for any per-unit numeric commitment.

**5. `tail_prob(Y, threshold)` measures P(Y > threshold). Read direction carefully.**

The grammar's `tail_prob(target, threshold)` returns the probability
that the target variable is ABOVE the threshold. For claims about
"probability below threshold" or "probability of poor outcome", the
mapping to `tail_prob` + assertion sign depends on the threshold's
polarity:

```text
Claim: "The probability of health falling BELOW a critical threshold
        is much HIGHER at elevated temperatures than at low temperatures."

(H is health; higher H = better. threshold < typical H = "falls below".)

Analysis:
  P(H < thresh | hi_temp) > P(H < thresh | lo_temp)
  ⇔ P(H > thresh | hi_temp) < P(H > thresh | lo_temp)  (complements)
  ⇔ tail_prob(H, thresh) at hi_temp < tail_prob(H, thresh) at lo_temp
  ⇔ difference (hi - lo) is NEGATIVE

WRONG:
  arms: [intervene{Temp: 1.5}, intervene{Temp: -1.5}]
  measurement: tail_prob(H, threshold=-1.0)
  comparison: difference
  assertion: positive  # reading "higher at elevated" as positive

RIGHT:
  arms: [intervene{Temp: 1.5}, intervene{Temp: -1.5}]
  measurement: tail_prob(H, threshold=-1.0)
  comparison: difference (ref_arm=lo_temp)
  assertion: negative  # tail_prob above-threshold drops at hi_temp
```

Rule: when claim mentions "below threshold", "poor outcome", or
"worst cases" and you reach for `tail_prob`, flip the assertion sign
if the claim's direction contradicts tail_prob's "above" semantics.
Use the equivalence `P(Y<k) = 1 - P(Y>k)` to translate direction.
Always use `comparison.kind=difference` for 2-arm tail_prob
comparisons, NOT `identity` (identity compares a single value to a
constant, not two arms).

### Other escape hatches

- `correlation` / `partial_correlation` are NOT fallback assertions for
  causal or quantitative claims. If the claim mentions "causes", "raises",
  "reduces", or a specific magnitude, reach for `intervene`/`adjust`
  arms + `mean` + `difference`/`ratio`. Correlation is for genuinely
  associational language.
- `identity` with no arms to compare is a red flag: a single-arm
  `mean` + `identity` is only meaningful for claims about a specific
  scalar ("the mean of Y is X"). For claims about relationships
  between arms, always use `difference` or `ratio`.
"""


# ---------------------------------------------------------------------------
# Abstention exemplars — model-dependent quantities the grammar cannot express
# ---------------------------------------------------------------------------
#
# The grammar's ground truth is the SCM oracle: only world-defined quantities
# (interventional means/quantiles, observational correlations and partial
# correlations, identifiability) are verifiable. Statistical-model outputs
# (regression coefficients, standardized betas, R-squared, AIC, mixed-effects
# variance components) depend on analyst choices, not on the SCM, so the
# verifier cannot ground truth them. The compiler must abstain on those
# claims rather than approximate them with a hybrid spec.
#
# Beyond model-dependent quantities, several other claim categories cannot
# be verified against the SCM oracle and must also abstain: temporal/lag
# claims (the SCM is atemporal), methodological/study-design claims
# (the SCM is a data-generating process, not a study protocol), statistical
# power/sample-size claims (the SCM does not define analyst sample budgets),
# and open-ended optimization claims without a defined objective.

ABSTENTION_EXEMPLARS = """
## Abstention — when to return an empty array

If the claim asks for a quantity that cannot be grounded against the SCM
oracle, you must ABSTAIN by returning an empty JSON array: []

The grammar can verify properties of the SCM:
- interventional means / variances / quantiles / tail probabilities
- observational correlations and partial correlations
- identifiability of an effect

The grammar CANNOT verify the following categories:

### 1. Model-output numbers (depend on analyst-chosen model, not the SCM)
- OLS / GLS / robust / ridge regression coefficients
- standardized betas, partial R-squared, total R-squared
- AIC / BIC / DIC / log-likelihood / likelihood-ratio statistics
- mixed-effects random-slope or random-intercept variance components
- propensity scores from a chosen propensity model
- "the coefficient on T in lm(Y ~ T + W)" — the value depends on the
  functional form, control set, and estimator choices

### 2. Temporal / lag claims (the SCM is atemporal)
- "X changes precede Y effects by N days/weeks/years"
- "the response to T arrives with a lag of L periods"
- "there is a delay of T time units between cause and effect"
- "the effect appears after a waiting period"

The SCM is a static data-generating process; it has no time axis, so
lag-based claims cannot be verified. Abstain.

### 3. Study-design / methodological claims
- "an RCT would be needed to establish the causal effect of X on Y"
- "only a double-blind trial could rule out placebo effects"
- "a regression-discontinuity design would identify this effect"
- "an instrumental-variable approach is required"

These claims are about the research protocol an analyst would need, not
about the world itself. The SCM oracle has nothing to say about study
designs. Abstain.

### 4. Statistical-power / sample-size claims
- "the sample size is insufficient to detect a small effect"
- "with n=100 the study would be underpowered"
- "a larger dataset would be needed to reject the null"

These claims depend on estimator choice, alpha level, and analyst
budget — none of which the SCM defines. Abstain.

### 5. Open-ended optimization / multi-objective claims
- "what is the optimal dose of T?"
- "what level of T maximizes Y while minimizing side effects?"
- "which policy minimizes cost subject to constraints C1, C2, ...?"

The grammar supports ranking a *fixed* set of pre-specified arms, but
"optimal over a continuous range" or "simultaneously maximize outcome
and minimize side effect" requires an objective function and a search
procedure the grammar does not express. Abstain.

### 6. Structural-role claims that require you to GUESS which node plays the role

This category is NARROW and kicks in ONLY when the claim uses a
structural-role label (**"collider", "the confounder", "the mediator"**)
WITHOUT naming the concrete world variable that plays that role, AND
WITHOUT giving you any text cue you can ground in world anchors.

The prototypical case: "Adjusting for *the collider variable* introduces
bias" — here, "the collider variable" is a structural-role descriptor,
not a variable name. To pick which observed variable plays the collider
role you would have to read the DAG you do not see.

Abstain on:
- "Adjusting for the collider variable introduces bias in the X-Y
  estimate." (no named variable; the role is the only identifier.)
- "The collider is caused by both exposure and disease; conditioning
  on it opens a spurious path." (same — role label is the identifier.)

Do NOT abstain on:
- **Identifiability language with explicit text cue** — claims that
  state the cause of unidentifiability in words you can encode, even
  without a specific adjust-set variable.
  * "The causal effect of X on Y cannot be determined from the available
    data because an unmeasured factor affects both." → compile:
    `identifiability_check(X, Y)` + `not_identifiable`. The phrase
    "unmeasured factor" / "latent" / "hidden" / "unobserved" is the
    ground truth you encode, no guessing needed.
  * "No set of measured variables is sufficient to block the backdoor
    path from X to Y through the hidden confounding factor." → compile:
    `identifiability_check(X, Y)` + `not_identifiable`.
  * "If we can observe W, then the effect is identifiable via backdoor
    adjustment on W." → compile: `identifiability_check(X, Y,
    candidate_adjust_set=[W])` + `identifiable`. W is NAMED.
- **Plain identifiability questions without structural roles** —
  "Can we estimate the causal effect of X on Y?" / "Is the effect
  identifiable?" → compile `identifiability_check(X, Y)` with empty
  adjust_set and pick the assertion matching the claim's implicit
  expectation (default to `identifiable` if nothing signals
  "unobserved confounder"; `not_identifiable` if the text names a
  hidden factor). These are generic identifiability questions, not
  graph-topology guessing.

Rule of thumb — apply tightly:
1. Does the claim use a pure structural-role label ("collider",
   "the confounder", "the mediator") as the ONLY identifier of which
   variable plays that role? → ABSTAIN.
2. Does the claim name a concrete variable or give a text cue
   ("unmeasured", "hidden", "latent", "observed W") that determines
   the answer? → COMPILE.
3. When in doubt, COMPILE. Over-abstention on identifiability claims
   loses signal. The narrow case is the pure-role-label case above.

Why this matters: the verifier's ground truth is the SCM. A spec whose
ground truth is an analyst choice, a time lag, a protocol, a sample
budget, a user-defined objective, or *a graph role you had to guess*
is not verifiable. Abstention is the honest answer.

### Abstention examples (return [] for each of these):

- "The OLS coefficient of T in the multivariate model is 0.42."
- "The standardized beta of T is 0.18."
- "The partial R-squared of W in the model with T and W is 0.06."
- "The model AIC drops by 12 when T is added."
- "In a hierarchical mixed-effects model, the random-slope variance for
  T across regions is small."
- "The propensity-score-weighted mean of Y is 1.2."
- "Temperature changes precede health effects by several days."
- "A randomized controlled trial would be needed to establish the
  causal effect of pollution on health."
- "The sample size is insufficient to detect a small effect of wind
  speed on health."
- "What treatment level maximizes outcome while minimizing side effects?"

### NOT abstention — these have valid SCM verifications:

- "After adjusting for W, T causally raises Y." → causal route (Example A
  above): two adjust arms + mean + difference.
- "T is positively associated with Y controlling for W." → observational
  route (Example B above): baseline + partial_correlation.
- "P(Y > k | do(T=1)) is at least 0.4." → intervene + tail_prob.
- "The interventional mean of Y under do(T=1) is greater than under
  do(T=0)." → intervene + mean + difference.
- "Among the three treatment levels {T=0, T=1, T=2}, which produces the
  highest mean Y?" → ranking (three intervene arms + mean + ranking
  assertion; this is a *fixed* set, not open-ended optimization).

The abstention rule asks: *"is the claim grounded in a world-defined
quantity the SCM can produce?"* — not *"does the text contain the
substring 'regression' or 'coefficient'"*.
"""


# ---------------------------------------------------------------------------
# JSON helpers — shared by both flows for abstention detection
# ---------------------------------------------------------------------------


def strip_json_fences(raw: str) -> str:
    """Strip markdown code fences and return the inner JSON-like text.

    Used by both the abstention detector and the parser so they look at
    the same effective payload.
    """
    text = raw.strip()
    if "```" in text:
        for p in text.split("```"):
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("[") or p.startswith("{"):
                return p
    return text


def is_explicit_abstention(raw: str) -> bool:
    """Detect a deliberate empty JSON array as the LLM's abstention signal.

    Returns True only when the LLM returned an explicit `[]` (after
    stripping markdown fences). This is the contract surface for
    abstention: a claim the grammar cannot verify is signalled by
    returning an empty array.

    Distinguishes deliberate abstention from:
    - empty raw response (LLM call returned ""), which is an error
    - non-array text (the LLM ignored the format), which is an error
    - parse failures inside a non-empty array, which are also errors
    """
    if not raw or not raw.strip():
        return False
    inner = strip_json_fences(raw)
    if not (inner.startswith("[") and inner.endswith("]")):
        return False
    middle = inner[1:-1].strip()
    return middle == ""
