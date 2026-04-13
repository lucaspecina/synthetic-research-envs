#!/usr/bin/env python
"""Compare catalog-based vs direct-to-AtomicSpec compilation across experiments.

For each experiment:
1. Catalog path: current pipeline (rescore.py logic) → count compiled units + truth
2. Direct path: LLM → AtomicSpec → verify_atom → count specs + truth

Hypothesis: the less we depend on the fixed catalog, the better we preserve
claim/SQ semantics across diverse investigation types.

Usage:
    python scripts/compare_compilers.py experiments/e2e_07_* experiments/e2e_08_* ...
    python scripts/compare_compilers.py experiments/e2e_0[789]_* experiments/e2e_1*
"""
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from sreg.models.open_investigation import (
    AtomicSpec, ClaimCard, SubQuestionIntent,
)
from sreg.models.scm_spec import SCMSpec
from sreg.tools.oi_compiler import CompilerOutput, build_world_summary
from sreg.tools.oi_extraction import ExtractionContext, compile_episode_claims
from sreg.tools.oi_verifier import verify_atom
from sreg.tools.scm_world_gen import SCMWorldGenTool
from sreg.solver.scm_solver import SCMSolver


# ── Grammar reference for direct compilation ──────────────────────────
GRAMMAR_REF = """
You have a composable verification grammar with 4 pieces:

## QueryArm
- kind: "baseline" (sample from joint), "intervene" (do-calculus, set values),
  "observe", "condition" (condition on values), "adjust", "sweep"
- label: unique name for this arm
- values: dict of variable=value for intervene/condition
- condition_on: dict for condition kind
- treatment/outcome: for adjust kind
- adjust_set: tuple of variable names to adjust for

## Measurement
- kind: "mean", "variance", "correlation", "partial_correlation",
  "tail_prob", "prob", "quantile", "identifiability_check"
- target: variable name for mean/variance/quantile/tail_prob
- lhs, rhs: variable names for correlation/partial_correlation
- cond_set: tuple of variables to partial out (for partial_correlation)
- treatment, outcome: for identifiability_check

## Comparison
- kind: "identity" (single arm), "difference" (arm1 - arm2), "ratio",
  "ranking" (rank multiple arms), "gap", "contrast_diff"
- ref_arm: reference arm label
- order: tuple of arm labels for ranking

## Assertion
- kind: "positive", "negative", "near_zero", "greater_than", "less_than",
  "rank_order", "identifiable", "not_identifiable"
- threshold: numeric (default 0.0)
- tolerance: float (default 0.05)
- order: tuple for rank_order

Return ONLY a JSON array of AtomicSpec objects:
[{"spec_id": "...", "arms": [...], "measurement": {...}, "comparison": {...}, "assertion": {...}}]

RULES:
- ALL variable names MUST come from the Variables list.
- Each spec checks ONE atomic fact. Complex claims need multiple specs.
- For partial_correlation with empty cond_set, it computes raw correlation.
- "baseline" arms sample the joint distribution (no intervention).
"""


def build_llm():
    from openai import OpenAI
    client = OpenAI(
        base_url=os.environ.get("AZURE_FOUNDRY_BASE_URL", ""),
        api_key=os.environ.get("AZURE_INFERENCE_CREDENTIAL", ""),
    )
    model = os.environ.get("AZURE_MODEL", "gpt-5.4")

    def call(system: str, user: str) -> str:
        resp = client.responses.create(
            model=model, instructions=system,
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
    text = raw.strip()
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("["):
                text = p
                break
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        return json.loads(text[start:end + 1])
    return []


def coerce_tuples(sd: dict):
    """Convert lists to tuples where pydantic expects them."""
    for arm in sd.get("arms", []):
        for k in ("adjust_set", "sweep_values"):
            if k in arm and isinstance(arm[k], list):
                arm[k] = tuple(arm[k])
    meas = sd.get("measurement", {})
    for k in ("cond_set", "candidate_causes", "candidate_adjust_set"):
        if k in meas and isinstance(meas[k], list):
            meas[k] = tuple(meas[k])
    for section in ("comparison", "assertion"):
        s = sd.get(section, {})
        if "order" in s and isinstance(s["order"], list):
            s["order"] = tuple(s["order"])


def reconstruct_world(src: dict):
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
    if scm_args is None:
        raise ValueError("No scm_construct found")
    if scm_args.get("edges") and isinstance(scm_args["edges"][0], dict):
        scm_args["edges"] = [(e["from"], e["to"]) for e in scm_args["edges"]]
    spec = SCMSpec(**scm_args)
    gen = SCMWorldGenTool()
    return gen.generate(spec, seed=42)


def get_claims(result: dict) -> list[dict]:
    claims = []
    for tc in result.get("solver_tool_calls", []):
        if tc.get("name") == "submit_claims":
            claims = tc["args"]["claims"]
    return claims


def catalog_compile(claims_raw, world, summary, sqs, src):
    """Run the current catalog-based compiler."""
    claim_cards = []
    for rc in claims_raw:
        claim_cards.append(ClaimCard(
            claim_id=rc["claim_id"],
            claim_text=rc["claim_text"],
            focus_variables=rc.get("focus_variables", [])[:8],
            confidence=rc.get("confidence", 0.5),
            evidence_basis=rc.get("evidence_basis", [
                {"artifact_id": "x", "rationale": "Analysis from solver"}
            ]),
        ))

    variable_descriptions = {}
    for name in summary.observable_names:
        meta = world.variable_meta.get(name)
        if not meta or not (meta.description or meta.unit):
            continue
        desc = meta.description.rstrip(".") if meta.description else ""
        if meta.unit:
            desc = f"{desc} [unit: {meta.unit}]" if desc else f"unit: {meta.unit}"
        variable_descriptions[name] = desc

    ctx = ExtractionContext(
        research_brief=src["problem"].get("research_question", ""),
        domain=src["problem"].get("domain", ""),
        description=src["problem"].get("description", ""),
        title=src["problem"].get("title", ""),
        variable_descriptions=variable_descriptions,
        sub_questions=[
            {"sq_id": sq.sq_id, "pattern": sq.pattern,
             "text_gloss": sq.text_gloss or sq.sq_id}
            for sq in sqs
        ],
    )

    from openai import OpenAI
    client = OpenAI(
        base_url=os.environ.get("AZURE_FOUNDRY_BASE_URL", ""),
        api_key=os.environ.get("AZURE_INFERENCE_CREDENTIAL", ""),
    )
    model_name = os.environ.get("AZURE_MODEL", "gpt-5.4")

    def llm_call(messages):
        instructions = messages[0]["content"] if messages else ""
        input_items = [
            {"role": m["role"], "content": m["content"]} for m in messages[1:]
        ]
        resp = client.responses.create(
            model=model_name, instructions=instructions, input=input_items,
        )
        for item in resp.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        return part.text
        return ""

    compiled = compile_episode_claims(
        claim_cards, summary, llm_call=llm_call, context=ctx,
    )

    results = []
    for co in compiled:
        if not isinstance(co, CompilerOutput):
            continue
        results.append({
            "claim_id": co.claim_id,
            "compiled": co.compiled,
            "n_units": len(co.units),
            "units": [],
        })
        if co.compiled:
            for unit in co.units:
                i = unit.intent
                results[-1]["units"].append({
                    "pattern": str(i.pattern),
                    "treatment": i.treatment,
                    "outcome": i.outcome,
                    "direction": str(i.direction),
                })
    return results


def direct_compile(claims_raw, world, summary, solver, llm_call):
    """Compile claims directly to AtomicSpec using LLM."""
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

    system = f"""You are a verification compiler. Given a research claim and world
variables, produce AtomicSpec(s) that verify whether the claim is true in a
structural causal model (SCM).

{GRAMMAR_REF}

Think about what the claim actually asserts, then produce specs to check it."""

    results = []
    for rc in claims_raw:
        user = (
            f'Claim: "{rc["claim_text"]}"\n\n'
            f"Variables in this world:\n{variables_info}\n\n"
            f"Produce AtomicSpec(s) to verify this claim."
        )
        raw = llm_call(system, user)
        spec_dicts = parse_specs(raw)

        claim_result = {
            "claim_id": rc["claim_id"],
            "n_specs": len(spec_dicts),
            "specs_valid": 0,
            "specs_true": 0,
            "specs": [],
        }

        for sd in spec_dicts:
            try:
                coerce_tuples(sd)
                spec = AtomicSpec(**sd)
                verdict = verify_atom(spec, world, solver, 20_000, 42)
                claim_result["specs_valid"] += 1
                if verdict.solver_assertion_holds:
                    claim_result["specs_true"] += 1
                claim_result["specs"].append({
                    "spec_id": spec.spec_id,
                    "holds": verdict.solver_assertion_holds,
                    "gt": verdict.ground_truth,
                    "meas": str(spec.measurement.kind),
                    "assert": str(spec.assertion.kind),
                })
            except Exception as e:
                claim_result["specs"].append({
                    "spec_id": sd.get("spec_id", "?"),
                    "error": str(e)[:80],
                })

        results.append(claim_result)
    return results


def process_experiment(exp_dir: Path, llm_call):
    """Process one experiment: catalog + direct compilation."""
    print(f"\n{'=' * 60}")
    print(f"  {exp_dir.name}")
    print(f"{'=' * 60}")

    with open(exp_dir / "src.json") as f:
        src = json.load(f)
    with open(exp_dir / "oi_result.json") as f:
        result = json.load(f)

    claims_raw = get_claims(result)
    if not claims_raw:
        print("  No claims submitted.")
        return None

    world = reconstruct_world(src)
    target = src["problem"].get("target") or src["problem"].get("target_node")
    summary = build_world_summary(world, target, n_mc=20_000, seed=42)
    solver = SCMSolver(world, n_mc=20_000)
    sqs = [SubQuestionIntent(**sq) for sq in src.get("sub_questions", [])]

    # ── Catalog compilation ──
    print("  [catalog] compiling...")
    cat = catalog_compile(claims_raw, world, summary, sqs, src)

    cat_compiled = sum(1 for c in cat if c["compiled"])
    cat_units = sum(c["n_units"] for c in cat)

    # Verify catalog units
    cat_true = 0
    for co_raw in cat:
        if not co_raw["compiled"]:
            continue
        # We need to re-run verification through the full pipeline
        # but for counting, we use the compiled status
    # Actually let's just use rescore for truth — too complex to rerun here
    # We'll report compilation rate only for catalog

    # ── Direct compilation ──
    print("  [direct] compiling...")
    direct = direct_compile(claims_raw, world, summary, solver, llm_call)

    dir_total_specs = sum(c["n_specs"] for c in direct)
    dir_valid_specs = sum(c["specs_valid"] for c in direct)
    dir_true_specs = sum(c["specs_true"] for c in direct)

    # ── Report ──
    print(f"\n  Claims: {len(claims_raw)}")
    print(f"  CATALOG: {cat_compiled}/{len(claims_raw)} compiled, {cat_units} units")
    print(f"  DIRECT:  {dir_valid_specs}/{dir_total_specs} valid specs, "
          f"{dir_true_specs} TRUE")

    print(f"\n  Per-claim detail:")
    for i, rc in enumerate(claims_raw):
        cid = rc["claim_id"]
        # Catalog
        cat_info = cat[i] if i < len(cat) else {"compiled": False, "n_units": 0}
        cat_status = f"{cat_info['n_units']} units" if cat_info["compiled"] else "ABSTENTION"
        if cat_info["compiled"] and cat_info["units"]:
            patterns = [u["pattern"] for u in cat_info["units"]]
            cat_status += f" ({', '.join(patterns)})"

        # Direct
        dir_info = direct[i] if i < len(direct) else {"n_specs": 0, "specs_valid": 0, "specs_true": 0}
        dir_status = (f"{dir_info['specs_valid']} valid, "
                      f"{dir_info['specs_true']} TRUE")
        if dir_info.get("specs"):
            meas_types = set()
            for s in dir_info["specs"]:
                if "meas" in s:
                    meas_types.add(s["meas"])
            if meas_types:
                dir_status += f" ({', '.join(sorted(meas_types))})"

        print(f"    {cid}:")
        print(f"      catalog: {cat_status}")
        print(f"      direct:  {dir_status}")
        print(f"      text: {rc['claim_text'][:80]}...")

    return {
        "experiment": exp_dir.name,
        "n_claims": len(claims_raw),
        "catalog_compiled": cat_compiled,
        "catalog_units": cat_units,
        "direct_specs": dir_total_specs,
        "direct_valid": dir_valid_specs,
        "direct_true": dir_true_specs,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("experiments", nargs="+")
    args = parser.parse_args()

    llm = build_llm()
    summaries = []

    for exp_path in args.experiments:
        exp_dir = Path(exp_path)
        if not exp_dir.is_dir():
            continue
        try:
            s = process_experiment(exp_dir, llm)
            if s:
                summaries.append(s)
        except Exception as e:
            print(f"  ERROR: {e}")

    # Final summary table
    print(f"\n\n{'#' * 60}")
    print(f"# COMPARISON SUMMARY")
    print(f"{'#' * 60}")
    print(f"\n{'Experiment':<35} {'Claims':>6} {'Cat.Comp':>9} {'Cat.Units':>9} "
          f"{'Dir.Valid':>9} {'Dir.TRUE':>9}")
    print("-" * 80)
    for s in summaries:
        print(f"{s['experiment']:<35} {s['n_claims']:>6} "
              f"{s['catalog_compiled']:>9} {s['catalog_units']:>9} "
              f"{s['direct_valid']:>9} {s['direct_true']:>9}")

    # Totals
    if summaries:
        print("-" * 80)
        tc = sum(s["n_claims"] for s in summaries)
        cc = sum(s["catalog_compiled"] for s in summaries)
        cu = sum(s["catalog_units"] for s in summaries)
        dv = sum(s["direct_valid"] for s in summaries)
        dt = sum(s["direct_true"] for s in summaries)
        print(f"{'TOTAL':<35} {tc:>6} {cc:>9} {cu:>9} {dv:>9} {dt:>9}")


if __name__ == "__main__":
    main()
