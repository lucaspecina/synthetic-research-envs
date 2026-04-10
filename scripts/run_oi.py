#!/usr/bin/env python
"""Run the OI solver on an existing generated case.

Takes a case directory (containing src.json) and runs the Open
Investigation solver, producing oi_result.json. This is the "use" side
of the build->use handoff: generate_src.py builds the case, run_oi.py
runs the solver on it.

Usage:
    python scripts/run_oi.py results/my_case/
    python scripts/run_oi.py results/my_case/ --claim-cap 10
    python scripts/run_oi.py results/my_case/ --max-iterations 30

Requires:
    - src.json in the case directory (with sub_questions_v2)
    - Azure credentials in .env (AZURE_FOUNDRY_BASE_URL, AZURE_INFERENCE_CREDENTIAL)

See: CURRENT_STATE.md section "Config v1 congelada" for default values.
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


def reconstruct_world(src: dict):
    """Reconstruct SCMWorld from scm_construct args in src.json."""
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


def main():
    p = argparse.ArgumentParser(
        description="Run OI solver on an existing generated case.",
    )
    p.add_argument(
        "case_dir",
        help="Path to case directory containing src.json",
    )
    p.add_argument(
        "--claim-cap", type=int, default=15,
        help="Max claims the solver can submit (default: 15, v1 frozen)",
    )
    p.add_argument(
        "--max-iterations", type=int, default=20,
        help="Max solver iterations (default: 20)",
    )
    p.add_argument(
        "--temperature", type=float, default=0.0,
        help="Solver temperature (default: 0.0)",
    )
    p.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)",
    )
    p.add_argument(
        "--n-mc", type=int, default=20_000,
        help="Monte Carlo samples for verification (default: 20000)",
    )
    p.add_argument(
        "--solver-model", default=None,
        help="Solver model (default: AZURE_SOLVER_MODEL or gpt-5.2-codex)",
    )
    p.add_argument(
        "--compiler-model", default=None,
        help="Compiler/judge model (default: AZURE_MODEL or gpt-5.4)",
    )
    p.add_argument(
        "--out", default=None,
        help="Output directory (default: same as case_dir)",
    )
    args = p.parse_args()

    from openai import OpenAI

    from sreg.models.open_investigation import load_sub_questions_v2_robust
    from sreg.models.research_problem import ResearchProblem
    from sreg.tools.oi_driver import build_oi_solver_tools, run_oi_investigation
    from sreg.tools.oi_runner import OIEpisodeRunner

    case_dir = Path(args.case_dir)
    out_dir = Path(args.out) if args.out else case_dir
    src_path = case_dir / "src.json"

    if not src_path.exists():
        print(f"ERROR: {src_path} not found")
        sys.exit(1)

    src = json.load(open(src_path, encoding="utf-8"))

    # --- Reconstruct world ---
    print("Reconstructing world from src.json...")
    world = reconstruct_world(src)
    problem = ResearchProblem(**src["problem"])
    print(f"  World: {problem.world_id}")
    print(f"  Title: {problem.title}")

    # --- Load sub-questions ---
    sqs_v2_raw = src.get("sub_questions_v2", [])
    if not sqs_v2_raw:
        print("ERROR: No sub_questions_v2 in src.json")
        sys.exit(1)

    load_result = load_sub_questions_v2_robust(sqs_v2_raw)
    sqs_v2 = load_result.loaded
    if not sqs_v2:
        print("ERROR: All SQs abstained by loader")
        sys.exit(1)
    print(f"  SQs v2: {len(sqs_v2)} loaded")

    # --- Models ---
    solver_model = args.solver_model or os.environ.get(
        "AZURE_SOLVER_MODEL", "gpt-5.2-codex"
    )
    compiler_model = args.compiler_model or os.environ.get(
        "AZURE_MODEL", "gpt-5.4"
    )

    # --- Clients ---
    base_url = os.environ.get("AZURE_FOUNDRY_BASE_URL", "")
    api_key = os.environ.get("AZURE_INFERENCE_CREDENTIAL", "")
    if not base_url or not api_key:
        print("ERROR: Azure credentials missing. Set AZURE_FOUNDRY_BASE_URL "
              "and AZURE_INFERENCE_CREDENTIAL in .env")
        sys.exit(1)

    solver_client = OpenAI(base_url=base_url, api_key=api_key)
    compiler_client = OpenAI(base_url=base_url, api_key=api_key)
    llm_compiler = build_compiler_llm(compiler_client, compiler_model)

    # --- Build runner ---
    claim_cap = args.claim_cap
    runner = OIEpisodeRunner(
        problem, world,
        seed=args.seed, n_mc=args.n_mc, llm_call=llm_compiler,
        claim_cap=claim_cap,
    )
    runner.set_subquestions_v2(sqs_v2)

    solver_tools = build_oi_solver_tools(claim_cap)
    submit_tool_schema = next(
        t for t in solver_tools if t["function"]["name"] == "submit_claims"
    )

    # --- Run solver ---
    print()
    print(f"Running OI solver...")
    print(f"  Solver: {solver_model}")
    print(f"  Compiler: {compiler_model}")
    print(f"  Claim cap: {claim_cap}")
    print(f"  Max iterations: {args.max_iterations}")
    print(f"  Temperature: {args.temperature}")
    print(f"  Seed: {args.seed}, n_mc: {args.n_mc}")
    print()

    t0 = time.time()
    oi_result = run_oi_investigation(
        runner, solver_client, solver_model,
        max_iterations=args.max_iterations,
        temperature=args.temperature,
    )
    elapsed = time.time() - t0

    # --- Persist results ---
    out_dir.mkdir(parents=True, exist_ok=True)
    if out_dir != case_dir:
        shutil.copy(src_path, out_dir / "src.json")

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

    out_path = out_dir / "oi_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(oi_json, f, indent=2)

    # --- Summary ---
    print()
    print("=" * 60)
    sc = oi_result.score
    n_claims = len(score_inputs.get("claims", [])) if score_inputs else 0
    print(f"  Done in {elapsed:.0f}s")
    print(f"  Steps: {oi_result.n_steps}")
    print(f"  Submitted: {oi_result.submitted}")
    print(f"  Claims: {n_claims}")
    if sc:
        print(f"  Correctness:      {sc.correctness:.3f}")
        wcov = getattr(sc, "weighted_coverage", None) or getattr(sc, "coverage", 0.0)
        print(f"  Weighted coverage: {wcov:.3f}")
        print(f"  Total:            {sc.total:.3f}")
    else:
        print("  Score: None (no claims submitted)")
    print(f"  Output: {out_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
