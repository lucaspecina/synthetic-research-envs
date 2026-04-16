"""Closure item (3) of Suite 2 diagnostic battery — D2 slots × baseline verdicts.

Joins `research/synthesis/suite2_diag_d2_results.json` (offline slot
elicitation, per-slot match=true/false) with
`research/synthesis/compiler_baseline_full_dump_v2.json` (55-target baseline,
bucketed into full_pass / verdict_wrong / adjust_swap / real_struct_err /
stage1_fail).

Keys answered:

1. Per-bucket slot accuracy: does arm_kinds drop more inside verdict_wrong and
   adjust_swap than inside full_pass? (If yes, slot-fail → verdict-fail
   attribution is direct.)
2. n_slots_wrong distribution per bucket: how many slots fail on average in
   each bucket?
3. Slot-fail attribution: of the N cases where slot X was wrong in D2, how
   many fell into each verdict bucket?
4. Per-id detail for verdict_wrong (19) + adjust_swap (10) — the 29 compiled-
   but-wrong cases: which slots failed?

Deliverable: JSON + markdown-ready summary for strategy doc §7.8.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


BASELINE = Path("research/synthesis/compiler_baseline_full_dump_v2.json")
D2 = Path("research/synthesis/suite2_diag_d2_results.json")
OUT = Path("research/synthesis/suite2_diag_d2_verdict_zipper.json")

SLOT_KEYS = [
    "status",
    "n_atoms",
    "arm_kinds",
    "role_vars",
    "measurement_kind",
    "comparison_kind",
    "assertion_polarity",
]

BUCKETS = ["full_pass", "adjust_swap", "verdict_wrong",
           "real_struct_err", "stage1_fail"]


def slot_hit(verdict: dict, slot: str) -> bool | None:
    entry = verdict.get("slots", {}).get(slot)
    if entry is None:
        return None
    match = entry.get("match")
    if match is None:
        return None
    return bool(match)


def slot_detail(verdict: dict, slot: str) -> dict | None:
    entry = verdict.get("slots", {}).get(slot)
    if entry is None:
        return None
    return {"gold": entry.get("gold"), "pred": entry.get("pred"),
            "match": entry.get("match")}


def main() -> None:
    baseline = json.loads(BASELINE.read_text())
    d2 = json.loads(D2.read_text())
    d2_results = d2["results"]

    b_by_id = {b["id"]: b for b in baseline}
    d2_by_id = {r["id"]: r for r in d2_results}

    common = sorted(set(b_by_id) & set(d2_by_id))
    missing_in_d2 = sorted(set(b_by_id) - set(d2_by_id))
    missing_in_baseline = sorted(set(d2_by_id) - set(b_by_id))

    # --- A. Bucket distribution ---
    bucket_dist = Counter(b_by_id[i]["category"] for i in common)

    # --- B. Per-bucket slot accuracy ---
    slot_by_bucket: dict[str, dict[str, list[bool]]] = {
        b: defaultdict(list) for b in BUCKETS
    }
    for i in common:
        bucket = b_by_id[i]["category"]
        verdict = d2_by_id[i]["verdict"]
        for slot in SLOT_KEYS:
            hit = slot_hit(verdict, slot)
            if hit is not None:
                slot_by_bucket[bucket][slot].append(hit)

    def rate(lst: list[bool]) -> float:
        return round(sum(lst) / len(lst), 3) if lst else 0.0

    per_bucket_slot_acc = {
        bucket: {slot: {"n": len(lst), "acc": rate(lst)}
                 for slot, lst in sorted(slots.items())}
        for bucket, slots in slot_by_bucket.items()
    }

    # --- C. n_slots_wrong distribution per bucket ---
    nwrong_by_bucket: dict[str, Counter] = {b: Counter() for b in BUCKETS}
    for i in common:
        bucket = b_by_id[i]["category"]
        verdict = d2_by_id[i]["verdict"]
        nwrong = 0
        for slot in SLOT_KEYS:
            hit = slot_hit(verdict, slot)
            if hit is False:
                nwrong += 1
        nwrong_by_bucket[bucket][nwrong] += 1

    # --- D. Slot-fail attribution ---
    # For each slot, of the cases where the slot failed in D2, which bucket
    # did each fall into?
    slot_attr: dict[str, dict] = {}
    for slot in SLOT_KEYS:
        by_bucket = Counter()
        total_miss = 0
        total_eval = 0
        for i in common:
            hit = slot_hit(d2_by_id[i]["verdict"], slot)
            if hit is None:
                continue
            total_eval += 1
            if not hit:
                total_miss += 1
                by_bucket[b_by_id[i]["category"]] += 1
        slot_attr[slot] = {
            "total_eval": total_eval,
            "total_miss": total_miss,
            "miss_by_bucket": dict(by_bucket),
        }

    # --- E. Per-id detail for the 29 compiled-but-wrong (verdict_wrong +
    # adjust_swap) ---
    detail: dict[str, list[dict]] = {"verdict_wrong": [], "adjust_swap": []}
    for i in common:
        bucket = b_by_id[i]["category"]
        if bucket not in detail:
            continue
        verdict = d2_by_id[i]["verdict"]
        slots_wrong = [s for s in SLOT_KEYS if slot_hit(verdict, s) is False]
        slot_info = {s: slot_detail(verdict, s) for s in slots_wrong}
        detail[bucket].append({
            "id": i,
            "family": d2_by_id[i].get("family"),
            "world": d2_by_id[i].get("world"),
            "slots_wrong": slots_wrong,
            "slot_details": slot_info,
        })

    # --- F. Interpretation ---
    interp: list[str] = []

    # F.1 arm_kinds across buckets
    arm_fp = per_bucket_slot_acc["full_pass"].get(
        "arm_kinds", {}).get("acc", 0)
    arm_vw = per_bucket_slot_acc["verdict_wrong"].get(
        "arm_kinds", {}).get("acc", 0)
    arm_as = per_bucket_slot_acc["adjust_swap"].get(
        "arm_kinds", {}).get("acc", 0)
    interp.append(
        f"arm_kinds accuracy by bucket: full_pass={arm_fp:.0%}, "
        f"adjust_swap={arm_as:.0%}, verdict_wrong={arm_vw:.0%}."
    )

    # F.2 Dominant failing slot inside adjust_swap
    as_slots = per_bucket_slot_acc["adjust_swap"]
    as_ranked = sorted(
        [(s, d["acc"], d["n"]) for s, d in as_slots.items()],
        key=lambda x: x[1],
    )
    if as_ranked:
        worst_as = as_ranked[0]
        interp.append(
            f"Worst D2 slot inside adjust_swap (n={bucket_dist['adjust_swap']}): "
            f"{worst_as[0]}={worst_as[1]:.0%}."
        )

    # F.3 Dominant failing slot inside verdict_wrong
    vw_slots = per_bucket_slot_acc["verdict_wrong"]
    vw_ranked = sorted(
        [(s, d["acc"], d["n"]) for s, d in vw_slots.items()],
        key=lambda x: x[1],
    )
    if vw_ranked:
        worst_vw = vw_ranked[0]
        interp.append(
            f"Worst D2 slot inside verdict_wrong "
            f"(n={bucket_dist['verdict_wrong']}): "
            f"{worst_vw[0]}={worst_vw[1]:.0%}."
        )

    # F.4 Slot-attribution summary
    for slot in ["arm_kinds", "assertion_polarity", "comparison_kind"]:
        a = slot_attr[slot]
        if a["total_miss"]:
            breakdown = ", ".join(
                f"{k}={v}" for k, v in sorted(
                    a["miss_by_bucket"].items(), key=lambda x: -x[1])
            )
            interp.append(
                f"{slot} misses ({a['total_miss']}/{a['total_eval']}) by "
                f"bucket: {breakdown}."
            )

    # F.5 Does full_pass have any slot failures? (Expected: ~0)
    fp_any_wrong = sum(
        nwrong_by_bucket["full_pass"][k] for k in nwrong_by_bucket["full_pass"]
        if k > 0
    )
    interp.append(
        f"full_pass (n={bucket_dist['full_pass']}) D2 slot failures: "
        f"{fp_any_wrong} cases have >=1 D2 slot wrong "
        f"(expected ~0 if D2 is well-calibrated)."
    )

    out = {
        "generated_by": "scripts/suite2_diag_d2_verdict_zipper.py",
        "sources": {"baseline": str(BASELINE), "d2": str(D2)},
        "n_joined": len(common),
        "missing_in_d2": missing_in_d2,
        "missing_in_baseline": missing_in_baseline,
        "bucket_distribution": dict(bucket_dist),
        "per_bucket_slot_acc": per_bucket_slot_acc,
        "n_slots_wrong_by_bucket": {
            b: dict(c) for b, c in nwrong_by_bucket.items()
        },
        "slot_attribution": slot_attr,
        "compiled_but_wrong_detail": detail,
        "interpretation": interp,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False))

    # --- Console summary ---
    print("=== D2 × verdict zipper ===\n")
    print(f"Joined {len(common)} ids "
          f"(missing_in_d2={len(missing_in_d2)}, "
          f"missing_in_baseline={len(missing_in_baseline)}).")
    print(f"Buckets: {dict(bucket_dist)}\n")

    print("A. Per-bucket slot accuracy:")
    header = "bucket".ljust(18) + "".join(s[:8].rjust(10) for s in SLOT_KEYS)
    print(" ", header)
    for bucket in BUCKETS:
        if bucket_dist[bucket] == 0:
            continue
        row = bucket.ljust(18)
        for slot in SLOT_KEYS:
            entry = per_bucket_slot_acc[bucket].get(slot, {})
            acc = entry.get("acc", 0)
            n = entry.get("n", 0)
            row += f"{acc:.0%}({n})".rjust(10)
        print(" ", row)

    print("\nB. n_slots_wrong distribution per bucket:")
    for bucket in BUCKETS:
        if bucket_dist[bucket] == 0:
            continue
        c = nwrong_by_bucket[bucket]
        parts = ", ".join(f"{k}->{c[k]}" for k in sorted(c))
        print(f"  {bucket:<18} total={bucket_dist[bucket]:<3} ({parts})")

    print("\nC. Slot-fail attribution (where did the misses fall?):")
    for slot in SLOT_KEYS:
        a = slot_attr[slot]
        if not a["total_miss"]:
            continue
        bybk = ", ".join(
            f"{k}={v}"
            for k, v in sorted(a["miss_by_bucket"].items(), key=lambda x: -x[1])
        )
        print(f"  {slot:<22} "
              f"miss={a['total_miss']}/{a['total_eval']:<3}  [{bybk}]")

    print("\nD. Compiled-but-wrong slot signatures:")
    for bucket, items in detail.items():
        print(f"\n  {bucket} (n={len(items)}):")
        for item in items:
            sig = ",".join(item["slots_wrong"]) if item["slots_wrong"] else "(none)"
            print(f"    {item['id']:<14} [{item['family']:<8}]  {sig}")

    print("\nE. Interpretation:")
    for line in interp:
        print(f"  - {line}")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
