#!/usr/bin/env python
"""Compiler Benchmark: catalog vs direct-to-AtomicSpec across diverse cases.

Metrics measured for each path:
  1. Compile rate / abstentions
  2. Semantic preservation (variable coverage, measurement diversity)
  3. Truth rate (verified against SCM)
  4. SQ coverage (which sub-questions are answered)
  5. Over-generation (specs per claim, redundancy)

Usage:
    python scripts/compiler_benchmark.py experiments/e2e_*
    python scripts/compiler_benchmark.py experiments/e2e_07_* experiments/e2e_08_*
    python scripts/compiler_benchmark.py experiments/e2e_* --output results/benchmark.json
"""
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from sreg.models.open_investigation import (
    AtomicSpec,
    ClaimCard,
    SubQuestionIntent,
)
from sreg.models.scm_spec import SCMSpec
from sreg.tools.oi_compiler import (
    ClaimIntent,
    CompilerOutput,
    WorldSummary,
    build_world_summary,
    lower_intent,
)
from sreg.tools.oi_extraction import ExtractionContext, compile_episode_claims
from sreg.tools.oi_subquestions import (
    resolve_subquestion,
    score_episode_with_subquestions,
)
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


# ── Scenario type classification ──────────────────────────────────────
SCENARIO_MAP = {
    "vaca_causal": "causal_simple",
    "vaca_predictive": "predictive",
    "epistemic": "epistemological",
    "system_mapping": "system_mapping",
    "confounding": "confounding",
    "heterogeneity": "heterogeneity",
    "selection_bias": "selection_bias",
    "competing_mechanisms": "model_discrimination",
    "policy_equity": "policy_multi_outcome",
    "value_of_info": "evidence_design",
    "methodology": "methodology",
    "immunotherapy": "tradeoff_multi_outcome",
    "social_media": "descriptive",
    "football": "system_mapping",
    "chemical": "optimization",
    "smoking": "paradox_causal",
    "treatment_het": "heterogeneity_deep",
    "coral": "mechanism_discovery",
    "soil": "environmental_pathway",
    "school": "social_determinants",
    "microbiome": "system_mapping_multi",
}


def classify_scenario(exp_name: str) -> str:
    """Classify experiment into scenario type."""
    name = exp_name.lower()
    for key, scenario in SCENARIO_MAP.items():
        if key in name:
            return scenario
    return "unknown"


# ── LLM client ───────────────────────────────────────────────────────
def build_llm():
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

    return call, client, model


def build_llm_for_catalog(client, model_name):
    """Build the llm_call function needed by compile_episode_claims."""

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

    return llm_call


# ── Helpers ───────────────────────────────────────────────────────────
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
        return json.loads(text[start : end + 1])
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


def build_variable_info(world, summary):
    """Build variable lines for LLM context."""
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
    return "\n".join(var_lines)


def build_variable_descriptions(world, summary):
    """Build variable descriptions dict for ExtractionContext."""
    variable_descriptions = {}
    for name in summary.observable_names:
        meta = world.variable_meta.get(name)
        if not meta or not (meta.description or meta.unit):
            continue
        desc = meta.description.rstrip(".") if meta.description else ""
        if meta.unit:
            desc = f"{desc} [unit: {meta.unit}]" if desc else f"unit: {meta.unit}"
        variable_descriptions[name] = desc
    return variable_descriptions


# ── Metric computation helpers ────────────────────────────────────────
def vars_in_spec(spec: AtomicSpec) -> set[str]:
    """Extract all variable names referenced by an AtomicSpec."""
    vs = set()
    for arm in spec.arms:
        if arm.values:
            vs.update(arm.values.keys())
        if arm.condition_on:
            vs.update(arm.condition_on.keys())
        if arm.treatment:
            vs.add(arm.treatment)
        if arm.outcome:
            vs.add(arm.outcome)
        if arm.adjust_set:
            vs.update(arm.adjust_set)
    m = spec.measurement
    if m.target:
        vs.add(m.target)
    if m.lhs:
        vs.add(m.lhs)
    if m.rhs:
        vs.add(m.rhs)
    if m.cond_set:
        vs.update(m.cond_set)
    if m.treatment:
        vs.add(m.treatment)
    if m.outcome:
        vs.add(m.outcome)
    return vs


def sq_key_vars(sq: SubQuestionIntent) -> set[str]:
    """Get the key variables (treatment + outcome) from a sub-question."""
    vs = set()
    if sq.roles:
        if sq.roles.treatment:
            vs.add(sq.roles.treatment)
        if sq.roles.outcome:
            vs.add(sq.roles.outcome)
        if sq.roles.mediator:
            vs.add(sq.roles.mediator)
        if sq.roles.modifier:
            vs.add(sq.roles.modifier)
        if sq.roles.confounder:
            vs.add(sq.roles.confounder)
        if sq.roles.ranking_vars:
            vs.update(sq.roles.ranking_vars)
    return vs


def measurement_fingerprint(spec: AtomicSpec) -> str:
    """Create a fingerprint for redundancy detection."""
    m = spec.measurement
    target = m.target or ""
    lhs = m.lhs or ""
    rhs = m.rhs or ""
    return f"{m.kind}|{target}|{lhs}|{rhs}"


# ── Catalog path ──────────────────────────────────────────────────────
def run_catalog(claims_raw, world, summary, sqs, src, llm_call_catalog):
    """Run catalog compilation + verification + SQ scoring."""
    claim_cards = []
    for rc in claims_raw:
        claim_cards.append(
            ClaimCard(
                claim_id=rc["claim_id"],
                claim_text=rc["claim_text"],
                focus_variables=rc.get("focus_variables", [])[:8],
                confidence=rc.get("confidence", 0.5),
                evidence_basis=rc.get("evidence_basis", [
                    {"artifact_id": "x", "rationale": "Analysis from solver"}
                ]),
            )
        )

    ctx = ExtractionContext(
        research_brief=src["problem"].get("research_question", ""),
        domain=src["problem"].get("domain", ""),
        description=src["problem"].get("description", ""),
        title=src["problem"].get("title", ""),
        variable_descriptions=build_variable_descriptions(world, summary),
        sub_questions=[
            {
                "sq_id": sq.sq_id,
                "pattern": sq.pattern,
                "text_gloss": sq.text_gloss or sq.sq_id,
            }
            for sq in sqs
        ],
    )

    compiled = compile_episode_claims(
        claim_cards, summary, llm_call=llm_call_catalog, context=ctx,
    )

    # Verify each unit's specs against SCM
    solver = SCMSolver(world, n_mc=20_000)
    claim_verdicts = {}  # claim_id -> list[AtomVerdict]
    claim_intents_with_truth = []  # [(ClaimIntent, truth_score)] per unit

    for co in compiled:
        if not isinstance(co, CompilerOutput) or not co.compiled:
            continue
        verdicts = []
        for unit in co.units:
            unit_verdicts = []
            for spec in unit.specs:
                try:
                    v = verify_atom(spec, world, solver, 20_000, 42)
                    verdicts.append(v)
                    unit_verdicts.append(v)
                except Exception:
                    pass
            unit_truth = (
                1.0 if unit_verdicts and all(v.solver_assertion_holds for v in unit_verdicts)
                else 0.0
            )
            claim_intents_with_truth.append((unit.intent, unit_truth))
        claim_verdicts[co.claim_id] = verdicts

    # Resolve SQs and score
    sq_score = None
    resolved_sqs = []
    if sqs and claim_intents_with_truth:
        for sq in sqs:
            try:
                rsq = resolve_subquestion(sq, world, summary, solver, 20_000, 42)
                resolved_sqs.append(rsq)
            except Exception:
                pass
        if resolved_sqs:
            sq_score = score_episode_with_subquestions(
                claim_intents_with_truth, resolved_sqs,
            )

    return {
        "compiled": compiled,
        "claim_verdicts": claim_verdicts,
        "sq_score": sq_score,
        "resolved_sqs": resolved_sqs,
        "claim_intents_with_truth": claim_intents_with_truth,
    }


# ── Direct path ───────────────────────────────────────────────────────
def run_direct(claims_raw, world, summary, solver, llm_call, src):
    """Run direct LLM -> AtomicSpec compilation + verification."""
    variables_info = build_variable_info(world, summary)
    brief = src["problem"].get("research_question", "")

    system = f"""You are a verification compiler. Given a research claim and world
variables, produce AtomicSpec(s) that verify whether the claim is true in a
structural causal model (SCM).

Research context: {brief}

{GRAMMAR_REF}

Think about what the claim actually asserts, then produce specs to check it.
Each spec should test ONE specific aspect of the claim."""

    results = {}  # claim_id -> {specs, verdicts, raw_count, ...}
    for rc in claims_raw:
        cid = rc["claim_id"]
        user = (
            f'Claim: "{rc["claim_text"]}"\n\n'
            f"Variables in this world:\n{variables_info}\n\n"
            f"Produce AtomicSpec(s) to verify this claim."
        )
        raw = llm_call(system, user)
        spec_dicts = parse_specs(raw)

        specs = []
        verdicts = []
        errors = 0
        for sd in spec_dicts:
            try:
                coerce_tuples(sd)
                spec = AtomicSpec(**sd)
                verdict = verify_atom(spec, world, solver, 20_000, 42)
                specs.append(spec)
                verdicts.append(verdict)
            except Exception:
                errors += 1

        results[cid] = {
            "specs": specs,
            "verdicts": verdicts,
            "raw_count": len(spec_dicts),
            "errors": errors,
        }

    return results


# ── Compute all 5 metrics ────────────────────────────────────────────
def compute_metrics(
    claims_raw,
    catalog_result,
    direct_result,
    sqs,
):
    """Compute all 5 metric groups for both paths."""

    def _sq_proxy_metrics_from_true_specs(
        sqs_list: list[SubQuestionIntent],
        specs_by_claim: dict[str, list[AtomicSpec]],
    ) -> dict:
        matched = 0
        detail = []
        for sq in sqs_list:
            sq_vars = sq_key_vars(sq)
            sq_hit = False
            for cid, specs in specs_by_claim.items():
                for spec in specs:
                    spec_vars = vars_in_spec(spec)
                    if sq_vars and sq_vars & spec_vars:
                        sq_hit = True
                        break
                if sq_hit:
                    break
            if sq_hit:
                matched += 1
            detail.append({
                "sq_id": sq.sq_id,
                "matched": sq_hit,
                "key_vars": sorted(sq_vars),
            })
        total = len(sqs_list)
        return {
            "coverage": matched / total if total else 0,
            "sqs_matched": matched,
            "sqs_total": total,
            "detail": detail,
        }

    n_claims = len(claims_raw)

    # ── M1: Compile rate / abstentions ──
    cat_compiled_list = catalog_result["compiled"]
    cat_n_compiled = sum(
        1 for co in cat_compiled_list
        if isinstance(co, CompilerOutput) and co.compiled
    )
    cat_n_abstention = sum(
        1 for co in cat_compiled_list
        if isinstance(co, CompilerOutput) and not co.compiled
    )
    cat_n_units = sum(
        len(co.units) for co in cat_compiled_list
        if isinstance(co, CompilerOutput) and co.compiled
    )

    dir_n_with_specs = sum(
        1 for v in direct_result.values() if v["specs"]
    )
    dir_n_no_specs = n_claims - dir_n_with_specs
    dir_total_specs = sum(len(v["specs"]) for v in direct_result.values())
    dir_total_errors = sum(v["errors"] for v in direct_result.values())
    dir_total_raw = sum(v["raw_count"] for v in direct_result.values())

    m1 = {
        "catalog": {
            "compiled": cat_n_compiled,
            "abstentions": cat_n_abstention,
            "compile_rate": cat_n_compiled / n_claims if n_claims else 0,
            "units": cat_n_units,
        },
        "direct": {
            "compiled": dir_n_with_specs,
            "abstentions": dir_n_no_specs,
            "compile_rate": dir_n_with_specs / n_claims if n_claims else 0,
            "valid_specs": dir_total_specs,
            "raw_specs": dir_total_raw,
            "parse_errors": dir_total_errors,
        },
    }

    # ── M2: Semantic preservation ──
    # Variable coverage: what fraction of claim's focus_variables appear in specs
    cat_var_coverages = []
    dir_var_coverages = []
    cat_meas_diversity = []
    dir_meas_diversity = []

    for rc in claims_raw:
        cid = rc["claim_id"]
        focus = set(rc.get("focus_variables", []))

        # Catalog: vars referenced in compiled specs
        cat_vars = set()
        cat_meas_kinds = set()
        for co in cat_compiled_list:
            if not isinstance(co, CompilerOutput):
                continue
            if co.claim_id != cid or not co.compiled:
                continue
            for unit in co.units:
                if unit.intent.treatment:
                    cat_vars.add(unit.intent.treatment)
                if unit.intent.outcome:
                    cat_vars.add(unit.intent.outcome)
                if unit.intent.mediator:
                    cat_vars.add(unit.intent.mediator)
                if unit.intent.modifier:
                    cat_vars.add(unit.intent.modifier)
                if unit.intent.confounder:
                    cat_vars.add(unit.intent.confounder)
                if unit.intent.ranking_vars:
                    cat_vars.update(unit.intent.ranking_vars)
                for spec in unit.specs:
                    cat_vars.update(vars_in_spec(spec))
                    cat_meas_kinds.add(str(spec.measurement.kind))

        if focus:
            cat_var_coverages.append(len(focus & cat_vars) / len(focus))
        cat_meas_diversity.append(len(cat_meas_kinds))

        # Direct: vars referenced in specs
        dr = direct_result.get(cid, {"specs": [], "verdicts": []})
        dir_vars = set()
        dir_meas_kinds = set()
        for spec in dr["specs"]:
            dir_vars.update(vars_in_spec(spec))
            dir_meas_kinds.add(str(spec.measurement.kind))

        if focus:
            dir_var_coverages.append(len(focus & dir_vars) / len(focus))
        dir_meas_diversity.append(len(dir_meas_kinds))

    m2 = {
        "catalog": {
            "avg_var_coverage": (
                sum(cat_var_coverages) / len(cat_var_coverages)
                if cat_var_coverages else 0
            ),
            "avg_measurement_diversity": (
                sum(cat_meas_diversity) / len(cat_meas_diversity)
                if cat_meas_diversity else 0
            ),
        },
        "direct": {
            "avg_var_coverage": (
                sum(dir_var_coverages) / len(dir_var_coverages)
                if dir_var_coverages else 0
            ),
            "avg_measurement_diversity": (
                sum(dir_meas_diversity) / len(dir_meas_diversity)
                if dir_meas_diversity else 0
            ),
        },
    }

    # ── M3: Truth rate ──
    cat_verdicts = catalog_result["claim_verdicts"]
    cat_truth_per_claim = []
    cat_specs_true = 0
    cat_specs_total = 0
    for cid, vs in cat_verdicts.items():
        if vs:
            cat_truth_per_claim.append(
                min(v.score for v in vs) if vs else 0.0
            )
            cat_specs_total += len(vs)
            cat_specs_true += sum(1 for v in vs if v.solver_assertion_holds)

    dir_truth_per_claim = []
    dir_specs_true = 0
    dir_specs_total = 0
    for cid, dr in direct_result.items():
        vs = dr["verdicts"]
        dir_specs_total += len(vs)
        n_true = sum(1 for v in vs if v.solver_assertion_holds)
        dir_specs_true += n_true
        if vs:
            dir_truth_per_claim.append(n_true / len(vs))

    m3 = {
        "catalog": {
            "claim_truth_rate": (
                sum(cat_truth_per_claim) / len(cat_truth_per_claim)
                if cat_truth_per_claim else 0
            ),
            "spec_truth_rate": (
                cat_specs_true / cat_specs_total if cat_specs_total else 0
            ),
            "n_claims_verified": len(cat_truth_per_claim),
            "specs_true": cat_specs_true,
            "specs_total": cat_specs_total,
        },
        "direct": {
            "spec_truth_rate": (
                dir_specs_true / dir_specs_total if dir_specs_total else 0
            ),
            "claim_all_true_rate": (
                sum(1 for x in dir_truth_per_claim if x == 1.0) / len(dir_truth_per_claim)
                if dir_truth_per_claim else 0
            ),
            "claim_avg_truth": (
                sum(dir_truth_per_claim) / len(dir_truth_per_claim)
                if dir_truth_per_claim else 0
            ),
            "specs_true": dir_specs_true,
            "specs_total": dir_specs_total,
        },
    }

    # ── M4: SQ coverage ──
    cat_sq = catalog_result.get("sq_score")
    cat_sq_metrics = {}
    if cat_sq:
        cat_sq_metrics = {
            "coverage": cat_sq.coverage,
            "weighted_coverage": cat_sq.weighted_coverage,
            "correctness": cat_sq.correctness,
            "total": cat_sq.total,
            "sqs_matched": sum(1 for s in cat_sq.sq_scores if s.matched),
            "sqs_total": len(cat_sq.sq_scores),
        }

    # Comparable SQ proxy for BOTH paths: true specs whose variables overlap SQ key vars.
    # This is weaker than full SQ scoring but comparable across direct/catalog outputs.
    cat_true_specs_by_claim = {
        cid: [v.spec for v in verdicts if v.solver_assertion_holds]
        for cid, verdicts in cat_verdicts.items()
    }
    dir_true_specs_by_claim = {
        cid: [v.spec for v in dr["verdicts"] if v.solver_assertion_holds]
        for cid, dr in direct_result.items()
    }
    cat_sq_proxy = _sq_proxy_metrics_from_true_specs(sqs, cat_true_specs_by_claim)
    dir_sq_proxy = _sq_proxy_metrics_from_true_specs(sqs, dir_true_specs_by_claim)

    m4 = {
        "catalog_actual": cat_sq_metrics,
        "catalog_proxy": cat_sq_proxy,
        "direct_proxy": dir_sq_proxy,
    }

    # ── M5: Over-generation ──
    cat_specs_per_claim = []
    for co in cat_compiled_list:
        if isinstance(co, CompilerOutput) and co.compiled:
            n_specs = sum(len(u.specs) for u in co.units)
            cat_specs_per_claim.append(n_specs)

    dir_specs_per_claim = []
    dir_redundancy_counts = []
    for cid, dr in direct_result.items():
        n = len(dr["specs"])
        dir_specs_per_claim.append(n)
        # Redundancy: specs with same measurement fingerprint
        fps = [measurement_fingerprint(s) for s in dr["specs"]]
        unique = len(set(fps))
        dir_redundancy_counts.append(n - unique)

    m5 = {
        "catalog": {
            "avg_specs_per_claim": (
                sum(cat_specs_per_claim) / len(cat_specs_per_claim)
                if cat_specs_per_claim else 0
            ),
            "max_specs_per_claim": max(cat_specs_per_claim, default=0),
        },
        "direct": {
            "avg_specs_per_claim": (
                sum(dir_specs_per_claim) / len(dir_specs_per_claim)
                if dir_specs_per_claim else 0
            ),
            "max_specs_per_claim": max(dir_specs_per_claim, default=0),
            "total_redundant": sum(dir_redundancy_counts),
            "avg_redundant_per_claim": (
                sum(dir_redundancy_counts) / len(dir_redundancy_counts)
                if dir_redundancy_counts else 0
            ),
        },
    }

    return {
        "compile_rate": m1,
        "semantic_preservation": m2,
        "truth_rate": m3,
        "sq_coverage": m4,
        "over_generation": m5,
    }


# ── Process one experiment ────────────────────────────────────────────
def process_experiment(exp_dir: Path, llm_call, client, model_name):
    """Process one experiment: both paths + all metrics."""
    exp_name = exp_dir.name
    scenario = classify_scenario(exp_name)
    print(f"\n{'=' * 70}")
    print(f"  {exp_name}  [{scenario}]")
    print(f"{'=' * 70}")

    with open(exp_dir / "src.json") as f:
        src = json.load(f)
    with open(exp_dir / "oi_result.json") as f:
        result = json.load(f)

    claims_raw = get_claims(result)
    if not claims_raw:
        print("  No claims submitted. Skipping.")
        return None

    print(f"  Claims: {len(claims_raw)}")

    world = reconstruct_world(src)
    target = src["problem"].get("target") or src["problem"].get("target_node")
    summary = build_world_summary(world, target, n_mc=20_000, seed=42)
    solver = SCMSolver(world, n_mc=20_000)
    sqs = [SubQuestionIntent(**sq) for sq in src.get("sub_questions", [])]
    print(f"  SQs: {len(sqs)}")

    # ── Catalog path ──
    t0 = time.time()
    print("  [catalog] compiling + verifying...")
    llm_call_catalog = build_llm_for_catalog(client, model_name)
    catalog_result = run_catalog(claims_raw, world, summary, sqs, src, llm_call_catalog)
    cat_time = time.time() - t0
    print(f"  [catalog] done ({cat_time:.1f}s)")

    # ── Direct path ──
    t0 = time.time()
    print("  [direct] compiling + verifying...")
    direct_result = run_direct(claims_raw, world, summary, solver, llm_call, src)
    dir_time = time.time() - t0
    print(f"  [direct] done ({dir_time:.1f}s)")

    # ── Compute metrics ──
    metrics = compute_metrics(claims_raw, catalog_result, direct_result, sqs)

    # ── Per-claim detail ──
    print(f"\n  Per-claim detail:")
    for rc in claims_raw:
        cid = rc["claim_id"]
        # Catalog
        cat_info = "ABSTENTION"
        for co in catalog_result["compiled"]:
            if isinstance(co, CompilerOutput) and co.claim_id == cid:
                if co.compiled:
                    n_units = len(co.units)
                    patterns = [str(u.intent.pattern) for u in co.units]
                    cat_info = f"{n_units} units ({', '.join(patterns)})"
                break
        # Direct
        dr = direct_result.get(cid, {"specs": [], "verdicts": [], "errors": 0})
        n_true = sum(1 for v in dr["verdicts"] if v.solver_assertion_holds)
        dir_info = f"{len(dr['specs'])} specs, {n_true} TRUE, {dr['errors']} errors"

        print(f"    {cid}: '{rc['claim_text'][:70]}...'")
        print(f"      catalog: {cat_info}")
        print(f"      direct:  {dir_info}")

    # ── Summary ──
    m1 = metrics["compile_rate"]
    m3 = metrics["truth_rate"]
    m4 = metrics["sq_coverage"]
    print(f"\n  SUMMARY:")
    print(f"    Compile:  catalog {m1['catalog']['compile_rate']:.0%} "
          f"({m1['catalog']['units']} units) | "
          f"direct {m1['direct']['compile_rate']:.0%} "
          f"({m1['direct']['valid_specs']} specs)")
    print(f"    Truth:    catalog {m3['catalog']['spec_truth_rate']:.2f} | "
          f"direct {m3['direct']['spec_truth_rate']:.2f} "
          f"({m3['direct']['specs_true']}/{m3['direct']['specs_total']})")
    print(f"    SQ proxy: catalog {m4['catalog_proxy']['coverage']:.2f} | "
          f"direct {m4['direct_proxy']['coverage']:.2f}")
    if m4["catalog_actual"]:
        print(f"    SQ actual (catalog scorer): {m4['catalog_actual']['coverage']:.2f} "
              f"(weighted {m4['catalog_actual']['weighted_coverage']:.2f})")

    return {
        "experiment": exp_name,
        "scenario": scenario,
        "n_claims": len(claims_raw),
        "n_sqs": len(sqs),
        "metrics": metrics,
        "time_catalog": round(cat_time, 1),
        "time_direct": round(dir_time, 1),
    }


# ── Summary table ─────────────────────────────────────────────────────
def print_summary_table(results):
    """Print final comparison table."""
    print(f"\n\n{'#' * 80}")
    print(f"# COMPILER BENCHMARK SUMMARY")
    print(f"{'#' * 80}")

    # Header
    hdr = (f"{'Experiment':<30} {'Type':<20} {'Clm':>3} "
           f"{'Cat.C%':>6} {'Dir.C%':>6} "
           f"{'Cat.Tru':>7} {'Dir.Tru':>7} "
           f"{'Cat.SQp':>7} {'Dir.SQp':>7} "
           f"{'Cat.Sp':>6} {'Dir.Sp':>6}")
    print(f"\n{hdr}")
    print("-" * len(hdr))

    for r in results:
        m = r["metrics"]
        m1 = m["compile_rate"]
        m3 = m["truth_rate"]
        m4 = m["sq_coverage"]
        m5 = m["over_generation"]
        cat_cov = m4["catalog_proxy"]["coverage"]

        print(
            f"{r['experiment']:<30} {r['scenario']:<20} {r['n_claims']:>3} "
            f"{m1['catalog']['compile_rate']:>5.0%} {m1['direct']['compile_rate']:>5.0%} "
            f"{m3['catalog']['spec_truth_rate']:>7.2f} {m3['direct']['spec_truth_rate']:>7.2f} "
            f"{cat_cov:>7.2f} {m4['direct_proxy']['coverage']:>7.2f} "
            f"{m5['catalog']['avg_specs_per_claim']:>6.1f} {m5['direct']['avg_specs_per_claim']:>6.1f}"
        )

    # Aggregates
    if results:
        print("-" * len(hdr))
        tc = sum(r["n_claims"] for r in results)
        cat_cr = sum(
            r["metrics"]["compile_rate"]["catalog"]["compiled"] for r in results
        ) / tc if tc else 0
        dir_cr = sum(
            r["metrics"]["compile_rate"]["direct"]["compiled"] for r in results
        ) / tc if tc else 0
        cat_trs = [
            r["metrics"]["truth_rate"]["catalog"]["spec_truth_rate"]
            for r in results if r["metrics"]["truth_rate"]["catalog"]["n_claims_verified"]
        ]
        dir_trs = [
            r["metrics"]["truth_rate"]["direct"]["spec_truth_rate"]
            for r in results if r["metrics"]["truth_rate"]["direct"]["specs_total"]
        ]
        cat_sqc = [
            r["metrics"]["sq_coverage"]["catalog_proxy"]["coverage"]
            for r in results
        ]
        dir_sqc = [
            r["metrics"]["sq_coverage"]["direct_proxy"]["coverage"]
            for r in results
        ]

        cat_tr = sum(cat_trs) / len(cat_trs) if cat_trs else 0
        dir_tr = sum(dir_trs) / len(dir_trs) if dir_trs else 0
        cat_sq = sum(cat_sqc) / len(cat_sqc) if cat_sqc else 0
        dir_sq = sum(dir_sqc) / len(dir_sqc) if dir_sqc else 0

        print(
            f"{'AVERAGE':<30} {'':<20} {tc:>3} "
            f"{cat_cr:>5.0%} {dir_cr:>5.0%} "
            f"{cat_tr:>7.2f} {dir_tr:>7.2f} "
            f"{cat_sq:>6.2f} {dir_sq:>6.2f} "
        )

    # Metric legend
    print(f"\nLegend:")
    print(f"  Cat.C% / Dir.C% = compile rate (claims that produced verifiable output)")
    print(f"  Cat.Tru / Dir.Tru = spec truth rate (fraction of verified specs that hold)")
    print(f"  Cat.SQp / Dir.SQp = SQ proxy coverage via true-spec variable overlap")
    print(f"  Cat.Sp / Dir.Sp = avg specs per compiled claim (over-generation indicator)")


# ── Main ──────────────────────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Benchmark catalog vs direct compilation across experiments"
    )
    parser.add_argument("experiments", nargs="+", help="Experiment directories")
    parser.add_argument("--output", "-o", help="Output JSON file")
    args = parser.parse_args()

    llm_call, client, model_name = build_llm()
    results = []

    for exp_path in sorted(args.experiments):
        exp_dir = Path(exp_path)
        if not exp_dir.is_dir():
            continue
        if not (exp_dir / "src.json").exists():
            continue
        if not (exp_dir / "oi_result.json").exists():
            continue
        try:
            r = process_experiment(exp_dir, llm_call, client, model_name)
            if r:
                results.append(r)
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    print_summary_table(results)

    # Semantic preservation aggregate
    if results:
        print(f"\n{'#' * 80}")
        print(f"# SEMANTIC PRESERVATION DETAIL")
        print(f"{'#' * 80}")
        cat_vc = [r["metrics"]["semantic_preservation"]["catalog"]["avg_var_coverage"]
                  for r in results]
        dir_vc = [r["metrics"]["semantic_preservation"]["direct"]["avg_var_coverage"]
                  for r in results]
        cat_md = [r["metrics"]["semantic_preservation"]["catalog"]["avg_measurement_diversity"]
                  for r in results]
        dir_md = [r["metrics"]["semantic_preservation"]["direct"]["avg_measurement_diversity"]
                  for r in results]
        print(f"\n  Variable coverage (of claim's focus_variables):")
        print(f"    Catalog avg: {sum(cat_vc) / len(cat_vc):.2f}")
        print(f"    Direct  avg: {sum(dir_vc) / len(dir_vc):.2f}")
        print(f"\n  Measurement diversity (distinct kinds per claim):")
        print(f"    Catalog avg: {sum(cat_md) / len(cat_md):.1f}")
        print(f"    Direct  avg: {sum(dir_md) / len(dir_md):.1f}")

    # Over-generation aggregate
    if results:
        print(f"\n{'#' * 80}")
        print(f"# OVER-GENERATION DETAIL")
        print(f"{'#' * 80}")
        dir_red = sum(
            r["metrics"]["over_generation"]["direct"]["total_redundant"]
            for r in results
        )
        dir_tot = sum(
            r["metrics"]["compile_rate"]["direct"]["valid_specs"]
            for r in results
        )
        print(f"\n  Direct path redundancy:")
        print(f"    Total redundant specs: {dir_red} / {dir_tot} "
              f"({dir_red / dir_tot:.0%})" if dir_tot else "    N/A")

    # Save JSON
    if args.output and results:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
