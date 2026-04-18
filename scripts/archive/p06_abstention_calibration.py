#!/usr/bin/env python3
"""P06 #37 — Abstention calibration for the SQ compiler.

Runs compile_sq_to_specs on a curated set of text_gloss entries (Set A:
should_not_abstain, Set B: should_abstain) and measures false-abstention
and false-non-abstention rates against the compiler's abstention contract.

Usage:
    python scripts/p06_abstention_calibration.py
    python scripts/p06_abstention_calibration.py --repeats 3
    python scripts/p06_abstention_calibration.py --dry-run

Gates (configurable via --gate-fa and --gate-fna):
    false_abstention_rate  < 15%   (Set A items that wrongly abstained)
    false_non_abstention_rate < 10% (Set B items that wrongly compiled)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Ensure repo root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from sreg.models.open_investigation import SQTier
from sreg.tools.oi_compiler import VariableAnchors, WorldSummary
from sreg.tools.oi_sq_compiler import compile_sq_to_specs

# ---------------------------------------------------------------------------
# Calibration world — agriculture domain, 8 observable variables
# ---------------------------------------------------------------------------
# The compiler only sees variable names + statistical anchors (via
# WorldSummary), never the DAG. This world provides realistic anchors
# for the calibration set entries.

_CALIBRATION_VARIABLES = {
    "rainfall": VariableAnchors(
        name="rainfall", mean=800.0, std=200.0,
        p10=520.0, p25=650.0, p50=790.0, p75=940.0, p90=1080.0,
        is_observable=True,
    ),
    "temperature": VariableAnchors(
        name="temperature", mean=22.0, std=5.0,
        p10=15.0, p25=18.5, p50=22.0, p75=25.5, p90=29.0,
        is_observable=True,
    ),
    "soil_nitrogen": VariableAnchors(
        name="soil_nitrogen", mean=45.0, std=12.0,
        p10=30.0, p25=37.0, p50=45.0, p75=53.0, p90=60.0,
        is_observable=True,
    ),
    "fertilizer_dose": VariableAnchors(
        name="fertilizer_dose", mean=1.5, std=0.8,
        p10=0.3, p25=0.8, p50=1.5, p75=2.2, p90=2.7,
        is_observable=True,
    ),
    "irrigation": VariableAnchors(
        name="irrigation", mean=1.5, std=0.7,
        p10=0.5, p25=1.0, p50=1.5, p75=2.0, p90=2.5,
        is_observable=True,
    ),
    "pest_damage": VariableAnchors(
        name="pest_damage", mean=12.0, std=8.0,
        p10=2.0, p25=5.0, p50=10.0, p75=17.0, p90=24.0,
        is_observable=True,
    ),
    "labor_hours": VariableAnchors(
        name="labor_hours", mean=40.0, std=10.0,
        p10=26.0, p25=33.0, p50=40.0, p75=47.0, p90=54.0,
        is_observable=True,
    ),
    "crop_yield": VariableAnchors(
        name="crop_yield", mean=75.0, std=20.0,
        p10=48.0, p25=61.0, p50=74.0, p75=88.0, p90=102.0,
        is_observable=True,
    ),
}

_CALIBRATION_SUMMARY = WorldSummary(
    world_id="calibration_agriculture",
    target="crop_yield",
    variables=_CALIBRATION_VARIABLES,
    observable_names=sorted(_CALIBRATION_VARIABLES.keys()),
)


# ---------------------------------------------------------------------------
# LLM call factory (same pattern as p06_recompile_only.py)
# ---------------------------------------------------------------------------

def build_text_llm(client, model: str):
    """Build a (system, user) -> str callable using Responses API."""

    def llm_call(system: str, user: str) -> str:
        resp = client.responses.create(
            model=model, instructions=system, input=user,
        )
        parts: list[str] = []
        for item in resp.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        parts.append(part.text)
        return "".join(parts)

    return llm_call


# ---------------------------------------------------------------------------
# Run one calibration entry
# ---------------------------------------------------------------------------

def run_entry(entry: dict, llm_call, summary: WorldSummary) -> dict:
    """Run compile_sq_to_specs on a single calibration entry."""
    entry_id = entry["id"]
    text_gloss = entry["text_gloss"]
    expected = entry["expected"]

    t0 = time.time()
    result = compile_sq_to_specs(
        sq_id=f"cal_{entry_id}",
        text_gloss=text_gloss,
        focus_variables=(),
        tier=SQTier.HIGH,
        summary=summary,
        llm_call=llm_call,
    )
    elapsed = time.time() - t0

    # Classify outcome
    if result.abstained:
        actual = "abstain"
    elif result.sq is not None:
        actual = "compile"
    else:
        actual = "error"

    correct = actual == expected
    n_specs = len(result.sq.verification_specs) if result.sq else 0

    return {
        "id": entry_id,
        "text_gloss": text_gloss,
        "expected": expected,
        "actual": actual,
        "correct": correct,
        "category": entry.get("category", ""),
        "difficulty": entry.get("difficulty", ""),
        "n_specs": n_specs,
        "errors": result.errors,
        "abstain_reason": result.abstain_reason,
        "raw_response": result.raw_response,
        "elapsed_s": round(elapsed, 2),
    }


# ---------------------------------------------------------------------------
# Aggregation and reporting
# ---------------------------------------------------------------------------

def aggregate(results: list[dict], gate_fa: float, gate_fna: float) -> dict:
    """Build confusion matrix and metrics from calibration results."""
    set_a = [r for r in results if r["expected"] == "compile"]
    set_b = [r for r in results if r["expected"] == "abstain"]

    # Confusion matrix counts
    true_compile = sum(1 for r in set_a if r["actual"] == "compile")
    false_abstain = sum(1 for r in set_a if r["actual"] == "abstain")
    false_error_a = sum(1 for r in set_a if r["actual"] == "error")

    true_abstain = sum(1 for r in set_b if r["actual"] == "abstain")
    false_compile = sum(1 for r in set_b if r["actual"] == "compile")
    false_error_b = sum(1 for r in set_b if r["actual"] == "error")

    n_a = len(set_a)
    n_b = len(set_b)

    fa_rate = false_abstain / n_a if n_a else 0.0
    fna_rate = false_compile / n_b if n_b else 0.0

    # Stratify by difficulty
    by_difficulty = {}
    for diff in ("easy", "medium", "hard"):
        d_a = [r for r in set_a if r["difficulty"] == diff]
        d_b = [r for r in set_b if r["difficulty"] == diff]
        by_difficulty[diff] = {
            "set_a_total": len(d_a),
            "set_a_correct": sum(1 for r in d_a if r["correct"]),
            "set_b_total": len(d_b),
            "set_b_correct": sum(1 for r in d_b if r["correct"]),
        }

    # Stratify by category
    by_category = {}
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in by_category:
            by_category[cat] = {"total": 0, "correct": 0, "wrong": []}
        by_category[cat]["total"] += 1
        if r["correct"]:
            by_category[cat]["correct"] += 1
        else:
            by_category[cat]["wrong"].append(r["id"])

    return {
        "counts": {
            "set_a_total": n_a,
            "true_compile": true_compile,
            "false_abstain": false_abstain,
            "false_error_a": false_error_a,
            "set_b_total": n_b,
            "true_abstain": true_abstain,
            "false_compile": false_compile,
            "false_error_b": false_error_b,
        },
        "rates": {
            "false_abstention_rate": round(fa_rate, 4),
            "false_non_abstention_rate": round(fna_rate, 4),
            "set_a_accuracy": round(true_compile / n_a, 4) if n_a else 0.0,
            "set_b_accuracy": round(true_abstain / n_b, 4) if n_b else 0.0,
        },
        "gates": {
            "false_abstention_gate": gate_fa,
            "false_abstention_pass": fa_rate < gate_fa,
            "false_non_abstention_gate": gate_fna,
            "false_non_abstention_pass": fna_rate < gate_fna,
            "all_pass": fa_rate < gate_fa and fna_rate < gate_fna,
        },
        "by_difficulty": by_difficulty,
        "by_category": by_category,
    }


def print_report(agg: dict, results: list[dict]):
    """Print a human-readable calibration report."""
    c = agg["counts"]
    r = agg["rates"]
    g = agg["gates"]

    print()
    print("=" * 72)
    print("  P06 #37 -- ABSTENTION CALIBRATION REPORT")
    print("=" * 72)
    print()

    # Confusion matrix
    print("  CONFUSION MATRIX")
    print("  " + "-" * 50)
    print(f"  Set A (should_not_abstain):  {c['set_a_total']} entries")
    print(f"    true_compile:   {c['true_compile']}")
    print(f"    false_abstain:  {c['false_abstain']}")
    print(f"    error:          {c['false_error_a']}")
    print()
    print(f"  Set B (should_abstain):      {c['set_b_total']} entries")
    print(f"    true_abstain:   {c['true_abstain']}")
    print(f"    false_compile:  {c['false_compile']}")
    print(f"    error:          {c['false_error_b']}")
    print()

    # Rates
    print("  RATES")
    print("  " + "-" * 50)
    print(f"  false_abstention_rate:       {r['false_abstention_rate']:.1%}"
          f"  (gate < {g['false_abstention_gate']:.0%})"
          f"  {'PASS' if g['false_abstention_pass'] else 'FAIL'}")
    print(f"  false_non_abstention_rate:   {r['false_non_abstention_rate']:.1%}"
          f"  (gate < {g['false_non_abstention_gate']:.0%})"
          f"  {'PASS' if g['false_non_abstention_pass'] else 'FAIL'}")
    print(f"  set_a_accuracy:              {r['set_a_accuracy']:.1%}")
    print(f"  set_b_accuracy:              {r['set_b_accuracy']:.1%}")
    print()

    # By difficulty
    print("  BY DIFFICULTY")
    print("  " + "-" * 50)
    for diff in ("easy", "medium", "hard"):
        d = agg["by_difficulty"].get(diff, {})
        a_ok = f"{d.get('set_a_correct', 0)}/{d.get('set_a_total', 0)}"
        b_ok = f"{d.get('set_b_correct', 0)}/{d.get('set_b_total', 0)}"
        print(f"  {diff:8s}  Set A: {a_ok:6s}  Set B: {b_ok:6s}")
    print()

    # Wrong entries detail
    wrong = [r for r in results if not r["correct"]]
    if wrong:
        print("  WRONG ENTRIES")
        print("  " + "-" * 50)
        for w in wrong:
            tag = "FALSE_ABSTAIN" if w["expected"] == "compile" else "FALSE_COMPILE"
            print(f"  [{w['id']}] {tag}")
            # Truncate long glosses for display
            gloss = w["text_gloss"]
            if len(gloss) > 70:
                gloss = gloss[:67] + "..."
            print(f"    gloss: {gloss}")
            if w["actual"] == "error":
                print(f"    errors: {w['errors'][:2]}")
            print()
    else:
        print("  All entries classified correctly.")
        print()

    # Gate summary
    status = "PASS" if g["all_pass"] else "FAIL"
    print(f"  OVERALL GATE: {status}")
    print("=" * 72)
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="P06 #37: Abstention calibration for SQ compiler"
    )
    parser.add_argument(
        "--calibration-set",
        default=str(Path(__file__).parent / "calibration" / "abstention_calibration_set.json"),
        help="Path to calibration JSON",
    )
    parser.add_argument("--compiler-model", default=None, help="Override LLM model")
    parser.add_argument("--gate-fa", type=float, default=0.15,
                        help="False-abstention rate gate (default 0.15)")
    parser.add_argument("--gate-fna", type=float, default=0.10,
                        help="False-non-abstention rate gate (default 0.10)")
    parser.add_argument("--repeats", type=int, default=1,
                        help="Number of repeats per entry (default 1)")
    parser.add_argument("--out-dir", default=None,
                        help="Output directory for results JSON")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print entries without calling LLM")
    args = parser.parse_args()

    # Load calibration set
    cal_path = Path(args.calibration_set)
    if not cal_path.exists():
        print(f"ERROR: calibration set not found: {cal_path}")
        sys.exit(1)

    with open(cal_path, "r", encoding="utf-8") as f:
        cal_data = json.load(f)
    entries = cal_data["entries"]

    set_a = [e for e in entries if e["expected"] == "compile"]
    set_b = [e for e in entries if e["expected"] == "abstain"]

    print(f"Loaded {len(entries)} entries: "
          f"{len(set_a)} should_not_abstain (A), "
          f"{len(set_b)} should_abstain (B)")

    if args.dry_run:
        print("\n-- DRY RUN: listing entries --\n")
        for e in entries:
            tag = "A" if e["expected"] == "compile" else "B"
            print(f"  [{e['id']}] ({tag}, {e['difficulty']}) {e['text_gloss'][:72]}")
        print(f"\nTotal: {len(entries)} entries. Use without --dry-run to run LLM.")
        return

    # Setup LLM
    base_url = os.environ.get("AZURE_FOUNDRY_BASE_URL", "")
    api_key = os.environ.get("AZURE_INFERENCE_CREDENTIAL", "")
    if not base_url or not api_key:
        print("ERROR: Azure env vars not set. Check .env file.")
        sys.exit(1)

    compiler_model = args.compiler_model or os.environ.get("AZURE_MODEL", "gpt-5.4")

    from openai import OpenAI
    client = OpenAI(base_url=base_url, api_key=api_key)
    llm_call = build_text_llm(client, compiler_model)

    # Output dir
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        out_dir = Path(__file__).parent.parent / "results" / "p06_abstention_calibration"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"compiler_model: {compiler_model}")
    print(f"repeats:        {args.repeats}")
    print(f"out_dir:        {out_dir}")
    print()

    # Run calibration
    all_results = []
    for rep in range(args.repeats):
        if args.repeats > 1:
            print(f"--- Repeat {rep + 1}/{args.repeats} ---")

        rep_results = []
        for i, entry in enumerate(entries):
            tag = "A" if entry["expected"] == "compile" else "B"
            print(f"  [{entry['id']}] ({tag}) {entry['text_gloss'][:55]}...",
                  end="", flush=True)
            result = run_entry(entry, llm_call, _CALIBRATION_SUMMARY)
            status = "OK" if result["correct"] else "WRONG"
            print(f"  -> {result['actual']:8s} {status}"
                  f"  ({result['elapsed_s']:.1f}s, {result['n_specs']} specs)")
            rep_results.append(result)

        all_results.append(rep_results)
        print()

    # Use first repeat for primary report (canonical)
    primary = all_results[0]
    agg = aggregate(primary, args.gate_fa, args.gate_fna)
    print_report(agg, primary)

    # Persist results
    out_data = {
        "calibration_set": str(cal_path),
        "compiler_model": compiler_model,
        "repeats": args.repeats,
        "gates": {"fa": args.gate_fa, "fna": args.gate_fna},
        "aggregate": agg,
        "entries": primary,
    }

    # Add repeat aggregates if > 1
    if args.repeats > 1:
        rep_aggs = []
        for rep_results in all_results:
            rep_aggs.append(aggregate(rep_results, args.gate_fa, args.gate_fna))
        out_data["repeat_aggregates"] = rep_aggs

        # Variance summary
        fa_rates = [a["rates"]["false_abstention_rate"] for a in rep_aggs]
        fna_rates = [a["rates"]["false_non_abstention_rate"] for a in rep_aggs]
        import statistics
        out_data["variance_summary"] = {
            "fa_rate_mean": round(statistics.mean(fa_rates), 4),
            "fa_rate_stdev": round(statistics.stdev(fa_rates), 4) if len(fa_rates) > 1 else 0,
            "fna_rate_mean": round(statistics.mean(fna_rates), 4),
            "fna_rate_stdev": round(statistics.stdev(fna_rates), 4) if len(fna_rates) > 1 else 0,
        }

    results_path = out_dir / "_calibration_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2, ensure_ascii=True, default=str)
    print(f"Results saved to: {results_path}")


if __name__ == "__main__":
    main()
