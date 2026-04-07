#!/usr/bin/env python
"""P06 paired exact: re-run OI investigation with frozen src.json.

Phase C of the bundling experiment. Removes the drift confound from the
smoke run by reusing the EXACT same SCM, problem, and sub_questions_v2
that p05_canonical_batch used. The only thing that changes is the new
solver prompt + relaxed claim cap (15) — both already in working tree.

Conditions enforced (per Cursor's review):
  1. Use frozen src.json EXACTLY (problem + sub_questions_v2, no regen).
  2. Hold fixed: model, max_iterations, temperature, runner_config.

Compares against the same baseline directory case-by-case. Run
scripts/p06_smoke_gate.py afterwards on this batch to get the paired delta.

Read src + frozen run config from baseline:
  results/p05_canonical_batch/<case>/src.json
  results/p05_canonical_batch/<case>/oi_result.json (for runner_config + models)

Writes new oi_result.json to:
  results/p06_paired/<case>/src.json (copied from baseline)
  results/p06_paired/<case>/oi_result.json (newly generated)
"""
from __future__ import annotations

import argparse
import hashlib
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


def world_fingerprint(world) -> dict:
    """Structural fingerprint of a reconstructed SCMWorld.

    Captures id + sorted variables + sorted edges. Two worlds with the
    same fingerprint have the same DAG structure (does NOT verify equation
    coefficients — those are deterministic from seed=42 + scm_args, which
    we already pin via reconstruct_world).
    """
    edges = []
    for child, parents in world.graph.items():
        for parent in parents:
            edges.append([parent, child])
    payload = {
        "id": world.id,
        "variables": sorted(world.variables),
        "edges": sorted(edges),
        "n_vars": len(world.variables),
        "n_edges": len(edges),
    }
    h = hashlib.sha1(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return {
        "hash": h,
        "n_vars": payload["n_vars"],
        "n_edges": payload["n_edges"],
        "id": payload["id"],
    }


def reconstruct_world(src: dict):
    """Reconstruct SCMWorld from scm_construct args (mirror rescore.py).

    This is deterministic reconstruction from frozen JSON inputs (same
    SCMSpec, same seed=42, same SCMWorldGenTool). Identical to what
    rescore.py does — not a fresh LLM-driven world generation.
    """
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
    """Build compiler llm_call (messages-protocol) — mirrors generate_src.py."""
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
    baseline_dir: Path,
    out_dir: Path,
) -> dict:
    """Re-run a single case with frozen SCM + new prompt/cap."""
    from openai import OpenAI

    from sreg.models.research_problem import ResearchProblem
    from sreg.models.open_investigation import SubQuestionIntentV2
    from sreg.tools.oi_driver import run_oi_investigation
    from sreg.tools.oi_runner import OIEpisodeRunner

    src_path = baseline_dir / case_name / "src.json"
    base_result_path = baseline_dir / case_name / "oi_result.json"

    if not src_path.exists() or not base_result_path.exists():
        return {"case": case_name, "error": "missing src.json or oi_result.json"}

    src = json.load(open(src_path, encoding="utf-8"))
    base_res = json.load(open(base_result_path, encoding="utf-8"))

    # === Frozen inputs (deterministic reconstruction from src.json) ===
    world = reconstruct_world(src)
    fp = world_fingerprint(world)
    print(f"  [{case_name}] world fingerprint: hash={fp['hash']} "
          f"vars={fp['n_vars']} edges={fp['n_edges']} id={fp['id']}")

    problem = ResearchProblem(**src["problem"])
    sqs_v2_raw = src.get("sub_questions_v2", [])
    if not sqs_v2_raw:
        return {"case": case_name, "error": "no sub_questions_v2 in src.json"}
    sqs_v2 = [SubQuestionIntentV2(**sq) for sq in sqs_v2_raw]

    # === Frozen runner config (from baseline oi_result.json) ===
    si = base_res.get("score_inputs_v2", {})
    runner_cfg = si.get("runner_config", {"seed": 42, "n_mc": 20_000})
    seed = runner_cfg.get("seed", 42)
    n_mc = runner_cfg.get("n_mc", 20_000)

    # === Frozen models (from baseline oi_result.json) ===
    solver_model = base_res.get("solver_model") or os.environ.get(
        "AZURE_SOLVER_MODEL", "gpt-5.2-codex"
    )
    compiler_model = base_res.get("compiler_model") or os.environ.get(
        "AZURE_MODEL", "gpt-5.4"
    )

    # === Build clients ===
    base_url = os.environ.get("AZURE_FOUNDRY_BASE_URL", "")
    api_key = os.environ.get("AZURE_INFERENCE_CREDENTIAL", "")
    if not base_url or not api_key:
        return {"case": case_name, "error": "Azure env vars not set (.env)"}

    solver_client = OpenAI(base_url=base_url, api_key=api_key)
    compiler_client = OpenAI(base_url=base_url, api_key=api_key)
    llm_compiler = build_compiler_llm(compiler_client, compiler_model)

    # === Build runner with frozen problem + world ===
    runner = OIEpisodeRunner(
        problem, world,
        seed=seed, n_mc=n_mc, llm_call=llm_compiler,
    )
    runner.set_subquestions_v2(sqs_v2)

    # === Run investigation (atomic prompt + cap=15 from working tree) ===
    print(f"  [{case_name}] solver={solver_model} compiler={compiler_model} "
          f"seed={seed} n_mc={n_mc}")
    print(f"  [{case_name}] running run_oi_investigation (max_iter=20, temp=0.0)...")
    t0 = time.time()
    oi_result = run_oi_investigation(
        runner, solver_client, solver_model,
        max_iterations=20, temperature=0.0,
    )
    elapsed = time.time() - t0

    # === Persist (mirror generate_src.py format) ===
    case_out_dir = out_dir / case_name
    case_out_dir.mkdir(parents=True, exist_ok=True)

    # Copy frozen src.json so p06_smoke_gate.py can load this directory
    shutil.copy(src_path, case_out_dir / "src.json")

    # Extract solver tool calls (mirror generate_src.py logic)
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
        "elapsed": elapsed,
        "n_steps": oi_result.n_steps,
        "submitted": oi_result.submitted,
        "score": oi_result.score.model_dump() if oi_result.score else None,
        "compiler_stats": runner.compiler_stats(),
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
        "ok": True,
        "elapsed_s": round(elapsed, 1),
        "n_steps": oi_result.n_steps,
        "submitted": oi_result.submitted,
        "n_claims": len(score_inputs.get("claims", [])) if score_inputs else 0,
        "correctness": round(getattr(sc, "correctness", 0.0), 3) if sc else None,
        "weighted_coverage": round(getattr(sc, "weighted_coverage", 0.0), 3) if sc else None,
        "total": round(getattr(sc, "total", 0.0), 3) if sc else None,
        "world_fingerprint": fp,
        "out_path": str(out_path),
    }
    print(f"  [{case_name}] done in {elapsed:.0f}s | "
          f"claims={summary['n_claims']} total={summary['total']}")
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--baseline", default="results/p05_canonical_batch",
        help="Baseline batch dir with frozen src.json + oi_result.json",
    )
    p.add_argument(
        "--out", default="results/p06_paired",
        help="Output dir for re-run cases",
    )
    p.add_argument(
        "--cases", nargs="+", required=True,
        help="Case names to re-run (e.g. microbiome coral_bleach)",
    )
    args = p.parse_args()

    baseline_dir = Path(args.baseline)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 80)
    print("  P06 PAIRED EXACT RUN")
    print("=" * 80)
    print(f"  baseline:   {baseline_dir}")
    print(f"  out:        {out_dir}")
    print(f"  cases:      {args.cases}")
    print()

    summaries = []
    for case in args.cases:
        try:
            summary = run_one_case(case, baseline_dir, out_dir)
        except Exception as e:
            import traceback
            traceback.print_exc()
            summary = {"case": case, "ok": False, "error": str(e)}
        summaries.append(summary)

    print()
    print("=" * 80)
    print("  RESULTS")
    print("=" * 80)
    for s in summaries:
        if s.get("ok"):
            print(f"  [OK]   {s['case']:<20} claims={s['n_claims']} "
                  f"total={s['total']} ({s['elapsed_s']}s)")
        else:
            print(f"  [FAIL] {s['case']:<20} {s.get('error', '')}")
    print()

    summary_path = out_dir / "_paired_run_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2)
    print(f"  Summary: {summary_path}")
    print()
    print("Next: scripts/p06_smoke_gate.py "
          f"--baseline {baseline_dir} --experimental {out_dir} "
          f"--out {out_dir / 'gate_report.json'}")
    print()


if __name__ == "__main__":
    main()
