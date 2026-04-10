#!/usr/bin/env python
"""Diagnose spec-level dispersion within compiled claims.

Hypothesis being investigated:
    The canonical v2 scorer computes claim_truth = n_hold / n_total over
    ALL specs of a claim, treating every spec as equally important. Pre-survey
    of p05_canonical_batch shows that 47/50 claims are single-unit (the
    grammar_direct backend collapses N sub-assertions into 1 unit with N
    specs), so unit-level dilution does NOT apply. The real question is
    whether spec-level aggregation within a single unit is destroying
    signal — i.e., whether claims with multiple specs frequently have
    n_hold>0 but a low hold_rate.

What this script does (read-only, no LLM):
    1. Re-load each frozen experiment via rescore.load_frozen
    2. For each claim in score_inputs_v2.compiled_claims:
       a. Re-verify each spec individually against the SCM
       b. Compute n_specs, n_hold, hold_rate
       c. Compute any_hold_gap = 1[n_hold>0] - hold_rate (DIAGNOSTIC ONLY)
       d. Read relevance_max from score_inputs_v2.relevance_results
    3. Aggregate batch-level: backend split, n_specs distribution,
       any_hold_gap distribution, top claims, salvageable count
    4. Spotlight 5-10 top claims with brief spec inspection

What this script does NOT do:
    - Propose a new scoring formula. any_hold_gap is a diagnostic ablation,
      not a scoring candidate. Choosing a fix (spec-level salience vs roles
      per spec vs other) requires reading oi_extraction.py first to
      understand the grammar_direct contract.
    - Refactor the scorer. Step 2 (unit-level scoring) remains
      DEPRIORITIZED for the current batch but not necessarily discarded
      for future workloads with different multi-unit distributions.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# Make sreg importable + load .env
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

# Reuse rescore infrastructure (same dir)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rescore import load_frozen, reconstruct_world  # noqa: E402

from sreg.models.open_investigation import AtomicSpec  # noqa: E402
from sreg.solver.scm_solver import SCMSolver  # noqa: E402
from sreg.tools.oi_verifier import verify_atom  # noqa: E402


# ---------------------------------------------------------------------------
# Per-claim analysis
# ---------------------------------------------------------------------------

def analyze_claim(co: dict, world, solver: SCMSolver, n_mc: int, seed: int) -> dict:
    """Re-verify each spec individually for one compiled claim."""
    claim_id = co["claim_id"]
    status = co["status"]
    units = co.get("units", [])

    backends = sorted({u["backend"] for u in units})
    backend = backends[0] if len(backends) == 1 else ("+".join(backends) if backends else "n/a")

    spec_results: list[dict] = []
    for u in units:
        for spec_dict in u.get("specs", []):
            try:
                spec = AtomicSpec.model_validate(spec_dict)
                v = verify_atom(spec, world, solver, n_mc, seed)
                spec_results.append({
                    "spec_id": spec.spec_id,
                    "holds": bool(v.solver_assertion_holds),
                    "error": None,
                })
            except Exception as e:
                spec_results.append({
                    "spec_id": spec_dict.get("spec_id", "?"),
                    "holds": False,
                    "error": str(e),
                })

    n_specs = len(spec_results)
    n_hold = sum(1 for s in spec_results if s["holds"])
    hold_rate = n_hold / n_specs if n_specs > 0 else 0.0
    any_hold = n_hold > 0
    any_hold_gap = (1.0 if any_hold else 0.0) - hold_rate

    return {
        "claim_id": claim_id,
        "status": status,
        "backend": backend,
        "n_units": len(units),
        "n_specs": n_specs,
        "n_hold": n_hold,
        "hold_rate": round(hold_rate, 4),
        "any_hold": any_hold,
        "any_hold_gap": round(any_hold_gap, 4),
        "specs": spec_results,
    }


def relevance_max_for_claim(claim_id: str, relevance_results: list) -> float:
    rels = [r["relevance"] for r in relevance_results if r["claim_id"] == claim_id]
    return max(rels) if rels else 0.0


def analyze_experiment(exp_dir: Path) -> dict:
    """Analyze all claims in one experiment."""
    frozen = load_frozen(exp_dir)
    src, result = frozen["src"], frozen["result"]
    si = result.get("score_inputs_v2", {})

    if not si.get("compiled_claims"):
        return {"experiment": exp_dir.name, "error": "no compiled_claims"}

    config = si.get("runner_config", {"seed": 42, "n_mc": 20_000})
    n_mc = int(config.get("n_mc", 20_000))
    seed = int(config.get("seed", 42))

    world = reconstruct_world(src)
    solver = SCMSolver(world, n_mc=n_mc)

    relevance_results = si.get("relevance_results", [])
    persisted_truths = si.get("claim_truths", {})

    claim_analyses = []
    for co in si["compiled_claims"]:
        a = analyze_claim(co, world, solver, n_mc, seed)
        a["relevance_max"] = round(relevance_max_for_claim(a["claim_id"], relevance_results), 4)
        a["claim_truth_persisted"] = round(persisted_truths.get(a["claim_id"], 0.0), 4)
        # Sanity check: persisted ≈ hold_rate (modulo evidence_basis penalty)
        a["persisted_minus_holdrate"] = round(a["claim_truth_persisted"] - a["hold_rate"], 4)
        claim_analyses.append(a)

    return {
        "experiment": exp_dir.name,
        "n_mc": n_mc,
        "seed": seed,
        "claims": claim_analyses,
    }


# ---------------------------------------------------------------------------
# Batch summary
# ---------------------------------------------------------------------------

def summarize_batch(experiments: list[dict]) -> dict:
    all_claims = []
    for exp in experiments:
        if "error" in exp:
            continue
        for c in exp["claims"]:
            all_claims.append({"experiment": exp["experiment"], **c})

    n_total = len(all_claims)
    n_abstention = sum(1 for c in all_claims if c["status"] == "abstention")
    n_compiled = n_total - n_abstention
    n_multi_unit = sum(1 for c in all_claims if c["n_units"] >= 2)
    n_single_unit = n_compiled - n_multi_unit

    backend_counts = Counter(c["backend"] for c in all_claims if c["status"] != "abstention")
    n_specs_dist = Counter(c["n_specs"] for c in all_claims if c["status"] != "abstention")

    compiled = [c for c in all_claims if c["status"] != "abstention" and c["n_specs"] > 0]

    # any_hold_gap buckets
    gap_buckets: dict[str, int] = {
        "0.00 (none)": 0,
        "(0, 0.25)": 0,
        "[0.25, 0.5)": 0,
        "[0.5, 0.75)": 0,
        "[0.75, 1.00]": 0,
    }
    for c in compiled:
        g = c["any_hold_gap"]
        if g == 0.0:
            gap_buckets["0.00 (none)"] += 1
        elif g < 0.25:
            gap_buckets["(0, 0.25)"] += 1
        elif g < 0.5:
            gap_buckets["[0.25, 0.5)"] += 1
        elif g < 0.75:
            gap_buckets["[0.5, 0.75)"] += 1
        else:
            gap_buckets["[0.75, 1.00]"] += 1

    # Salvageable: n_hold > 0 AND hold_rate < 0.5
    salvageable = [c for c in compiled if c["n_hold"] > 0 and c["hold_rate"] < 0.5]
    salvageable_relevant = [c for c in salvageable if c["relevance_max"] >= 0.5]

    # Sanity: max abs deviation between persisted truth and our hold_rate
    deltas = [abs(c["persisted_minus_holdrate"]) for c in compiled]
    max_persisted_delta = max(deltas) if deltas else 0.0
    n_persisted_mismatch = sum(1 for d in deltas if d > 0.001)

    # Top by any_hold_gap * relevance_max (DIAGNOSTIC RANKING)
    ranked = sorted(
        compiled,
        key=lambda c: c["any_hold_gap"] * c["relevance_max"],
        reverse=True,
    )

    # Mean hold_rate by backend
    mean_hold_by_backend: dict[str, float] = {}
    for b in backend_counts:
        rs = [c["hold_rate"] for c in compiled if c["backend"] == b]
        if rs:
            mean_hold_by_backend[b] = round(sum(rs) / len(rs), 4)

    # Mean n_specs by backend
    mean_n_specs_by_backend: dict[str, float] = {}
    for b in backend_counts:
        ns = [c["n_specs"] for c in compiled if c["backend"] == b]
        if ns:
            mean_n_specs_by_backend[b] = round(sum(ns) / len(ns), 2)

    return {
        "n_total_claims": n_total,
        "n_abstention": n_abstention,
        "n_multi_unit": n_multi_unit,
        "n_single_unit": n_single_unit,
        "backend_split": dict(backend_counts),
        "n_specs_distribution": dict(sorted(n_specs_dist.items())),
        "mean_hold_rate_by_backend": mean_hold_by_backend,
        "mean_n_specs_by_backend": mean_n_specs_by_backend,
        "any_hold_gap_buckets": gap_buckets,
        "n_salvageable": len(salvageable),
        "n_salvageable_relevant": len(salvageable_relevant),
        "max_persisted_delta": round(max_persisted_delta, 4),
        "n_persisted_mismatch": n_persisted_mismatch,
        "top_by_gap_times_relevance": ranked[:10],
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(experiments: list[dict], summary: dict):
    print()
    print("=" * 78)
    print("  SPEC-LEVEL DISPERSION DIAGNOSTIC")
    print("=" * 78)
    print()
    print(f"Total claims:    {summary['n_total_claims']}")
    print(f"  multi-unit:    {summary['n_multi_unit']}")
    print(f"  single-unit:   {summary['n_single_unit']}")
    print(f"  abstentions:   {summary['n_abstention']}")
    print()
    print(f"Backend split (compiled only): {summary['backend_split']}")
    print(f"Mean n_specs by backend:       {summary['mean_n_specs_by_backend']}")
    print(f"Mean hold_rate by backend:     {summary['mean_hold_rate_by_backend']}")
    print()
    print(f"n_specs distribution: {summary['n_specs_distribution']}")
    print()

    print("Sanity check (persisted claim_truth vs recomputed hold_rate):")
    print(f"  max abs delta:     {summary['max_persisted_delta']}")
    print(f"  n claims mismatch: {summary['n_persisted_mismatch']}")
    print("  (mismatches are expected if evidence_basis penalty applied)")
    print()

    print("any_hold_gap distribution (DIAGNOSTIC ABLATION ONLY, not a scoring proposal):")
    print("  Asks: 'if we said any spec holding -> claim partially true,")
    print("         how much would the truth measure increase?'")
    for bucket, count in summary["any_hold_gap_buckets"].items():
        bar = "#" * count
        print(f"  {bucket:>15} {count:>3}  {bar}")
    print()

    print("Salvageable claims (n_hold>=1 AND hold_rate<0.5):")
    print(f"  total:                    {summary['n_salvageable']}")
    print(f"  with relevance_max>=0.5:  {summary['n_salvageable_relevant']}")
    print()

    # Top table
    print("Top 10 claims by any_hold_gap * relevance_max:")
    print(
        f"  {'Experiment':<16} {'ClaimID':<32} {'Bkend':<14} "
        f"{'n':>3} {'hold':>4} {'rate':>5} {'gap':>5} {'rel':>5}"
    )
    print(f"  {'-' * 16} {'-' * 32} {'-' * 14} {'-' * 3} {'-' * 4} {'-' * 5} {'-' * 5} {'-' * 5}")
    for c in summary["top_by_gap_times_relevance"]:
        print(
            f"  {c['experiment'][:16]:<16} {c['claim_id'][:32]:<32} "
            f"{c['backend'][:14]:<14} {c['n_specs']:>3} {c['n_hold']:>4} "
            f"{c['hold_rate']:>5.2f} {c['any_hold_gap']:>5.2f} {c['relevance_max']:>5.2f}"
        )
    print()

    # Spotlight: brief spec-level inspection of the top 5
    print("Spotlight (top 5 — brief spec inspection):")
    print()
    for i, c in enumerate(summary["top_by_gap_times_relevance"][:5], 1):
        print(f"  [{i}] {c['experiment']} / {c['claim_id']}")
        print(
            f"      backend={c['backend']}  n_specs={c['n_specs']}  "
            f"n_hold={c['n_hold']}  hold_rate={c['hold_rate']:.2f}  "
            f"relevance_max={c['relevance_max']:.2f}"
        )
        for s in c["specs"]:
            mark = "[+]" if s["holds"] else "[-]"
            err = f"  ERR: {s['error']}" if s.get("error") else ""
            print(f"      {mark} {s['spec_id'][:64]}{err}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Diagnose spec-level dispersion within compiled claims (read-only)"
    )
    parser.add_argument("batch_dir", help="Batch directory (e.g., results/p05_canonical_batch)")
    parser.add_argument("--out", default=None, help="JSON output path")
    args = parser.parse_args()

    batch_dir = Path(args.batch_dir)
    if not batch_dir.is_dir():
        print(f"ERROR: not a directory: {batch_dir}")
        sys.exit(1)

    experiments: list[dict] = []
    for exp_dir in sorted(batch_dir.iterdir()):
        if not exp_dir.is_dir():
            continue
        if not (exp_dir / "oi_result.json").exists():
            continue
        print(f"Analyzing {exp_dir.name}...", end=" ", flush=True)
        try:
            r = analyze_experiment(exp_dir)
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            continue

        if "error" in r:
            print(f"SKIP ({r['error']})")
        else:
            print(f"{len(r['claims'])} claims")
        experiments.append(r)

    summary = summarize_batch(experiments)
    print_report(experiments, summary)

    out_path = Path(args.out) if args.out else batch_dir / "spec_dispersion_diagnostic.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"experiments": experiments, "summary": summary}, f, indent=2)
    print(f"JSON saved to: {out_path}")


if __name__ == "__main__":
    main()
