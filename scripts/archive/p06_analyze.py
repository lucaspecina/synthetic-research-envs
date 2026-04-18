#!/usr/bin/env python
"""P06 Phase C analysis: per-case deltas + confound detection + verdict.

Implements the pre-registered interpretation rule in
research/notes/p06_interpretation_rule.md mechanically. Read-only. No LLM.

Inputs:
  --baseline DIR     baseline batch (e.g. results/p05_canonical_batch)
  --experimental DIR paired batch (e.g. results/p06_paired)
  --out FILE         JSON output (optional)

Outputs:
  1. Per-case table: delta_total, delta_correctness, delta_coverage,
     n_claims base/exp, mean_n_specs base/exp, frac_atomic base/exp
  2. Per-case confound flags: evidence_penalty, force_submit, cap_pegged,
     abstentions, compile_failures
  3. Aggregate metrics: P1, C1, C2, C3 from the pre-registered rule
  4. Red flags: RF1, RF2, RF3, RF4, RF5
  5. Verdict: STRONG WIN / WEAK WIN / INCONCLUSIVE / SUSPICIOUS /
     DIFFERENT STORY / HYPOTHESIS FAILS

This script does NOT make judgment calls beyond what's in the rule file.
If the rule says "RF1 fires when >= 3 cases hit 15 claims", that's what
this script checks — not "mostly OK".
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Load + confound detection
# ---------------------------------------------------------------------------


def _load_oi(case_dir: Path) -> dict | None:
    p = case_dir / "oi_result.json"
    if not p.exists():
        return None
    return json.load(open(p, encoding="utf-8"))


def _load_metrics(case_dir: Path) -> dict | None:
    """Load case metrics + confounds from oi_result.json."""
    res = _load_oi(case_dir)
    if res is None:
        return None

    si = res.get("score_inputs_v2", {})
    sc = res.get("score", {}) or {}

    claims_raw = si.get("claims", [])
    compiled = si.get("compiled_claims", [])

    n_claims = len(claims_raw)
    n_compiled = sum(1 for c in compiled if c.get("status") == "compiled")
    n_partial = sum(1 for c in compiled if c.get("status") == "partial")
    n_abstention = sum(1 for c in compiled if c.get("status") == "abstention")
    n_error = n_claims - n_compiled - n_partial - n_abstention

    # n_specs per (non-abstention) claim
    n_specs_list: list[int] = []
    for c in compiled:
        if c.get("status") == "abstention":
            continue
        n = sum(len(u.get("specs", [])) for u in c.get("units", []))
        n_specs_list.append(n)
    mean_n_specs = mean(n_specs_list) if n_specs_list else 0.0
    frac_atomic = (
        sum(1 for n in n_specs_list if n == 1) / len(n_specs_list)
        if n_specs_list else 0.0
    )

    # --- Confound detection ---

    # Force-submit: look for the force-submit nudge text in conversation
    msgs = res.get("conversation", [])
    force_submit = any(
        "MUST call submit_claims NOW" in str(m.get("content", ""))
        or "exhausted all iterations" in str(m.get("content", ""))
        for m in msgs
    )

    # Evidence-basis fabrication: claims with artifact_ids NOT in trace
    trace = si.get("trace", {})
    accessed = set()
    for a in trace.get("accesses", []):
        aid = a.get("artifact_id")
        if aid:
            accessed.add(aid)
    # If trace is empty (very old format), infer from data_assets
    fabricated_claims = 0
    for c in claims_raw:
        eb = c.get("evidence_basis", []) or []
        cited = {ref.get("artifact_id") for ref in eb if ref.get("artifact_id")}
        if accessed and cited and (cited - accessed):
            fabricated_claims += 1

    # Cap pegged at 15 (experimental) or 5 (baseline)
    cap_pegged_15 = n_claims == 15
    cap_pegged_5 = n_claims == 5

    return {
        "n_claims": n_claims,
        "mean_n_specs": mean_n_specs,
        "frac_atomic": frac_atomic,
        "n_compiled": n_compiled,
        "n_partial": n_partial,
        "n_abstention": n_abstention,
        "n_error": n_error,
        "correctness": sc.get("correctness", 0.0),
        "weighted_coverage": sc.get("weighted_coverage", 0.0),
        "total": sc.get("total", 0.0),
        "force_submit": force_submit,
        "fabricated_claims": fabricated_claims,
        "cap_pegged_15": cap_pegged_15,
        "cap_pegged_5": cap_pegged_5,
        "abstention_rate": n_abstention / max(n_claims, 1),
        "error_rate": n_error / max(n_claims, 1),
    }


def _pearson(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation (no numpy dep)."""
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = (sum((x - mx) ** 2 for x in xs)) ** 0.5
    dy = (sum((y - my) ** 2 for y in ys)) ** 0.5
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------


def _print_table(rows: list[dict], cols: list[tuple[str, str]]):
    """rows is list of dicts. cols is list of (header, key)."""
    headers = [c[0] for c in cols]
    keys = [c[1] for c in cols]

    def _cell(v):
        if isinstance(v, float):
            return f"{v:+.3f}" if v != int(v) else f"{v:+.1f}"
        if isinstance(v, bool):
            return "Y" if v else "."
        return str(v)

    widths = [
        max(
            len(h),
            max((len(_cell(r.get(k, ""))) for r in rows), default=0),
        )
        for h, k in zip(headers, keys)
    ]
    sep = "  "
    print("  " + sep.join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  " + sep.join("-" * w for w in widths))
    for r in rows:
        print("  " + sep.join(_cell(r.get(k, "")).ljust(w) for k, w in zip(keys, widths)))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", required=True)
    p.add_argument("--experimental", required=True)
    p.add_argument("--out", default=None)
    args = p.parse_args()

    baseline_dir = Path(args.baseline)
    exp_dir = Path(args.experimental)

    # Gather cases present in experimental
    case_names = sorted(
        d.name for d in exp_dir.iterdir()
        if d.is_dir() and (d / "oi_result.json").exists()
    )

    per_case: list[dict] = []
    for name in case_names:
        base = _load_metrics(baseline_dir / name)
        exp = _load_metrics(exp_dir / name)
        if base is None or exp is None:
            print(f"  SKIP {name}: missing baseline or experimental")
            continue
        per_case.append({
            "case": name,
            # base
            "b_total": round(base["total"], 3),
            "b_corr": round(base["correctness"], 3),
            "b_cov": round(base["weighted_coverage"], 3),
            "b_nc": base["n_claims"],
            "b_specs": round(base["mean_n_specs"], 2),
            "b_atom": round(base["frac_atomic"], 2),
            # exp
            "e_total": round(exp["total"], 3),
            "e_corr": round(exp["correctness"], 3),
            "e_cov": round(exp["weighted_coverage"], 3),
            "e_nc": exp["n_claims"],
            "e_specs": round(exp["mean_n_specs"], 2),
            "e_atom": round(exp["frac_atomic"], 2),
            # deltas
            "d_total": round(exp["total"] - base["total"], 3),
            "d_corr": round(exp["correctness"] - base["correctness"], 3),
            "d_cov": round(exp["weighted_coverage"] - base["weighted_coverage"], 3),
            # confounds (b = baseline, e = experimental)
            "b_force": base["force_submit"],
            "e_force": exp["force_submit"],
            "b_fab": base["fabricated_claims"],
            "e_fab": exp["fabricated_claims"],
            "e_peg15": exp["cap_pegged_15"],
            "b_peg5": base["cap_pegged_5"],
            "e_abst": round(exp["abstention_rate"], 2),
            "e_err": round(exp["error_rate"], 2),
            # keep raw for aggregation
            "_base": base,
            "_exp": exp,
        })

    if not per_case:
        print("No cases to analyze.")
        return

    print()
    print("=" * 110)
    print("  P06 PHASE C — PAIRED ANALYSIS")
    print("=" * 110)
    print(f"  baseline:       {baseline_dir}")
    print(f"  experimental:   {exp_dir}")
    print(f"  cases analyzed: {len(per_case)}")
    print()

    # --- Table 1: scores + deltas ---
    print("SCORES (base / exp / delta):")
    _print_table(per_case, [
        ("case", "case"),
        ("b_total", "b_total"), ("e_total", "e_total"), ("d_total", "d_total"),
        ("b_corr", "b_corr"),   ("e_corr", "e_corr"),   ("d_corr", "d_corr"),
        ("b_cov", "b_cov"),     ("e_cov", "e_cov"),     ("d_cov", "d_cov"),
    ])
    print()

    # --- Table 2: atomization metrics ---
    print("ATOMIZATION (base -> exp):")
    _print_table(per_case, [
        ("case", "case"),
        ("b_nc", "b_nc"), ("e_nc", "e_nc"),
        ("b_specs", "b_specs"), ("e_specs", "e_specs"),
        ("b_atom", "b_atom"), ("e_atom", "e_atom"),
    ])
    print()

    # --- Table 3: confound flags ---
    print("CONFOUNDS (Y = flag fired):")
    _print_table(per_case, [
        ("case", "case"),
        ("b_force", "b_force"), ("e_force", "e_force"),
        ("b_fab", "b_fab"), ("e_fab", "e_fab"),
        ("b_peg5", "b_peg5"), ("e_peg15", "e_peg15"),
        ("e_abst", "e_abst"), ("e_err", "e_err"),
    ])
    print()

    # --- Aggregate metrics ---
    def _agg(key: str) -> float:
        return mean(c[key] for c in per_case)

    agg_d_corr = _agg("d_corr")
    agg_d_cov = _agg("d_cov")
    agg_d_total = _agg("d_total")
    agg_d_specs = _agg("e_specs") - _agg("b_specs")
    agg_d_atom = _agg("e_atom") - _agg("b_atom")
    agg_d_nc = _agg("e_nc") - _agg("b_nc")

    n_pos_corr = sum(1 for c in per_case if c["d_corr"] > 0)
    n_pos_cov = sum(1 for c in per_case if c["d_cov"] > 0)
    n_pos_total = sum(1 for c in per_case if c["d_total"] > 0)

    # Pearson correlation: baseline mean_n_specs vs delta_total
    base_specs = [c["b_specs"] for c in per_case]
    d_totals = [c["d_total"] for c in per_case]
    corr_bundling = _pearson(base_specs, d_totals)

    print("AGGREGATE (means over", len(per_case), "cases):")
    print(f"  delta_correctness       = {agg_d_corr:+.4f}  ({n_pos_corr}/{len(per_case)} positive)")
    print(f"  delta_weighted_coverage = {agg_d_cov:+.4f}  ({n_pos_cov}/{len(per_case)} positive)")
    print(f"  delta_total             = {agg_d_total:+.4f}  ({n_pos_total}/{len(per_case)} positive)")
    print(f"  delta_mean_n_specs      = {agg_d_specs:+.4f}")
    print(f"  delta_frac_atomic       = {agg_d_atom:+.4f}")
    print(f"  delta_n_claims          = {agg_d_nc:+.4f}")
    print(f"  corr(base_specs, d_tot) = {corr_bundling:+.4f}")
    print()

    # --- Pre-registered criteria ---
    N = len(per_case)
    p1_pass = (agg_d_corr >= 0.03) and (n_pos_corr >= round(0.66 * N))
    c1_pass = (agg_d_specs <= -0.5) and (agg_d_atom >= 0.15)
    c2_pass = (agg_d_cov >= 0.05) and (_sign_match(per_case, "d_corr", "d_cov") >= round(0.66 * N))
    c3_pass = corr_bundling >= 0.30

    # Red flags
    n_peg15 = sum(1 for c in per_case if c["e_peg15"])
    b_force_count = sum(1 for c in per_case if c["b_force"])
    e_force_count = sum(1 for c in per_case if c["e_force"])
    agg_d_abst_err = _agg("e_abst") + _agg("e_err") - (
        _agg_base("b_base_abst_err", per_case)
    )
    new_fab = sum(
        1 for c in per_case if c["e_fab"] > 0 and c["b_fab"] == 0
    )

    rf1 = n_peg15 >= 3
    rf2 = e_force_count > b_force_count + 2
    rf3 = agg_d_abst_err >= 0.05
    rf4 = new_fab >= 3

    # RF5: exclude confounded cases and re-check P1
    robust_cases = [
        c for c in per_case
        if not c["e_force"] and c["e_fab"] == 0 and not c["e_peg15"]
    ]
    if robust_cases:
        robust_d_corr = mean(c["d_corr"] for c in robust_cases)
        rf5 = robust_d_corr < 0.03
    else:
        robust_d_corr = None
        rf5 = True  # no robust cases at all → definitely not robust

    print("PRE-REGISTERED CRITERIA:")
    _mark = lambda v: "[PASS]" if v else "[FAIL]"
    print(f"  {_mark(p1_pass)} P1: agg_d_corr >= +0.03 AND >= {round(0.66*N)}/{N} cases positive")
    print(f"         -> agg_d_corr={agg_d_corr:+.4f}, {n_pos_corr}/{N} positive")
    print(f"  {_mark(c1_pass)} C1: agg_d_specs <= -0.5 AND agg_d_atom >= +0.15")
    print(f"         -> agg_d_specs={agg_d_specs:+.4f}, agg_d_atom={agg_d_atom:+.4f}")
    print(f"  {_mark(c2_pass)} C2: agg_d_cov >= +0.05 AND same-sign corr/cov on {round(0.66*N)}/{N}")
    print(f"         -> agg_d_cov={agg_d_cov:+.4f}")
    print(f"  {_mark(c3_pass)} C3: corr(base_specs, d_tot) >= +0.30")
    print(f"         -> corr={corr_bundling:+.4f}")
    print()

    print("RED FLAGS:")
    _rmark = lambda v: "[FIRED]" if v else "[ok]   "
    print(f"  {_rmark(rf1)} RF1: >=3 cases pegged at 15 claims ({n_peg15} fired)")
    print(f"  {_rmark(rf2)} RF2: e_force > b_force+2 (b={b_force_count}, e={e_force_count})")
    print(f"  {_rmark(rf3)} RF3: delta abstention+error >= +0.05 (agg={agg_d_abst_err:+.4f})")
    print(f"  {_rmark(rf4)} RF4: new fabrication >=3 cases ({new_fab} cases)")
    rf5_str = (
        f"robust_d_corr={robust_d_corr:+.4f}" if robust_d_corr is not None
        else "NO robust cases"
    )
    print(f"  {_rmark(rf5)} RF5: robust-subset d_corr below +0.03 ({rf5_str})")
    print()

    # --- Verdict ---
    any_rf = rf1 or rf2 or rf3 or rf4 or rf5
    if p1_pass and c1_pass and c2_pass and c3_pass and not any_rf:
        verdict = "STRONG WIN"
        reason = "All pre-registered criteria pass; no red flags."
    elif p1_pass and c1_pass and not any_rf:
        verdict = "WEAK WIN"
        reason = "Primary + mechanism pass; corroboration mixed; no red flags."
    elif p1_pass and c1_pass and any_rf:
        verdict = "INCONCLUSIVE"
        reason = "Primary passes but confounds present; interpret with care."
    elif p1_pass and not c1_pass:
        verdict = "SUSPICIOUS"
        reason = "Scores improved without atomization mechanism firing."
    elif (not p1_pass) and c2_pass:
        verdict = "DIFFERENT STORY"
        reason = "Coverage improved, correctness did not. Not a bundling win."
    else:
        verdict = "HYPOTHESIS FAILS"
        reason = "Primary criterion not met."

    print("=" * 110)
    print(f"  VERDICT: {verdict}")
    print(f"  reason:  {reason}")
    print("=" * 110)
    print()

    # Drop internal refs before JSON dump
    for c in per_case:
        c.pop("_base", None)
        c.pop("_exp", None)

    if args.out:
        out = {
            "baseline": str(baseline_dir),
            "experimental": str(exp_dir),
            "per_case": per_case,
            "aggregate": {
                "delta_correctness": agg_d_corr,
                "delta_weighted_coverage": agg_d_cov,
                "delta_total": agg_d_total,
                "delta_mean_n_specs": agg_d_specs,
                "delta_frac_atomic": agg_d_atom,
                "delta_n_claims": agg_d_nc,
                "n_pos_correctness": n_pos_corr,
                "n_pos_coverage": n_pos_cov,
                "n_pos_total": n_pos_total,
                "corr_baseline_specs_delta_total": corr_bundling,
            },
            "criteria": {
                "P1": p1_pass,
                "C1": c1_pass,
                "C2": c2_pass,
                "C3": c3_pass,
            },
            "red_flags": {
                "RF1_cap_peg15_cases": n_peg15,
                "RF1_fired": rf1,
                "RF2_force_submit_baseline": b_force_count,
                "RF2_force_submit_experimental": e_force_count,
                "RF2_fired": rf2,
                "RF3_agg_delta_abst_err": agg_d_abst_err,
                "RF3_fired": rf3,
                "RF4_new_fabrication_cases": new_fab,
                "RF4_fired": rf4,
                "RF5_robust_d_corr": robust_d_corr,
                "RF5_fired": rf5,
            },
            "verdict": verdict,
            "reason": reason,
        }
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"  JSON saved: {args.out}")
        print()


def _sign_match(per_case: list[dict], key_a: str, key_b: str) -> int:
    """Count cases where sign(a) == sign(b)."""
    return sum(
        1 for c in per_case
        if (c[key_a] > 0) == (c[key_b] > 0) or (c[key_a] == 0 and c[key_b] == 0)
    )


def _agg_base(_label, per_case: list[dict]) -> float:
    """Return baseline aggregate of (abstention_rate + error_rate)."""
    vals = []
    for c in per_case:
        b = c.get("_base", {}) or {}
        vals.append(b.get("abstention_rate", 0.0) + b.get("error_rate", 0.0))
    return mean(vals) if vals else 0.0


if __name__ == "__main__":
    main()
