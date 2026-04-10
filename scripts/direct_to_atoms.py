#!/usr/bin/env python
"""Prototype: compile claims and SQs directly to AtomicSpec, no PatternClass.

Takes claim text (or SQ text) + world variables + grammar schema,
asks the LLM to produce AtomicSpec(s), verifies against the SCM,
and compares with the current catalog-based pipeline.

Usage:
    python scripts/direct_to_atoms.py
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from sreg.models.open_investigation import (
    Assertion, AtomicSpec, Comparison, Measurement, QueryArm,
)
from sreg.models.scm_spec import SCMSpec
from sreg.solver.scm_solver import SCMSolver
from sreg.tools.oi_compiler import build_world_summary
from sreg.tools.oi_verifier import verify_atom
from sreg.tools.scm_world_gen import SCMWorldGenTool

# ── Grammar reference for the LLM prompt ─────────────────────────────
GRAMMAR_REF = """
You have a composable verification grammar with 4 pieces:

## QueryArm
Each spec has 1+ arms. Each arm generates data from the SCM.
- kind: "baseline" (sample from joint), "intervene" (do-calculus, set values),
  "observe" (observe natural distribution), "condition" (condition on values),
  "adjust" (observe but adjust for confounders), "sweep" (vary a variable)
- label: unique name for this arm (e.g. "baseline", "treated", "control")
- values: dict of variable=value for intervene/condition (e.g. {"X": 1.0})
- condition_on: dict for condition kind
- treatment/outcome: for adjust kind
- adjust_set: tuple of variable names to adjust for (for adjust kind)

## Measurement
What to compute from the sampled data.
- kind: "mean", "variance", "correlation", "partial_correlation",
  "tail_prob", "prob", "quantile", "identifiability_check"
- target: variable name for mean/variance/quantile/tail_prob
- lhs, rhs: variable names for correlation/partial_correlation
- cond_set: tuple of variables to condition on (for partial_correlation)
- treatment, outcome: for identifiability_check
- threshold: for tail_prob

## Comparison
How to relate measurements across arms.
- kind: "identity" (single arm, just check the value),
  "difference" (arm1 - arm2), "ratio", "ranking" (rank multiple arms),
  "gap" (check minimum gap), "contrast_diff"
- ref_arm: reference arm label for difference/ratio
- order: tuple of arm labels for ranking
- tolerance: float (default 0.05)

## Assertion
What should be true about the comparison result.
- kind: "positive", "negative", "near_zero", "greater_than", "less_than",
  "rank_order", "identifiable", "not_identifiable"
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
- Generate 1..N specs that together verify the claim.
- Each spec checks ONE atomic fact. Complex claims need multiple specs.
- For partial_correlation with empty cond_set, it computes raw correlation.
- "baseline" arms sample from the joint distribution (no intervention).
- Return a JSON array of specs.
"""


def build_llm():
    """Build LLM call function."""
    from openai import OpenAI
    client = OpenAI(
        base_url=os.environ.get("AZURE_FOUNDRY_BASE_URL", ""),
        api_key=os.environ.get("AZURE_INFERENCE_CREDENTIAL", ""),
    )
    model = os.environ.get("AZURE_MODEL", "gpt-5.4")

    def call(system: str, user: str) -> str:
        resp = client.responses.create(
            model=model,
            instructions=system,
            input=[{"role": "user", "content": user}],
        )
        for item in resp.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        return part.text
        return ""
    return call


def parse_specs(raw: str) -> list[dict]:
    """Extract JSON array from LLM response."""
    # Try to find JSON array in response
    text = raw.strip()
    # Remove markdown code fences
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("["):
                text = p
                break

    # Find the array
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        return json.loads(text[start:end + 1])
    return []


def compile_and_verify(
    label: str,
    text: str,
    variables_info: str,
    world,
    solver,
    llm_call,
    is_sq: bool = False,
):
    """Compile text directly to AtomicSpecs and verify."""
    print(f"\n{'=' * 60}")
    print(f"{'SQ' if is_sq else 'CLAIM'}: {label}")
    print(f"{'=' * 60}")
    print(f"Text: {text[:200]}...")

    task = "sub-question" if is_sq else "claim"
    system = f"""You are a verification compiler. Given a research {task} and a list
of world variables, produce AtomicSpec(s) that verify whether the {task} is true
in a structural causal model (SCM).

{GRAMMAR_REF}

Think step by step:
1. What is the {task} actually asserting?
2. What measurements on the SCM would confirm or refute it?
3. Compose those into AtomicSpec(s).

Return ONLY a JSON array of AtomicSpec objects. No explanation."""

    user = f"""Research {task}:
\"{text}\"

Variables in this world:
{variables_info}

Produce AtomicSpec(s) to verify this {task}."""

    print("\nCalling LLM for direct compilation...")
    raw = llm_call(system, user)
    print(f"LLM response length: {len(raw)} chars")

    # Parse specs
    spec_dicts = parse_specs(raw)
    print(f"Parsed {len(spec_dicts)} spec(s)")

    if not spec_dicts:
        print(f"FAILED: could not parse specs from response")
        print(f"Raw response:\n{raw[:500]}")
        return []

    # Validate and verify each spec
    results = []
    for i, sd in enumerate(spec_dicts):
        print(f"\n--- Spec {i}: {sd.get('spec_id', f'spec_{i}')} ---")
        try:
            # Ensure tuples where needed
            for arm in sd.get("arms", []):
                if "adjust_set" in arm and isinstance(arm["adjust_set"], list):
                    arm["adjust_set"] = tuple(arm["adjust_set"])
                if "sweep_values" in arm and isinstance(arm["sweep_values"], list):
                    arm["sweep_values"] = tuple(arm["sweep_values"])
            meas = sd.get("measurement", {})
            if "cond_set" in meas and isinstance(meas["cond_set"], list):
                meas["cond_set"] = tuple(meas["cond_set"])
            if "candidate_causes" in meas and isinstance(meas["candidate_causes"], list):
                meas["candidate_causes"] = tuple(meas["candidate_causes"])
            if "candidate_adjust_set" in meas and isinstance(meas["candidate_adjust_set"], list):
                meas["candidate_adjust_set"] = tuple(meas["candidate_adjust_set"])
            comp = sd.get("comparison", {})
            if "order" in comp and isinstance(comp["order"], list):
                comp["order"] = tuple(comp["order"])
            assrt = sd.get("assertion", {})
            if "order" in assrt and isinstance(assrt["order"], list):
                assrt["order"] = tuple(assrt["order"])

            spec = AtomicSpec(**sd)
            print(f"  Valid AtomicSpec: arms={[a.kind for a in spec.arms]}, "
                  f"meas={spec.measurement.kind}, comp={spec.comparison.kind}, "
                  f"assert={spec.assertion.kind}")

            verdict = verify_atom(spec, world, solver, 20_000, 42)
            print(f"  HOLDS: {verdict.solver_assertion_holds}")
            print(f"  ground_truth: {verdict.ground_truth}")
            results.append({
                "spec_id": spec.spec_id,
                "holds": verdict.solver_assertion_holds,
                "ground_truth": verdict.ground_truth,
                "detail": verdict.detail,
            })
        except Exception as e:
            print(f"  ERROR: {e}")
            # Print the spec dict for debugging
            print(f"  spec_dict: {json.dumps(sd, indent=2)[:300]}")
            results.append({"spec_id": sd.get("spec_id", f"spec_{i}"), "error": str(e)})

    return results


def main():
    # Load e2e_03 world
    with open("experiments/e2e_03_epistemic/src.json") as f:
        src = json.load(f)
    with open("experiments/e2e_03_epistemic/oi_result.json") as f:
        result = json.load(f)

    # Reconstruct world
    scm_args = None
    for tc in src.get("process", {}).get("tools_called", []):
        if tc.get("tool") == "scm_construct":
            res = tc.get("result", {})
            if "world_id" in res or "error" not in res:
                scm_args = tc["args"]
                break
    if scm_args is None:
        for tc in src.get("process", {}).get("tools_called", []):
            if tc.get("tool") == "scm_construct":
                scm_args = tc["args"]
    if scm_args.get("edges") and isinstance(scm_args["edges"][0], dict):
        scm_args["edges"] = [(e["from"], e["to"]) for e in scm_args["edges"]]

    spec = SCMSpec(**scm_args)
    gen = SCMWorldGenTool()
    world = gen.generate(spec, seed=42)
    solver = SCMSolver(world, n_mc=20_000)
    summary = build_world_summary(world, "childhood_wheeze_prevalence", n_mc=20_000, seed=42)

    # Build variables info string
    var_lines = []
    for name in summary.observable_names:
        meta = world.variable_meta.get(name)
        desc = ""
        if meta:
            if meta.description:
                desc = meta.description.rstrip(".")
            if meta.unit:
                desc = f"{desc} [unit: {meta.unit}]" if desc else f"unit: {meta.unit}"
        var_lines.append(f"- {name}: {desc}" if desc else f"- {name}")
    variables_info = "\n".join(var_lines)

    llm = build_llm()

    # ── Get claims from e2e_03 ──
    claims_raw = []
    for tc in result.get("solver_tool_calls", []):
        if tc.get("name") == "submit_claims":
            claims_raw = tc["args"]["claims"]

    # ── CLAIMS TO TEST ──
    # C2: adjustment sensitivity (ABSTENTION in current pipeline)
    c2 = next(c for c in claims_raw if c["claim_id"] == "C2")
    # C3: instrument inconsistency (wrong direction in current pipeline)
    c3 = next(c for c in claims_raw if c["claim_id"] == "C3")

    # ── SQ TO TEST ──
    # The REAL brief question (not the compressed SQ)
    sq_brief = (
        "Assess whether the available district-level data can support a causal "
        "claim about particulate pollution and pediatric wheeze. Identify the "
        "main sources of bias or non-identification in the current evidence base."
    )

    print("\n" + "#" * 60)
    print("# DIRECT-TO-ATOMICSPEC PROTOTYPE")
    print("# Comparing catalog-based vs direct compilation")
    print("#" * 60)

    print("\n\n>>> CURRENT PIPELINE RESULTS (catalog-based) <<<")
    print("C2: ABSTENTION (no pattern for adjustment sensitivity)")
    print("C3: obs_assoc near_zero x2, truth=0.0+0.0 (wrong direction)")
    print("SQ1: causal_effect existence_and_sign (compressed from epistemological brief)")

    # ── Test claims ──
    c2_results = compile_and_verify(
        "C2 (adjustment sensitivity)",
        c2["claim_text"],
        variables_info, world, solver, llm,
    )

    c3_results = compile_and_verify(
        "C3 (instrument inconsistency)",
        c3["claim_text"],
        variables_info, world, solver, llm,
    )

    # ── Test SQ (the real brief, not the compressed version) ──
    sq_results = compile_and_verify(
        "SQ: epistemological brief",
        sq_brief,
        variables_info, world, solver, llm,
        is_sq=True,
    )

    # ── Summary ──
    print("\n\n" + "#" * 60)
    print("# COMPARISON SUMMARY")
    print("#" * 60)

    print("\n## C2 (adjustment sensitivity)")
    print(f"  Catalog pipeline: ABSTENTION (0 specs)")
    print(f"  Direct pipeline:  {len(c2_results)} specs")
    for r in c2_results:
        if "error" in r:
            print(f"    {r['spec_id']}: ERROR - {r['error']}")
        else:
            print(f"    {r['spec_id']}: holds={r['holds']}, gt={r['ground_truth']}")

    print(f"\n## C3 (instrument inconsistency)")
    print(f"  Catalog pipeline: 2 specs, both near_zero, truth=0.0+0.0")
    print(f"  Direct pipeline:  {len(c3_results)} specs")
    for r in c3_results:
        if "error" in r:
            print(f"    {r['spec_id']}: ERROR - {r['error']}")
        else:
            print(f"    {r['spec_id']}: holds={r['holds']}, gt={r['ground_truth']}")

    print(f"\n## SQ (epistemological brief, direct)")
    print(f"  Catalog pipeline: causal_effect(sign) -- loses epistemological content")
    print(f"  Direct pipeline:  {len(sq_results)} specs")
    for r in sq_results:
        if "error" in r:
            print(f"    {r['spec_id']}: ERROR - {r['error']}")
        else:
            print(f"    {r['spec_id']}: holds={r['holds']}, gt={r['ground_truth']}")


if __name__ == "__main__":
    main()
