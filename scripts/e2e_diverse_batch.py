#!/usr/bin/env python3
"""E2E Diverse Batch: run 12 diverse seeds through full OI pipeline.

Generates world via orchestrator + runs solver + scores with v2 judge.
Collects per-seed metrics and compiler backend stats (grammar-direct vs v1).

Usage:
    python scripts/e2e_diverse_batch.py --out results/e2e_batch_diverse
    python scripts/e2e_diverse_batch.py --out results/e2e_batch_diverse --seeds 3  # quick test
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# 12 diverse seeds — covering 9+ investigation types
# ---------------------------------------------------------------------------

SEEDS = [
    # (seed_file, short_name, investigation_type)
    ("microbiome_system_mapping.md", "microbiome", "system_mapping"),
    ("coral_reef_bleaching.md", "coral_bleach", "descriptive"),
    ("identifiability_pollution.md", "identifiability", "epistemological"),
    ("confounding_by_indication.md", "confounding", "confounding"),
    ("poverty_reduction_china.md", "poverty", "causal_simple"),
    ("treatment_heterogeneity.md", "heterogeneity", "heterogeneity"),
    ("chemical_formulation.md", "chemical", "optimization"),
    ("selection_bias_police.md", "selection_bias", "selection_bias"),
    ("policy_equity_tradeoff.md", "policy_equity", "policy_tradeoff"),
    ("competing_mechanisms.md", "competing_mech", "causal_mechanism"),
    ("methodology_missing_data.md", "missing_data", "epistemological_method"),
    ("vaca_muerta_predictive.md", "vaca_predict", "prediction"),
]


def run_one_seed(
    seed_file: str,
    short_name: str,
    inv_type: str,
    out_dir: str,
    seed_dir: str,
) -> dict:
    """Run one seed through generate_src.py --oi and collect results."""
    seed_path = os.path.join(seed_dir, seed_file)
    case_dir = os.path.join(out_dir, short_name)

    print(f"\n{'='*60}")
    print(f"  [{short_name}] type={inv_type}")
    print(f"  seed: {seed_file}")
    print(f"{'='*60}")

    t0 = time.time()

    try:
        # Run the full pipeline
        cmd = [
            sys.executable, "scripts/generate_src.py",
            "--seed-file", seed_path,
            "-o", case_dir,
            "--oi", "--inspect",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=900,  # 15 min max per seed
            encoding="utf-8",
            errors="replace",
        )
        elapsed = time.time() - t0

        # Parse output for score line
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        score_line = ""
        for line in stdout.split("\n"):
            if "Score:" in line:
                score_line = line.strip()

        # Try to load oi_result.json for detailed stats
        oi_json_path = os.path.join(case_dir, "oi_result.json")
        oi_data = None
        if os.path.exists(oi_json_path):
            with open(oi_json_path, "r") as f:
                oi_data = json.load(f)

        # Extract scores
        score = oi_data.get("score", {}) if oi_data else {}
        total = score.get("total", -1)
        correctness = score.get("correctness", -1)
        coverage = score.get("weighted_coverage", score.get("coverage", -1))
        submitted = oi_data.get("submitted", False) if oi_data else False
        n_steps = oi_data.get("n_steps", -1) if oi_data else -1

        # Compiler stats: count backend types from the conversation/score
        # We need to inspect CompilerOutput data — check if it's in the score
        sq_scores = score.get("sq_scores", [])

        entry = {
            "seed": seed_file,
            "name": short_name,
            "type": inv_type,
            "total": total,
            "correctness": correctness,
            "coverage": coverage,
            "submitted": submitted,
            "n_steps": n_steps,
            "elapsed": round(elapsed, 1),
            "return_code": result.returncode,
            "score_line": score_line,
            "error": "" if result.returncode == 0 else stderr[-500:] if stderr else "unknown",
        }

        status = "OK" if result.returncode == 0 and submitted else "FAIL"
        print(f"  [{status}] total={total:.3f} corr={correctness:.3f} "
              f"cov={coverage:.3f} steps={n_steps} time={elapsed:.0f}s")

        return entry

    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        print(f"  [TIMEOUT] after {elapsed:.0f}s")
        return {
            "seed": seed_file, "name": short_name, "type": inv_type,
            "total": -1, "correctness": -1, "coverage": -1,
            "submitted": False, "n_steps": -1, "elapsed": round(elapsed, 1),
            "return_code": -1, "score_line": "", "error": "TIMEOUT",
        }
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  [ERROR] {e}")
        return {
            "seed": seed_file, "name": short_name, "type": inv_type,
            "total": -1, "correctness": -1, "coverage": -1,
            "submitted": False, "n_steps": -1, "elapsed": round(elapsed, 1),
            "return_code": -1, "score_line": "", "error": str(e),
        }


def analyze_compiler_backends(out_dir: str, results: list[dict]) -> dict:
    """Analyze compiler backends from oi_result.json compiler_stats field."""
    stats = {
        "total_claims": 0,
        "grammar_direct": 0,
        "v1_fallback": 0,
        "abstention": 0,
        "total_specs": 0,
        "per_seed": {},
    }

    for r in results:
        case_dir = os.path.join(out_dir, r["name"])
        oi_path = os.path.join(case_dir, "oi_result.json")
        if not os.path.exists(oi_path):
            continue

        with open(oi_path, "r") as f:
            oi = json.load(f)

        cs = oi.get("compiler_stats", {})
        if cs:
            stats["total_claims"] += cs.get("total_claims", 0)
            stats["grammar_direct"] += cs.get("grammar_direct", 0)
            stats["v1_fallback"] += cs.get("v1_fallback", 0)
            stats["abstention"] += cs.get("abstention", 0)
            stats["total_specs"] += cs.get("total_specs", 0)
            stats["per_seed"][r["name"]] = cs
        else:
            # Fallback: count from solver_tool_calls
            n_claims = 0
            for tc in oi.get("solver_tool_calls", []):
                if tc.get("name") == "submit_claims":
                    args = tc.get("args", {})
                    n_claims = len(args.get("claims", []))
            stats["total_claims"] += n_claims
            stats["per_seed"][r["name"]] = {"n_claims": n_claims}

    return stats


def print_summary(results: list[dict], compiler_stats: dict):
    """Print final summary table."""
    print("\n")
    print("=" * 80)
    print("  E2E DIVERSE BATCH — SUMMARY")
    print("=" * 80)

    # Score table
    print(f"\n{'Seed':<20} {'Type':<22} {'Total':>6} {'Corr':>6} {'Cov':>6} "
          f"{'Steps':>5} {'Time':>5} {'Status':<6}")
    print("-" * 80)

    ok = 0
    fail = 0
    totals = []
    corrs = []
    covs = []

    for r in results:
        status = "OK" if r["return_code"] == 0 and r["submitted"] else "FAIL"
        if status == "OK":
            ok += 1
            if r["total"] >= 0:
                totals.append(r["total"])
                corrs.append(r["correctness"])
                covs.append(r["coverage"])
        else:
            fail += 1

        t = f"{r['total']:.3f}" if r['total'] >= 0 else "---"
        c = f"{r['correctness']:.3f}" if r['correctness'] >= 0 else "---"
        v = f"{r['coverage']:.3f}" if r['coverage'] >= 0 else "---"
        print(f"{r['name']:<20} {r['type']:<22} {t:>6} {c:>6} {v:>6} "
              f"{r['n_steps']:>5} {r['elapsed']:>5.0f}s {status:<6}")

    print("-" * 80)
    if totals:
        avg_t = sum(totals) / len(totals)
        avg_c = sum(corrs) / len(corrs)
        avg_v = sum(covs) / len(covs)
        print(f"{'AVERAGE':<20} {'(N=' + str(len(totals)) + ')':<22} "
              f"{avg_t:>6.3f} {avg_c:>6.3f} {avg_v:>6.3f}")
    print(f"\nSuccess: {ok}/{ok+fail} | Fail: {fail}/{ok+fail}")

    # Compiler stats
    tc = compiler_stats["total_claims"]
    gd = compiler_stats["grammar_direct"]
    v1 = compiler_stats["v1_fallback"]
    ab = compiler_stats["abstention"]
    ts = compiler_stats.get("total_specs", 0)

    print(f"\n--- Compiler Backend Stats ---")
    print(f"Total claims: {tc}")
    if tc > 0:
        print(f"  Grammar-direct (A23): {gd}/{tc} ({100*gd/tc:.0f}%)")
        print(f"  V1 fallback:          {v1}/{tc} ({100*v1/tc:.0f}%)")
        print(f"  Abstention:           {ab}/{tc} ({100*ab/tc:.0f}%)")
        print(f"  Total specs produced:  {ts} ({ts/tc:.1f} per claim)")

    # Per-seed compiler breakdown
    print(f"\n{'Seed':<20} {'Claims':>6} {'Direct':>6} {'V1':>6} {'Abst':>6} {'Specs':>6}")
    print("-" * 60)
    for r in results:
        ps = compiler_stats.get("per_seed", {}).get(r["name"], {})
        nc = ps.get("total_claims", ps.get("n_claims", 0))
        nd = ps.get("grammar_direct", 0)
        nv = ps.get("v1_fallback", 0)
        na = ps.get("abstention", 0)
        ns = ps.get("total_specs", 0)
        print(f"{r['name']:<20} {nc:>6} {nd:>6} {nv:>6} {na:>6} {ns:>6}")

    total_time = sum(r["elapsed"] for r in results)
    print(f"\nTotal batch time: {total_time:.0f}s ({total_time/60:.1f}min)")


def main():
    parser = argparse.ArgumentParser(description="E2E Diverse Batch")
    parser.add_argument("--out", type=str, required=True, help="Output directory")
    parser.add_argument(
        "--seeds", type=int, default=len(SEEDS),
        help=f"Number of seeds to run (default: all {len(SEEDS)})",
    )
    args = parser.parse_args()

    seeds_dir = os.path.join(os.path.dirname(__file__), "..", "seeds")
    os.makedirs(args.out, exist_ok=True)

    selected = SEEDS[:args.seeds]
    print(f"E2E Diverse Batch: {len(selected)} seeds")
    print(f"Output: {args.out}")
    print(f"Started: {datetime.now().isoformat()}")

    results = []
    for seed_file, short_name, inv_type in selected:
        entry = run_one_seed(seed_file, short_name, inv_type, args.out, seeds_dir)
        results.append(entry)

        # Save intermediate results after each seed
        summary_path = os.path.join(args.out, "batch_results.json")
        with open(summary_path, "w") as f:
            json.dump(results, f, indent=2)

    # Analyze compiler backends
    compiler_stats = analyze_compiler_backends(args.out, results)

    # Print summary
    print_summary(results, compiler_stats)

    # Save final summary
    final = {
        "timestamp": datetime.now().isoformat(),
        "n_seeds": len(results),
        "results": results,
        "compiler_stats": compiler_stats,
    }
    final_path = os.path.join(args.out, "batch_summary.json")
    with open(final_path, "w") as f:
        json.dump(final, f, indent=2)
    print(f"\nResults saved to: {final_path}")


if __name__ == "__main__":
    main()
