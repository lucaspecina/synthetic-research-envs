"""Diagnostic: does adding a pattern exemplar to the prompt fix compiler failures?

Tests 3 conditions per failing claim:
  A) Baseline (current prompt, no extra guidance)
  B) + Pattern exemplar (add worked example for the relevant pattern)
  C) + Pattern hint (tell the LLM "this is a mediation claim", no exemplar)

This separates:
  - Recognition gap (C fixes it but not A) = LLM knows HOW but didn't recognize WHAT
  - Recipe gap (B fixes it but not C) = LLM recognized WHAT but didn't know HOW
  - Capability gap (neither B nor C fixes it) = deeper problem
"""
import sys, os, json, copy
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv
load_dotenv()

from sreg.inference.openai_client import OpenAIClient
from sreg.inference.protocol import Message, MessageRole
from sreg.solver.scm_solver import SCMSolver
from sreg.tools.oi_compiler import build_world_summary
from sreg.tools.oi_extraction import compile_claim_direct
from sreg.models.open_investigation import ClaimCard, EvidenceRef
from sreg.tools.oi_verifier import verify_atom
from sreg.tools.oi_sq_compiler import GRAMMAR_REF, _build_variables_info

from tests.eval.suite2_translation.fact_tables import ALL_FACTS, Verdict
from tests.eval.suite2_translation.gold_targets import ALL_GOLD_TARGETS
from tests.eval.suite2_translation.worlds import ALL_WORLDS

FACT_BY_ID = {f.fact_id: f for f in ALL_FACTS}
WORLD_FOR_FACT = {f.fact_id: f.world for f in ALL_FACTS}

# Pattern-specific exemplars (abstract, not case-specific)
PATTERN_EXEMPLARS = {
    "mediation": """
## Worked example -- Mediation (indirect effect)

A mediation claim says "X affects Y through M" or "M mediates X->Y".
To verify this, you need the INDIRECT effect = total effect - direct effect.

Recipe: 4 arms + contrast_diff comparison.
- total_hi: intervene do(X=hi)
- total_lo: intervene do(X=lo)
- direct_hi: intervene do(X=hi, M=fixed)  -- fix mediator to block indirect path
- direct_lo: intervene do(X=lo, M=fixed)  -- fix mediator to block indirect path
- measurement: mean of Y
- comparison: contrast_diff  -- computes (total_hi-total_lo) - (direct_hi-direct_lo) = indirect
- assertion: positive (if claim says "through M increases Y")

ANTI-PATTERN: Do NOT test "X affects M" and "M affects Y" as two separate specs.
That tests two associations, not mediation. The indirect effect is about the
PATHWAY, not two individual links.

Spec:
[{
  "spec_id": "indirect_effect_X_on_Y_via_M",
  "arms": [
    {"label": "total_hi", "kind": "intervene", "values": {"X": 1.0}},
    {"label": "total_lo", "kind": "intervene", "values": {"X": 0.0}},
    {"label": "direct_hi", "kind": "intervene", "values": {"X": 1.0, "M": 0.0}},
    {"label": "direct_lo", "kind": "intervene", "values": {"X": 0.0, "M": 0.0}}
  ],
  "measurement": {"kind": "mean", "target": "Y"},
  "comparison": {"kind": "contrast_diff"},
  "assertion": {"kind": "positive"}
}]
""",
    "confounding": """
## Worked example -- Confounding detection

A confounding claim says "C confounds X->Y" or "the observational association
differs from the causal effect because of C".
To verify: compare the OBSERVATIONAL association with the CAUSAL effect.
If they differ, there IS confounding.

Recipe: 4 arms (2 observe + 2 intervene) + contrast_diff.
- obs_hi: observe X=hi  (natural distribution, filtered)
- obs_lo: observe X=lo
- causal_hi: intervene do(X=hi)
- causal_lo: intervene do(X=lo)
- measurement: mean of Y
- comparison: contrast_diff -- computes (obs_hi-obs_lo) - (causal_hi-causal_lo) = bias
- assertion: gap_material (bias is non-trivial)

ANTI-PATTERN: Do NOT measure partial correlations. Confounding is about the GAP
between what you observe vs what you'd get with intervention. You need BOTH
regimes (observe AND intervene) in the same spec.

Spec:
[{
  "spec_id": "confounding_bias_C_on_X_Y",
  "arms": [
    {"label": "obs_hi", "kind": "observe", "values": {"X": 1.0}},
    {"label": "obs_lo", "kind": "observe", "values": {"X": -1.0}},
    {"label": "causal_hi", "kind": "intervene", "values": {"X": 1.0}},
    {"label": "causal_lo", "kind": "intervene", "values": {"X": -1.0}}
  ],
  "measurement": {"kind": "mean", "target": "Y"},
  "comparison": {"kind": "contrast_diff"},
  "assertion": {"kind": "gap_material"}
}]
""",
    "heterogeneity": """
## Worked example -- Effect heterogeneity (effect modification)

A heterogeneity claim says "the effect of X on Y depends on Z" or
"Z modifies the effect of X".
To verify: COMPARE the treatment effect across subgroups of Z.
The key is the COMPARISON between subgroups, not just estimating within each.

Recipe: 4 arms + contrast_diff.
- hi_mod_treated: intervene do(X=hi), condition_on Z in top subgroup
- hi_mod_control: intervene do(X=lo), condition_on Z in top subgroup
- lo_mod_treated: intervene do(X=hi), condition_on Z in bottom subgroup
- lo_mod_control: intervene do(X=lo), condition_on Z in bottom subgroup
- measurement: mean of Y
- comparison: contrast_diff -- (effect in hi Z) - (effect in lo Z)
- assertion: gap_material or positive/negative

ANTI-PATTERN: Do NOT estimate the effect separately in each subgroup as
independent specs. That shows effects EXIST in subgroups but does NOT test
whether they DIFFER. Heterogeneity is about the DIFFERENCE between effects.

Spec:
[{
  "spec_id": "effect_modification_X_by_Z",
  "arms": [
    {"label": "hi_z_treated", "kind": "intervene", "values": {"X": 1.0},
     "condition_on": {"Z": {"kind": "quantile_range", "q_lo": 0.75, "q_hi": 1.0}}},
    {"label": "hi_z_control", "kind": "intervene", "values": {"X": 0.0},
     "condition_on": {"Z": {"kind": "quantile_range", "q_lo": 0.75, "q_hi": 1.0}}},
    {"label": "lo_z_treated", "kind": "intervene", "values": {"X": 1.0},
     "condition_on": {"Z": {"kind": "quantile_range", "q_lo": 0.0, "q_hi": 0.25}}},
    {"label": "lo_z_control", "kind": "intervene", "values": {"X": 0.0},
     "condition_on": {"Z": {"kind": "quantile_range", "q_lo": 0.0, "q_hi": 0.25}}}
  ],
  "measurement": {"kind": "mean", "target": "Y"},
  "comparison": {"kind": "contrast_diff"},
  "assertion": {"kind": "gap_material"}
}]
""",
}

PATTERN_HINTS = {
    "mediation": "IMPORTANT: This is a MEDIATION claim. You need to measure the indirect effect (total - direct). Use 4 arms: total effect arms + direct effect arms (fix mediator), then contrast_diff comparison.",
    "confounding": "IMPORTANT: This is a CONFOUNDING claim. You need to compare observational vs causal regimes. Use 4 arms: 2 observe + 2 intervene, then contrast_diff to measure the bias gap.",
    "heterogeneity": "IMPORTANT: This is a HETEROGENEITY claim. You need to COMPARE the treatment effect across subgroups, not just estimate it in each. Use contrast_diff to compare effects.",
}

# Test cases: (fact_id, surface_form_index, pattern)
TEST_CASES = [
    ("W1_F05", 1, "mediation"),       # "Compliance mediates treatment->outcome"
    ("W1_F07", 0, "confounding"),      # "Severity confounds treatment->outcome"
    ("W1_F06", 0, "heterogeneity"),    # "Effect depends on biomarker level"
]


def make_llm_call(client):
    def llm_call(*args):
        if len(args) == 2 and isinstance(args[0], str):
            system, user = args
            msgs = [
                Message(role=MessageRole.SYSTEM, content=system),
                Message(role=MessageRole.USER, content=user),
            ]
        elif len(args) == 1 and isinstance(args[0], list):
            msgs = [
                Message(role=MessageRole(m["role"]), content=m["content"])
                for m in args[0]
            ]
        else:
            raise TypeError(f"Unexpected args: {type(args)}")
        resp = client.chat(msgs, temperature=0.0)
        return resp.message.content or ""
    return llm_call


def compile_with_modified_prompt(claim, summary, llm_call_fn, extra_system="", extra_user=""):
    """Run compile_claim_direct but with extra prompt content injected."""
    from sreg.models.open_investigation import AtomicSpec
    from sreg.tools.oi_compiler import CompiledUnit, CompilerOutput
    from sreg.tools.oi_sq_compiler import (
        _build_variables_info, _coerce_tuples, _parse_specs_json, _validate_variables,
    )

    system_prompt = f"""You are a verification compiler for a research evaluation system.

Given a research claim and world variables, produce AtomicSpec(s) that verify
whether the claim is true according to a structural causal model (SCM).

{GRAMMAR_REF}

## Guidelines for claim compilation
- Extract ALL testable assertions from the claim text.
- Each AtomicSpec tests ONE atomic fact.
- A claim like "X causes Y and also affects Z" should produce 2+ specs.
- Causal claims ("X causes Y", "X leads to Y") need interventional arms.
- Associational claims ("X correlates with Y") use baseline arms with
  correlation or partial_correlation measurement.
- Claims about confounding need partial_correlation or interventional specs
  that show the gap between crude and adjusted effects.
- Mediation claims need specs comparing total vs direct effects.
- "No effect" or "null association" claims should use near_zero assertion.
- Direction: "increases" -> positive, "decreases" -> negative.
- For difference/ratio comparisons: ref_arm is REQUIRED and must be the
  control/baseline arm.

{extra_system}

## Output format
Return a JSON array of AtomicSpec objects. Return ONLY the JSON array."""

    world_vars = set(summary.observable_names)
    variables_info = _build_variables_info(summary)

    parts = [
        f'Claim: "{claim.claim_text}"',
        f"\nVariables in this world:\n{variables_info}",
    ]
    if claim.focus_variables:
        parts.append(f"\nFocus variables: {', '.join(claim.focus_variables)}")
    if extra_user:
        parts.append(f"\n{extra_user}")
    parts.append("\nProduce AtomicSpec(s) to verify this claim.")
    user_prompt = "\n".join(parts)

    try:
        raw = llm_call_fn(system_prompt, user_prompt)
    except Exception as e:
        return None, str(e)

    try:
        items = _parse_specs_json(raw)
    except Exception as e:
        return None, str(e)

    if not items:
        return None, "empty"

    specs = []
    errors = []
    for i, item in enumerate(items):
        spec_dict = item
        if isinstance(item, dict) and "spec" in item:
            spec_dict = item["spec"]
        var_errors = _validate_variables(spec_dict, world_vars)
        if var_errors:
            errors.extend(f"Spec {i}: {e}" for e in var_errors)
            continue
        if "spec_id" not in spec_dict:
            spec_dict["spec_id"] = f"diag_{i}"
        try:
            spec_dict = _coerce_tuples(spec_dict)
            atom = AtomicSpec(**spec_dict)
            specs.append(atom)
        except Exception as e:
            errors.append(f"Spec {i}: {e}")

    if not specs:
        return None, "; ".join(errors)

    return specs, None


def evaluate_specs(specs, fact, world, solver):
    """Run specs through verifier and check verdict."""
    verdicts = []
    for spec in specs:
        result = verify_atom(spec, world, solver, n_mc=50_000, seed=42)
        verdicts.append(result)

    all_hold = all(v.solver_assertion_holds for v in verdicts)
    any_fail = any(not v.solver_assertion_holds for v in verdicts)

    if fact.truth_value == Verdict.TRUE:
        ok = all_hold
    elif fact.truth_value == Verdict.FALSE:
        ok = any_fail
    elif fact.truth_value == Verdict.NOT_IDENTIFIABLE:
        ok = all_hold
    else:
        ok = False

    return ok, verdicts


def describe_specs(specs):
    """Compact description of compiled specs."""
    lines = []
    for s in specs:
        arm_str = ", ".join(
            f"{a.kind.value}({dict(a.values)})" for a in s.arms
        )
        lines.append(
            f"  {s.spec_id}: [{arm_str}] "
            f"measure={s.measurement.kind.value} "
            f"compare={s.comparison.kind.value} "
            f"assert={s.assertion.kind.value}"
        )
    return "\n".join(lines)


# Main
client = OpenAIClient()
llm_call = make_llm_call(client)
solver_cache = {}


def get_solver(wk):
    if wk not in solver_cache:
        w = ALL_WORLDS[wk]
        solver_cache[wk] = (w, SCMSolver(w, n_mc=50_000))
    return solver_cache[wk]


print("=" * 70)
print("  PROMPT DIAGNOSTIC TEST")
print("=" * 70)

for fact_id, sf_idx, pattern in TEST_CASES:
    fact = FACT_BY_ID[fact_id]
    sf = fact.surface_forms[sf_idx]
    wk = WORLD_FOR_FACT[fact_id]
    world, solver = get_solver(wk)

    # Find gold target
    gt = None
    for g in ALL_GOLD_TARGETS:
        if g.fact_id == fact_id and g.surface_form_index == sf_idx:
            gt = g
            break

    target_var = "Y" if "w1" in wk else ("D" if "w2" in wk else "H")
    summary = build_world_summary(world, target_var)

    focus = []
    if gt and gt.structural_contract and gt.structural_contract.required_role_vars:
        focus = list(set(gt.structural_contract.required_role_vars.values()))
    if not focus:
        focus = [target_var]

    claim = ClaimCard(
        claim_id=f"{fact_id}_s{sf_idx}_diag",
        claim_text=sf.text,
        focus_variables=focus,
        confidence=1.0,
        evidence_basis=[EvidenceRef(
            artifact_id="diag", rationale="Diagnostic test for prompt quality",
        )],
    )

    print(f"\n{'='*70}")
    print(f"  {fact_id}_s{sf_idx} | pattern={pattern} | truth={fact.truth_value.value}")
    print(f"  Claim: {sf.text[:80]}")
    print(f"{'='*70}")

    conditions = [
        ("A) Baseline", "", ""),
        ("B) + Exemplar", PATTERN_EXEMPLARS[pattern], ""),
        ("C) + Hint only", "", PATTERN_HINTS[pattern]),
    ]

    for label, extra_sys, extra_usr in conditions:
        specs, err = compile_with_modified_prompt(
            claim, summary, llm_call, extra_system=extra_sys, extra_user=extra_usr,
        )
        if specs is None:
            print(f"\n  {label}: COMPILE FAILED ({err})")
            continue

        ok, verdicts = evaluate_specs(specs, fact, world, solver)
        v_str = ", ".join(
            f"{'HOLD' if v.solver_assertion_holds else 'FAIL'}"
            for v in verdicts
        )
        print(f"\n  {label}: {'VERDICT OK' if ok else 'VERDICT WRONG'} [{v_str}]")
        print(f"    {len(specs)} spec(s):")
        print(describe_specs(specs))

print(f"\n{'='*70}")
print("  INTERPRETATION")
print("=" * 70)
print("  If B fixes but A fails: RECIPE GAP (prompt doesn't teach HOW)")
print("  If C fixes but A fails: RECOGNITION GAP (LLM knew how, didn't recognize)")
print("  If neither B nor C fixes: CAPABILITY GAP (deeper problem)")
print("=" * 70)
