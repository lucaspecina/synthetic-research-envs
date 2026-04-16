"""Closure item (4) of Suite 2 diagnostic battery — D1 × D2 joint-failure matrix.

Join `suite2_diag_d1_results.json` (pattern family recognition) ×
`suite2_diag_d2_results.json` (per-slot elicitation) ×
`compiler_baseline_full_dump_v2.json` (55-target baseline buckets).

Dos matrices 2×2:

(A) Principal — D1 × D2-critical (arm_kinds slot only):
    - D2-critical = bottleneck skeleton (arm_kinds match); fallback to status
      match for abstain golds
    - Distingue recognition vs composition GAPS en el slot que duele

(B) Secundaria — D1 × D2-strict (all slots match):
    - Mide calidad final de elicitación completa

Cada celda se enriquece con:
    - count
    - baseline bucket distribution
    - slot miss profile (qué slots rompen más en esa celda)

Hipótesis a distinguir (Codex #34):
    - ¿verdict_wrong se concentra en both-broken o composition-gap?
    - ¿full_pass también aparece en D1-pass + D2-fail (valida F13)?
    - ¿D1-fail + D2-pass es bloque real o anecdótico?
    - ¿D1 y D2 son ortogonales o una arrastra a la otra?

Deliverable: JSON + console summary + markdown-ready para §7.9 del strategy doc.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


BASELINE = Path("research/synthesis/compiler_baseline_full_dump_v2.json")
D1 = Path("research/synthesis/suite2_diag_d1_results.json")
D2 = Path("research/synthesis/suite2_diag_d2_results.json")
OUT = Path("research/synthesis/suite2_diag_d1_d2_joint_results.json")

SLOT_KEYS = [
    "status",
    "n_atoms",
    "arm_kinds",
    "role_vars",
    "measurement_kind",
    "comparison_kind",
    "assertion_polarity",
]


def d2_strict_pass(verdict: dict) -> bool:
    n_m = verdict.get("n_matched", 0)
    n_t = verdict.get("n_total", 0)
    return n_t > 0 and n_m == n_t


def d2_critical_pass(verdict: dict) -> bool:
    """For compile golds: arm_kinds.match. For abstain golds: status.match."""
    slots = verdict.get("slots", {})
    arm = slots.get("arm_kinds")
    if arm is not None and arm.get("match") is not None:
        return bool(arm["match"])
    st = slots.get("status")
    if st is not None and st.get("match") is not None:
        return bool(st["match"])
    return False


def slots_wrong(verdict: dict) -> list[str]:
    slots = verdict.get("slots", {})
    wrong = []
    for k in SLOT_KEYS:
        entry = slots.get(k)
        if entry is None:
            continue
        if entry.get("match") is False:
            wrong.append(k)
    return wrong


def cell_profile(items: list[dict]) -> dict:
    """Summarize a cell: counts, bucket dist, slot miss profile."""
    bucket_dist = Counter(i["bucket"] for i in items)
    slot_miss = Counter()
    for i in items:
        for s in i["slots_wrong"]:
            slot_miss[s] += 1
    return {
        "n": len(items),
        "by_bucket": dict(bucket_dist),
        "slot_miss_count": dict(slot_miss),
        "ids": [i["id"] for i in items],
    }


def build_matrix(items: list[dict], d2_key: str) -> dict:
    cells: dict[tuple, list[dict]] = {
        (True, True): [], (True, False): [],
        (False, True): [], (False, False): [],
    }
    for i in items:
        cells[(i["d1_pass"], i[d2_key])].append(i)
    return {
        "d1_pass_d2_pass": cell_profile(cells[(True, True)]),
        "d1_pass_d2_fail": cell_profile(cells[(True, False)]),
        "d1_fail_d2_pass": cell_profile(cells[(False, True)]),
        "d1_fail_d2_fail": cell_profile(cells[(False, False)]),
    }


def main() -> None:
    baseline = json.loads(BASELINE.read_text())
    d1 = json.loads(D1.read_text())
    d2 = json.loads(D2.read_text())

    b_by_id = {b["id"]: b for b in baseline}
    d1_by_id = {r["id"]: r for r in d1["results"]}
    d2_by_id = {r["id"]: r for r in d2["results"]}

    common = sorted(set(b_by_id) & set(d1_by_id) & set(d2_by_id))

    # Build joined records
    items: list[dict] = []
    for i in common:
        verdict = d2_by_id[i]["verdict"]
        items.append({
            "id": i,
            "family": d1_by_id[i].get("gold_family"),
            "bucket": b_by_id[i]["category"],
            "d1_pass": bool(d1_by_id[i].get("correct")),
            "d2_strict_pass": d2_strict_pass(verdict),
            "d2_critical_pass": d2_critical_pass(verdict),
            "slots_wrong": slots_wrong(verdict),
        })

    matrix_critical = build_matrix(items, "d2_critical_pass")
    matrix_strict = build_matrix(items, "d2_strict_pass")

    # --- Marginals + correlation ---
    n = len(items)
    d1_pass_n = sum(1 for i in items if i["d1_pass"])
    d2_crit_pass_n = sum(1 for i in items if i["d2_critical_pass"])
    d2_strict_pass_n = sum(1 for i in items if i["d2_strict_pass"])

    # Phi coefficient for D1 × D2-critical
    def phi(mx: dict) -> float:
        a = mx["d1_pass_d2_pass"]["n"]
        b = mx["d1_pass_d2_fail"]["n"]
        c = mx["d1_fail_d2_pass"]["n"]
        d = mx["d1_fail_d2_fail"]["n"]
        denom = ((a + b) * (c + d) * (a + c) * (b + d)) ** 0.5
        if denom == 0:
            return 0.0
        return (a * d - b * c) / denom

    phi_critical = phi(matrix_critical)
    phi_strict = phi(matrix_strict)

    # --- Bucket partitioning per cell (for quick reading) ---
    # Focus on compiled-but-wrong buckets (verdict_wrong + adjust_swap)
    def bucket_in_cell(mx: dict, bucket: str) -> dict:
        return {
            cell: mx[cell]["by_bucket"].get(bucket, 0)
            for cell in ["d1_pass_d2_pass", "d1_pass_d2_fail",
                         "d1_fail_d2_pass", "d1_fail_d2_fail"]
        }

    bucket_location = {
        b: {
            "critical": bucket_in_cell(matrix_critical, b),
            "strict": bucket_in_cell(matrix_strict, b),
        }
        for b in ["full_pass", "adjust_swap", "verdict_wrong",
                  "real_struct_err", "stage1_fail"]
    }

    # --- Interpretation ---
    interp: list[str] = []

    # I.1 marginals
    interp.append(
        f"Marginals: D1 pass={d1_pass_n}/{n} ({d1_pass_n/n:.0%}), "
        f"D2-critical pass={d2_crit_pass_n}/{n} ({d2_crit_pass_n/n:.0%}), "
        f"D2-strict pass={d2_strict_pass_n}/{n} ({d2_strict_pass_n/n:.0%})."
    )

    # I.2 phi
    interp.append(
        f"D1-D2 correlation (phi): critical={phi_critical:.2f}, "
        f"strict={phi_strict:.2f}. "
        f"Near 0 = orthogonal; |phi| > 0.3 = correlated."
    )

    # I.3 where does verdict_wrong live?
    vw_c = bucket_location["verdict_wrong"]["critical"]
    total_vw = sum(vw_c.values())
    if total_vw:
        dom = max(vw_c.items(), key=lambda kv: kv[1])
        interp.append(
            f"verdict_wrong ({total_vw}) concentration in D1×D2-critical: "
            f"dominant cell = {dom[0]} ({dom[1]}/{total_vw}). "
            f"Breakdown: {vw_c}."
        )

    # I.4 where does adjust_swap live?
    as_c = bucket_location["adjust_swap"]["critical"]
    total_as = sum(as_c.values())
    if total_as:
        dom = max(as_c.items(), key=lambda kv: kv[1])
        interp.append(
            f"adjust_swap ({total_as}) concentration in D1×D2-critical: "
            f"dominant cell = {dom[0]} ({dom[1]}/{total_as}). "
            f"Breakdown: {as_c}."
        )

    # I.5 full_pass in D1-pass+D2-fail (validates F13)?
    fp_c = bucket_location["full_pass"]["critical"]
    fp_strict = bucket_location["full_pass"]["strict"]
    interp.append(
        f"full_pass distribution (critical): {fp_c}; (strict): {fp_strict}. "
        f"If full_pass has any 'd1_pass_d2_fail' mass, F13 is validated "
        f"(D2 is noisier than the true compile oracle)."
    )

    # I.6 D1-fail + D2-pass — real or anecdotal?
    rfp_crit_n = matrix_critical["d1_fail_d2_pass"]["n"]
    rfp_strict_n = matrix_strict["d1_fail_d2_pass"]["n"]
    interp.append(
        f"d1_fail+d2_pass cell sizes: critical={rfp_crit_n}, "
        f"strict={rfp_strict_n}. Counts >= 3 = real block; <3 = anecdotal."
    )

    # I.7 top slots failing in composition-gap cell (d1_pass + d2_fail)
    cg_slots = matrix_critical["d1_pass_d2_fail"]["slot_miss_count"]
    if cg_slots:
        top = sorted(cg_slots.items(), key=lambda kv: -kv[1])[:4]
        top_str = ", ".join(f"{k}={v}" for k, v in top)
        interp.append(
            f"composition-gap cell (D1 pass + D2-critical fail) top slots: "
            f"{top_str}."
        )

    out = {
        "generated_by": "scripts/suite2_diag_d1_d2_joint_matrix.py",
        "sources": {"baseline": str(BASELINE), "d1": str(D1), "d2": str(D2)},
        "n_joined": n,
        "marginals": {
            "d1_pass": d1_pass_n,
            "d2_critical_pass": d2_crit_pass_n,
            "d2_strict_pass": d2_strict_pass_n,
            "total": n,
        },
        "correlation_phi": {
            "critical": phi_critical,
            "strict": phi_strict,
        },
        "matrix_critical": matrix_critical,
        "matrix_strict": matrix_strict,
        "bucket_location": bucket_location,
        "items": items,
        "interpretation": interp,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False))

    # --- Console summary ---
    print("=== D1 × D2 joint matrix ===\n")
    print(f"n_joined: {n}")
    print(f"Marginals: D1={d1_pass_n}, D2-crit={d2_crit_pass_n}, "
          f"D2-strict={d2_strict_pass_n}\n")

    def print_matrix(mx: dict, label: str) -> None:
        print(f"{label}:")
        print(f"  {'':>20} {'D2 pass':>14} {'D2 fail':>14}")
        for d1_label, keys in [
            ("D1 pass", ("d1_pass_d2_pass", "d1_pass_d2_fail")),
            ("D1 fail", ("d1_fail_d2_pass", "d1_fail_d2_fail")),
        ]:
            row = f"  {d1_label:>20}"
            for k in keys:
                row += f"{mx[k]['n']:>14}"
            print(row)
        print()

    print_matrix(matrix_critical, "A. D1 × D2-critical (arm_kinds)")
    print(f"   phi = {phi_critical:.2f}")
    print()
    print_matrix(matrix_strict, "B. D1 × D2-strict (all slots)")
    print(f"   phi = {phi_strict:.2f}")
    print()

    print("C. Bucket distribution per cell (critical matrix):")
    for cell in ["d1_pass_d2_pass", "d1_pass_d2_fail",
                 "d1_fail_d2_pass", "d1_fail_d2_fail"]:
        info = matrix_critical[cell]
        print(f"  {cell:<24} n={info['n']:<3} buckets={info['by_bucket']}")
    print()

    print("D. Slot miss profile per cell (critical matrix, where D2 fails):")
    for cell in ["d1_pass_d2_fail", "d1_fail_d2_fail"]:
        info = matrix_critical[cell]
        if not info["slot_miss_count"]:
            continue
        top = sorted(info["slot_miss_count"].items(),
                     key=lambda kv: -kv[1])[:5]
        top_str = ", ".join(f"{k}={v}" for k, v in top)
        print(f"  {cell:<24} top-slot-misses: {top_str}")
    print()

    print("E. Where does each bucket fall (critical matrix):")
    for b, loc in bucket_location.items():
        c = loc["critical"]
        nonzero = {k: v for k, v in c.items() if v}
        print(f"  {b:<18} {nonzero}")
    print()

    print("F. Interpretation:")
    for line in interp:
        print(f"  - {line}")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
