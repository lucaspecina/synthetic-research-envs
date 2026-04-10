#!/usr/bin/env python
"""P06 smoke gate: did the atomic-claims prompt change behavior as expected?

Computes Codex's gate (4 checks) plus expanded metrics on a smoke set.
Compares against a frozen baseline directory case-by-case (by case name).

Gate (PASS/FAIL):
  1. n_claims/episode             — should be HIGHER than baseline
  2. mean n_specs/claim           — should be LOWER than baseline
  3. fraction n_specs=1           — should be HIGHER than baseline
  4. error rate                   — should NOT explode (< 5% over baseline)

NOT a measurement of score improvement — that's Phase C (paired comparison).
This script answers: "is the prompt actually atomizing claims?"

Read-only. No LLM. Loads frozen oi_result.json + src.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_case(case_dir: Path) -> dict:
    """Load and digest one experiment directory."""
    src = json.load(open(case_dir / "src.json", encoding="utf-8"))
    res = json.load(open(case_dir / "oi_result.json", encoding="utf-8"))
    si = res.get("score_inputs_v2", {})
    sc = res.get("score", {})

    claims_raw = si.get("claims", [])
    compiled = si.get("compiled_claims", [])
    truths = si.get("claim_truths", {})

    n_claims = len(claims_raw)
    n_compiled = sum(1 for c in compiled if c.get("status") == "compiled")
    n_partial = sum(1 for c in compiled if c.get("status") == "partial")
    n_abstention = sum(1 for c in compiled if c.get("status") == "abstention")
    n_error = n_claims - n_compiled - n_partial - n_abstention

    # n_specs per claim (sum across units)
    n_specs_per_claim: list[int] = []
    for c in compiled:
        if c.get("status") == "abstention":
            continue
        n = sum(len(u.get("specs", [])) for u in c.get("units", []))
        n_specs_per_claim.append(n)

    n_with_one_spec = sum(1 for n in n_specs_per_claim if n == 1)
    n_with_zero_specs = sum(1 for n in n_specs_per_claim if n == 0)

    mean_n_specs = (
        sum(n_specs_per_claim) / len(n_specs_per_claim)
        if n_specs_per_claim else 0.0
    )
    frac_atomic = (
        n_with_one_spec / len(n_specs_per_claim)
        if n_specs_per_claim else 0.0
    )

    # Claim text length
    claim_lens = [len(c.get("claim_text", "")) for c in claims_raw]
    mean_claim_len = sum(claim_lens) / len(claim_lens) if claim_lens else 0.0
    min_claim_len = min(claim_lens) if claim_lens else 0
    max_claim_len = max(claim_lens) if claim_lens else 0

    # Confidence
    confidences = [c.get("confidence", 0.0) for c in claims_raw]
    mean_conf = sum(confidences) / len(confidences) if confidences else 0.0

    # Hold rates by bucket
    hold_rates = list(truths.values())
    mean_hold = sum(hold_rates) / len(hold_rates) if hold_rates else 0.0

    # World fingerprint (drift detection for paired comparison)
    world = src.get("world", {})
    problem = src.get("problem", {})
    src_str = json.dumps(src, sort_keys=True)
    world_hash = hashlib.sha1(src_str.encode("utf-8")).hexdigest()[:12]

    return {
        "case": case_dir.name,
        # gate metrics
        "n_claims": n_claims,
        "mean_n_specs": round(mean_n_specs, 3),
        "frac_atomic": round(frac_atomic, 3),
        "n_error": n_error,
        "error_rate": round(n_error / max(n_claims, 1), 3),
        # expanded
        "n_compiled": n_compiled,
        "n_partial": n_partial,
        "n_abstention": n_abstention,
        "n_zero_specs": n_with_zero_specs,
        "compilation_success": round(
            (n_compiled + n_partial) / max(n_claims, 1), 3
        ),
        "mean_claim_len": round(mean_claim_len, 1),
        "min_claim_len": min_claim_len,
        "max_claim_len": max_claim_len,
        "mean_confidence": round(mean_conf, 3),
        "mean_hold_rate": round(mean_hold, 3),
        # score
        "correctness": round(sc.get("correctness", 0.0), 3),
        "weighted_coverage": round(sc.get("weighted_coverage", 0.0), 3),
        "total": round(sc.get("total", 0.0), 3),
        # fingerprint
        "n_vars": len(world.get("variables", [])),
        "brief_len": len(problem.get("research_question", "")),
        "n_sqs": len(src.get("sub_questions_v2", [])),
        "src_hash": world_hash,
    }


def aggregate(cases: list[dict]) -> dict:
    if not cases:
        return {}
    keys = [
        "n_claims", "mean_n_specs", "frac_atomic", "error_rate",
        "compilation_success", "mean_claim_len", "mean_confidence",
        "mean_hold_rate", "correctness", "weighted_coverage", "total",
    ]
    return {k: round(sum(c[k] for c in cases) / len(cases), 3) for k in keys}


def print_table(rows: list[dict], cols: list[str]):
    widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    header = "  ".join(c.ljust(widths[c]) for c in cols)
    print("  " + header)
    print("  " + "  ".join("-" * widths[c] for c in cols))
    for r in rows:
        print("  " + "  ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", required=True, help="Baseline batch dir (e.g. results/p05_canonical_batch)")
    p.add_argument("--experimental", required=True, help="Experimental batch dir (e.g. results/p06_smoke)")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    baseline_dir = Path(args.baseline)
    exp_dir = Path(args.experimental)

    exp_cases: list[dict] = []
    for case_dir in sorted(exp_dir.iterdir()):
        if not case_dir.is_dir() or not (case_dir / "oi_result.json").exists():
            continue
        try:
            exp_cases.append(load_case(case_dir))
        except Exception as e:
            print(f"ERROR loading {case_dir.name}: {e}", file=sys.stderr)

    base_cases: list[dict] = []
    for c in exp_cases:
        bc_dir = baseline_dir / c["case"]
        if (bc_dir / "oi_result.json").exists():
            base_cases.append(load_case(bc_dir))

    print()
    print("=" * 90)
    print("  P06 SMOKE GATE")
    print("=" * 90)
    print()

    cols_main = [
        "case", "n_claims", "mean_n_specs", "frac_atomic", "error_rate",
        "correctness", "weighted_coverage", "total",
    ]
    print("BASELINE:")
    print_table(base_cases, cols_main)
    print()
    print("EXPERIMENTAL:")
    print_table(exp_cases, cols_main)
    print()

    cols_health = [
        "case", "n_compiled", "n_partial", "n_abstention", "n_zero_specs",
        "compilation_success", "mean_claim_len", "mean_confidence",
    ]
    print("Compilation health (experimental):")
    print_table(exp_cases, cols_health)
    print()

    cols_drift = ["case", "n_vars", "n_sqs", "brief_len", "src_hash"]
    print("World fingerprint (drift detection):")
    print("BASELINE:")
    print_table(base_cases, cols_drift)
    print("EXPERIMENTAL:")
    print_table(exp_cases, cols_drift)
    print()

    base_agg = aggregate(base_cases)
    exp_agg = aggregate(exp_cases)
    print("Aggregated means:")
    print(f"  {'metric':<22} {'baseline':>10} {'experimental':>14} {'delta':>10}")
    print(f"  {'-'*22} {'-'*10} {'-'*14} {'-'*10}")
    for k in [
        "n_claims", "mean_n_specs", "frac_atomic", "error_rate",
        "compilation_success", "mean_confidence", "mean_hold_rate",
        "correctness", "weighted_coverage", "total",
    ]:
        b = base_agg.get(k, 0.0)
        e = exp_agg.get(k, 0.0)
        d = e - b
        sign = "+" if d > 0 else ""
        print(f"  {k:<22} {b:>10.3f} {e:>14.3f} {sign}{d:>9.3f}")
    print()

    # Codex gate
    print("=" * 90)
    print("  CODEX GATE (4 checks):")
    print("=" * 90)
    checks = [
        ("n_claims should be HIGHER",
         exp_agg.get("n_claims", 0) > base_agg.get("n_claims", 0)),
        ("mean_n_specs should be LOWER",
         exp_agg.get("mean_n_specs", 99) < base_agg.get("mean_n_specs", 0)),
        ("frac_atomic should be HIGHER",
         exp_agg.get("frac_atomic", 0) > base_agg.get("frac_atomic", 0)),
        ("error_rate should not explode (< baseline + 0.05)",
         exp_agg.get("error_rate", 1.0) < base_agg.get("error_rate", 0) + 0.05),
    ]
    all_pass = True
    for label, passed in checks:
        mark = "[PASS]" if passed else "[FAIL]"
        print(f"  {mark}  {label}")
        if not passed:
            all_pass = False
    print()
    print(f"  Gate result: {'PASS — proceed to Phase C' if all_pass else 'FAIL — diagnose before proceeding'}")
    print()

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({
                "baseline": base_cases,
                "experimental": exp_cases,
                "baseline_agg": base_agg,
                "experimental_agg": exp_agg,
                "gate_pass": all_pass,
                "gate_checks": [(label, passed) for label, passed in checks],
            }, f, indent=2)
        print(f"JSON saved: {args.out}")


if __name__ == "__main__":
    main()
