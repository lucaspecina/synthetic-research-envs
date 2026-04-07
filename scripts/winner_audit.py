#!/usr/bin/env python
"""Winner audit: do low-truth claims displace materially more truthful claims?

For each SQ in each experiment:
  1. Compute score = truth * relevance for every claim
  2. Sort claims by score (desc)
  3. winner = highest-scoring claim, runner_up = second
  4. displacement = winner.truth - runner_up.truth
     - displacement < 0 means: winner ganó por relevance, runner_up era más verdadero
     - threshold |displacement| >= 0.1 = "material"

Truth source: hold_rate from spec_dispersion_diagnostic.json (pre-penalty,
clean of evidence_basis adjustments). This is the same value used by
_score_with_judge minus the penalty applied later.

Read-only. No LLM. Stratifies by n_specs as bonus (Codex #2).
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_diagnostic(batch_dir: Path) -> dict[str, dict]:
    """Load spec_dispersion_diagnostic.json -> {(exp, claim_id): claim_dict}."""
    path = batch_dir / "spec_dispersion_diagnostic.json"
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    out = {}
    for exp in d["experiments"]:
        if "error" in exp:
            continue
        for c in exp["claims"]:
            out[(exp["experiment"], c["claim_id"])] = c
    return out


def audit_experiment(exp_dir: Path, claims_by_id: dict) -> dict:
    """Run winner audit for a single experiment."""
    src = json.load(open(exp_dir / "src.json", encoding="utf-8"))
    result = json.load(open(exp_dir / "oi_result.json", encoding="utf-8"))
    si = result.get("score_inputs_v2", {})
    if not si.get("relevance_results"):
        return {"experiment": exp_dir.name, "error": "no relevance_results"}

    relevance_results = si["relevance_results"]
    sqs = src.get("sub_questions_v2", [])

    # Build (claim_id, sq_id) -> relevance
    rel_map: dict[tuple[str, str], float] = {}
    for r in relevance_results:
        rel_map[(r["claim_id"], r["sq_id"])] = r["relevance"]

    # Distinct claim_ids
    claim_ids = sorted({r["claim_id"] for r in relevance_results})

    audits_per_sq = []
    for sq in sqs:
        sq_id = sq["sq_id"]

        scored = []
        for cid in claim_ids:
            cinfo = claims_by_id.get((exp_dir.name, cid))
            if not cinfo:
                continue  # abstention or missing
            truth = cinfo.get("hold_rate", 0.0)
            rel = rel_map.get((cid, sq_id), 0.0)
            scored.append({
                "claim_id": cid,
                "truth": truth,
                "relevance": rel,
                "score": truth * rel,
                "n_specs": cinfo.get("n_specs", 0),
            })

        if not scored:
            continue

        scored.sort(key=lambda x: x["score"], reverse=True)
        winner = scored[0]
        runner_up = scored[1] if len(scored) >= 2 else None

        displacement = (winner["truth"] - runner_up["truth"]) if runner_up else 0.0

        # Also: highest-truth claim (regardless of relevance)
        by_truth = sorted(scored, key=lambda x: x["truth"], reverse=True)
        most_truthful = by_truth[0]

        # Was the winner the most truthful?
        winner_is_most_truthful = winner["claim_id"] == most_truthful["claim_id"]

        audits_per_sq.append({
            "sq_id": sq_id,
            "tier": sq.get("tier"),
            "winner": winner,
            "runner_up": runner_up,
            "most_truthful": most_truthful,
            "winner_is_most_truthful": winner_is_most_truthful,
            "displacement": round(displacement, 4),
            "truth_gap_to_max": round(winner["truth"] - most_truthful["truth"], 4),
        })

    return {
        "experiment": exp_dir.name,
        "n_sqs": len(audits_per_sq),
        "audits": audits_per_sq,
    }


def stratify_by_n_specs(claims_by_id: dict) -> dict:
    """Bucket claims by n_specs and report mean hold_rate."""
    buckets = {
        "1": [],
        "2-3": [],
        "4-5": [],
        "6+": [],
    }
    for c in claims_by_id.values():
        if c.get("status") == "abstention":
            continue
        n = c.get("n_specs", 0)
        if n == 1:
            buckets["1"].append(c)
        elif n <= 3:
            buckets["2-3"].append(c)
        elif n <= 5:
            buckets["4-5"].append(c)
        else:
            buckets["6+"].append(c)

    result = {}
    for label, claims in buckets.items():
        if not claims:
            result[label] = {"n": 0, "mean_hold_rate": 0.0, "mean_n_hold": 0.0}
            continue
        mean_hr = sum(c["hold_rate"] for c in claims) / len(claims)
        mean_nh = sum(c["n_hold"] for c in claims) / len(claims)
        result[label] = {
            "n": len(claims),
            "mean_hold_rate": round(mean_hr, 4),
            "mean_n_hold": round(mean_nh, 2),
        }
    return result


def print_report(experiments: list[dict], strat: dict, claims_by_id: dict):
    print()
    print("=" * 78)
    print("  WINNER AUDIT")
    print("=" * 78)
    print()

    total_sqs = 0
    total_displaced = 0  # winner truth < most_truthful by >= 0.1
    total_winners_with_low_truth = 0  # winner.truth < 0.5
    all_audits = []

    for exp in experiments:
        if "error" in exp:
            continue
        for a in exp["audits"]:
            total_sqs += 1
            if a["truth_gap_to_max"] <= -0.1:
                total_displaced += 1
            if a["winner"]["truth"] < 0.5:
                total_winners_with_low_truth += 1
            all_audits.append({"experiment": exp["experiment"], **a})

    print(f"Total SQs analyzed: {total_sqs}")
    print(f"Winners that ARE the most truthful claim:    "
          f"{total_sqs - sum(1 for a in all_audits if not a['winner_is_most_truthful'])}")
    print(f"Winners that are NOT the most truthful:      "
          f"{sum(1 for a in all_audits if not a['winner_is_most_truthful'])}")
    print(f"Material displacement (truth_gap_to_max <= -0.1): {total_displaced}")
    print(f"Winners with truth < 0.5:                    {total_winners_with_low_truth}")
    print()

    # Stratification
    print("Stratification by n_specs (mean hold_rate per bucket):")
    print(f"  {'bucket':<6} {'n':>4} {'mean_hold_rate':>15} {'mean_n_hold':>12}")
    for label, s in strat.items():
        print(f"  {label:<6} {s['n']:>4} {s['mean_hold_rate']:>15.4f} {s['mean_n_hold']:>12.2f}")
    print()

    # Top 10 displacements
    displaced_sorted = sorted(
        [a for a in all_audits if a["truth_gap_to_max"] <= -0.05],
        key=lambda a: a["truth_gap_to_max"],
    )

    if displaced_sorted:
        print(f"Top displacements (winner truth < most_truthful by >= 0.05):")
        print(
            f"  {'Experiment':<16} {'SQ':<6} {'Winner':<6} {'w.truth':>7} {'w.rel':>6} "
            f"{'w*r':>5} | {'Best':<6} {'b.truth':>7} {'b.rel':>6} {'gap':>6}"
        )
        print(f"  {'-'*16} {'-'*6} {'-'*6} {'-'*7} {'-'*6} {'-'*5}   {'-'*6} {'-'*7} {'-'*6} {'-'*6}")
        for a in displaced_sorted[:15]:
            w = a["winner"]
            mt = a["most_truthful"]
            # Best one's relevance for the same SQ
            print(
                f"  {a['experiment'][:16]:<16} {a['sq_id'][:6]:<6} "
                f"{w['claim_id'][:6]:<6} {w['truth']:>7.3f} {w['relevance']:>6.3f} "
                f"{w['score']:>5.2f} | "
                f"{mt['claim_id'][:6]:<6} {mt['truth']:>7.3f} {mt.get('relevance', 0):>6.3f} "
                f"{a['truth_gap_to_max']:>+6.2f}"
            )
        print()
    else:
        print("No material displacements found — winners are also the most truthful.")
        print()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("batch_dir")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    batch_dir = Path(args.batch_dir)
    if not (batch_dir / "spec_dispersion_diagnostic.json").exists():
        print("ERROR: run diagnose_spec_dispersion.py first")
        sys.exit(1)

    claims_by_id = load_diagnostic(batch_dir)

    experiments = []
    for exp_dir in sorted(batch_dir.iterdir()):
        if not exp_dir.is_dir():
            continue
        if not (exp_dir / "oi_result.json").exists():
            continue
        try:
            r = audit_experiment(exp_dir, claims_by_id)
            experiments.append(r)
        except Exception as e:
            print(f"ERROR in {exp_dir.name}: {e}")
            import traceback
            traceback.print_exc()

    strat = stratify_by_n_specs(claims_by_id)
    print_report(experiments, strat, claims_by_id)

    out_path = Path(args.out) if args.out else batch_dir / "winner_audit.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"experiments": experiments, "stratification": strat}, f, indent=2)
    print(f"JSON saved to: {out_path}")


if __name__ == "__main__":
    main()
