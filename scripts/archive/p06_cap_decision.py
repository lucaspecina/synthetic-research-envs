#!/usr/bin/env python
"""P06 cap decision: paired A/B on claim cap (5 vs 15).

Runs each case TWICE with the same prompt, code, world, and config —
only MAX_CLAIMS differs between conditions. This isolates the effect of
the claim cap on solver behavior and scores.

Question (from p06_addendum_cap_decision.md):
  "Under the current atomic prompt and post-fix code, does cap=5 or
   cap=15 produce better scores for SREG v1?"

Design:
  - Frozen src.json from p05_canonical_batch (same world, problem, SQs)
  - Same atomic prompt (only the "1-N" line changes)
  - Same solver model, compiler model, seed, n_mc, temperature
  - Interleaved order: case_1 cap=5, case_1 cap=15, case_2 cap=5, ...
  - Canonical scoring path only (SQ v2 + LLM judge)

Output:
  results/p06_cap_decision/cap5/<case>/oi_result.json
  results/p06_cap_decision/cap15/<case>/oi_result.json
  results/p06_cap_decision/_summary.json  (per-run summaries)

Analysis: run separately (e.g. a future p06_cap_analyze.py).

See: research/notes/p06_addendum_cap_decision.md
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

# Inject repo root + load .env
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# All 12 cases in p05_canonical_batch
ALL_CASES = [
    "chemical", "competing_mech", "confounding", "coral_bleach",
    "heterogeneity", "identifiability", "immunotherapy", "microbiome",
    "missing_data", "policy_equity", "poverty", "selection_bias",
]


def reconstruct_world(src: dict):
    """Reconstruct SCMWorld from scm_construct args (mirrors rescore.py)."""
    from sreg.models.scm_spec import SCMSpec
    from sreg.tools.scm_world_gen import SCMWorldGenTool

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
        raise ValueError("No scm_construct call found in src.json")

    if scm_args.get("edges") and isinstance(scm_args["edges"][0], dict):
        scm_args["edges"] = [(e["from"], e["to"]) for e in scm_args["edges"]]

    spec = SCMSpec(**scm_args)
    gen = SCMWorldGenTool()
    return gen.generate(spec, seed=42)


def build_compiler_llm(client, model: str):
    """Build compiler llm_call (messages-protocol)."""
    def llm_compiler(messages: list[dict[str, str]]) -> str:
        instructions = messages[0]["content"] if messages else ""
        input_items = [
            {"role": m["role"], "content": m["content"]}
            for m in messages[1:]
        ]
        resp = client.responses.create(
            model=model, instructions=instructions, input=input_items,
        )
        for item in resp.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        return part.text
        return ""
    return llm_compiler


def run_one_case(
    case_name: str,
    claim_cap: int,
    baseline_dir: Path,
    out_dir: Path,
) -> dict:
    """Run a single case with a specific claim_cap."""
    from openai import OpenAI

    from sreg.models.open_investigation import load_sub_questions_v2_robust
    from sreg.models.research_problem import ResearchProblem
    from sreg.tools.oi_driver import build_oi_solver_tools, run_oi_investigation
    from sreg.tools.oi_runner import OIEpisodeRunner

    tag = f"cap={claim_cap}"
    src_path = baseline_dir / case_name / "src.json"
    base_result_path = baseline_dir / case_name / "oi_result.json"

    if not src_path.exists() or not base_result_path.exists():
        return {"case": case_name, "condition": tag, "error": "missing files"}

    src = json.load(open(src_path, encoding="utf-8"))
    base_res = json.load(open(base_result_path, encoding="utf-8"))

    # --- Frozen inputs ---
    world = reconstruct_world(src)
    problem = ResearchProblem(**src["problem"])
    sqs_v2_raw = src.get("sub_questions_v2", [])
    if not sqs_v2_raw:
        return {"case": case_name, "condition": tag, "error": "no SQs"}

    load_result = load_sub_questions_v2_robust(sqs_v2_raw)
    sqs_v2 = load_result.loaded
    if not sqs_v2:
        return {
            "case": case_name, "condition": tag,
            "error": "all SQs abstained by loader",
        }

    # --- Frozen config ---
    si = base_res.get("score_inputs_v2", {})
    runner_cfg = si.get("runner_config", {"seed": 42, "n_mc": 20_000})
    seed = runner_cfg.get("seed", 42)
    n_mc = runner_cfg.get("n_mc", 20_000)

    solver_model = base_res.get("solver_model") or os.environ.get(
        "AZURE_SOLVER_MODEL", "gpt-5.2-codex"
    )
    compiler_model = base_res.get("compiler_model") or os.environ.get(
        "AZURE_MODEL", "gpt-5.4"
    )

    # --- Clients ---
    base_url = os.environ.get("AZURE_FOUNDRY_BASE_URL", "")
    api_key = os.environ.get("AZURE_INFERENCE_CREDENTIAL", "")
    if not base_url or not api_key:
        return {"case": case_name, "condition": tag, "error": "Azure env missing"}

    solver_client = OpenAI(base_url=base_url, api_key=api_key)
    compiler_client = OpenAI(base_url=base_url, api_key=api_key)
    llm_compiler = build_compiler_llm(compiler_client, compiler_model)

    # --- Runner with explicit claim_cap ---
    runner = OIEpisodeRunner(
        problem, world,
        seed=seed, n_mc=n_mc, llm_call=llm_compiler,
        claim_cap=claim_cap,
    )
    runner.set_subquestions_v2(sqs_v2)

    # --- Snapshot of tool schema for auditability ---
    solver_tools = build_oi_solver_tools(claim_cap)
    submit_tool_schema = next(
        t for t in solver_tools if t["function"]["name"] == "submit_claims"
    )

    # --- Run ---
    print(f"  [{case_name}] {tag} solver={solver_model} seed={seed} n_mc={n_mc}")
    t0 = time.time()
    oi_result = run_oi_investigation(
        runner, solver_client, solver_model,
        max_iterations=20, temperature=0.0,
    )
    elapsed = time.time() - t0

    # --- Persist ---
    cap_label = f"cap{claim_cap}"
    case_out_dir = out_dir / cap_label / case_name
    case_out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(src_path, case_out_dir / "src.json")

    # Extract solver tool calls
    solver_tool_calls = []
    for msg in oi_result.messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                entry = {"name": fn.get("name", ""), "step": len(solver_tool_calls)}
                if fn.get("name") == "submit_claims":
                    try:
                        entry["args"] = json.loads(fn.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        entry["args"] = fn.get("arguments", "")
                solver_tool_calls.append(entry)

    oi_json = {
        "world": problem.world_id,
        "solver_model": solver_model,
        "compiler_model": compiler_model,
        "claim_cap": claim_cap,
        "submit_claims_tool_schema": submit_tool_schema,
        "elapsed": elapsed,
        "n_steps": oi_result.n_steps,
        "submitted": oi_result.submitted,
        "score": oi_result.score.model_dump() if oi_result.score else None,
        "compiler_stats": runner.compiler_stats(),
        "loader_diagnostics": load_result.model_dump(mode="json"),
        "solver_tool_calls": solver_tool_calls,
        "conversation": oi_result.messages,
    }
    score_inputs = runner.get_score_inputs()
    if score_inputs:
        oi_json["score_inputs_v2"] = score_inputs

    out_path = case_out_dir / "oi_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(oi_json, f, indent=2)

    sc = oi_result.score
    summary = {
        "case": case_name,
        "condition": cap_label,
        "claim_cap": claim_cap,
        "ok": True,
        "elapsed_s": round(elapsed, 1),
        "n_steps": oi_result.n_steps,
        "submitted": oi_result.submitted,
        "n_claims": len(score_inputs.get("claims", [])) if score_inputs else 0,
        "correctness": round(getattr(sc, "correctness", 0.0), 3) if sc else None,
        "weighted_coverage": (
            round(getattr(sc, "weighted_coverage", 0.0), 3) if sc else None
        ),
        "coverage": round(getattr(sc, "coverage", 0.0), 3) if sc else None,
        "total": round(getattr(sc, "total", 0.0), 3) if sc else None,
        "force_submitted": not oi_result.submitted and sc is not None,
        "out_path": str(out_path),
    }
    print(
        f"  [{case_name}] {tag} done in {elapsed:.0f}s | "
        f"claims={summary['n_claims']} total={summary['total']}"
    )
    return summary


def main():
    p = argparse.ArgumentParser(
        description="P06 cap decision: paired A/B on claim cap (5 vs 15).",
    )
    p.add_argument(
        "--baseline", default="results/p05_canonical_batch",
        help="Baseline batch dir (default: results/p05_canonical_batch)",
    )
    p.add_argument(
        "--out", default="results/p06_cap_decision",
        help="Output dir (default: results/p06_cap_decision)",
    )
    p.add_argument(
        "--cases", nargs="+", default=ALL_CASES,
        help="Case names (default: all 12)",
    )
    p.add_argument(
        "--caps", nargs="+", type=int, default=[5, 15],
        help="Claim caps to test (default: 5 15)",
    )
    args = p.parse_args()

    baseline_dir = Path(args.baseline)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    caps = args.caps

    print()
    print("=" * 70)
    print("  P06 CAP DECISION: paired A/B on claim cap")
    print(f"  Conditions: {' vs '.join(f'cap={c}' for c in caps)}")
    print(f"  Cases: {len(args.cases)}")
    print(f"  Total runs: {len(args.cases) * len(caps)}")
    print(f"  Baseline: {baseline_dir}")
    print(f"  Output:   {out_dir}")
    print("=" * 70)
    print()

    all_summaries = []
    errors = []

    # Interleaved: case_1 cap=5, case_1 cap=15, case_2 cap=5, ...
    for case in args.cases:
        for cap in caps:
            print(f"\n--- {case} cap={cap} ---")
            try:
                result = run_one_case(case, cap, baseline_dir, out_dir)
            except Exception as e:
                result = {
                    "case": case, "condition": f"cap{cap}",
                    "claim_cap": cap, "ok": False, "error": str(e),
                }
                print(f"  [{case}] cap={cap} ERROR: {e}")

            all_summaries.append(result)
            if not result.get("ok", False):
                errors.append(result)

    # --- Summary ---
    summary_path = out_dir / "_summary.json"
    summary_doc = {
        "experiment": "p06_cap_decision",
        "question": (
            "Under the current atomic prompt and post-fix code, "
            "does cap=5 or cap=15 produce better scores for SREG v1?"
        ),
        "protocol": "research/notes/p06_addendum_cap_decision.md",
        "caps_tested": caps,
        "n_cases": len(args.cases),
        "n_runs": len(all_summaries),
        "n_errors": len(errors),
        "runs": all_summaries,
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_doc, f, indent=2)

    # --- Print comparison table ---
    print()
    print("=" * 70)
    print("  RESULTS")
    print("=" * 70)
    print(
        f"{'case':<20} "
        + "  ".join(f"{'total_' + str(c):<10}" for c in caps)
        + f"  {'delta':<10}  {'n_claims_' + str(caps[0]):<12}  "
        f"{'n_claims_' + str(caps[-1]):<12}"
    )
    print("-" * 70)

    for case in args.cases:
        runs_by_cap = {}
        for s in all_summaries:
            if s["case"] == case and s.get("ok"):
                runs_by_cap[s["claim_cap"]] = s

        cols = []
        for c in caps:
            r = runs_by_cap.get(c)
            cols.append(f"{r['total']:<10.3f}" if r and r.get("total") is not None else "ERR       ")

        if len(caps) == 2 and all(c in runs_by_cap for c in caps):
            t0 = runs_by_cap[caps[0]].get("total")
            t1 = runs_by_cap[caps[1]].get("total")
            if t0 is not None and t1 is not None:
                delta = t1 - t0
                delta_str = f"{delta:+.3f}"
            else:
                delta_str = "---"
        else:
            delta_str = "---"

        nc = []
        for c in caps:
            r = runs_by_cap.get(c)
            nc.append(str(r["n_claims"]) if r else "?")

        print(f"{case:<20} {'  '.join(cols)}  {delta_str:<10}  {nc[0]:<12}  {nc[-1]:<12}")

    print()
    if errors:
        print(f"  ERRORS: {len(errors)}")
        for e in errors:
            print(f"    {e['case']} {e.get('condition', '?')}: {e.get('error', '?')}")
    else:
        print("  No errors.")

    print(f"\n  Summary written to: {summary_path}")
    print(f"  Analyze with P1/C1/C2/C3 criteria from the addendum.")
    print()


if __name__ == "__main__":
    main()
