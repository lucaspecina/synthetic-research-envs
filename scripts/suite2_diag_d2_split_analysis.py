"""Closure item (2) of Suite 2 diagnostic battery — D2 split by n_atoms.

Post-processes `research/synthesis/suite2_diag_d2_results.json` to answer:

1. Per-slot accuracy split by gold.n_atoms = 1 vs >1.
   - Does accuracy drop for multi-atom (mediation/heterogeneity) claims?
2. Cardinality collapse: for multi-atom golds, how often does predicted
   n_atoms collapse to 1?
3. Arm_kinds accuracy split by claim type:
   - single-arm observational (n_atoms=1, kinds subset of
     {baseline, observe, condition})
   - single-arm causal (n_atoms=1, intervene in kinds)
   - contrast-causal (n_atoms=1, kinds like [intervene, observe] pair)
   - multi-atom (n_atoms>1)
4. Is the arm_kinds bottleneck (50% accuracy) driven by a single
   category?

Deliverable: JSON + markdown-ready summary to splice into
strategy doc §7.4.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


D2_RESULTS = Path("research/synthesis/suite2_diag_d2_results.json")
OUT = Path("research/synthesis/suite2_diag_d2_split_results.json")

SLOT_KEYS = [
    "status",
    "n_atoms",
    "arm_kinds",
    "role_vars",
    "measurement_kind",
    "comparison_kind",
    "assertion_polarity",
]


def classify_claim(gold: dict) -> str:
    """Classify gold structural contract into a diagnostic bucket."""
    if gold.get("status") != "compile":
        return "abstain"
    n_atoms = gold.get("n_atoms")
    if isinstance(n_atoms, list):
        n_atoms = n_atoms[0] if n_atoms else 1
    if n_atoms and n_atoms > 1:
        return "multi_atom"
    kinds = set(gold.get("arm_kinds", []))
    if not kinds:
        return "single_unknown"
    obs_kinds = {"baseline", "observe", "condition"}
    if kinds.issubset(obs_kinds):
        return "single_observational"
    if "adjust" in kinds:
        return "single_adjust"
    if "sweep" in kinds:
        return "single_sweep"
    if len(kinds) >= 2 and "intervene" in kinds:
        return "single_contrast_causal"
    if kinds == {"intervene"}:
        return "single_causal"
    return "single_other"


def slot_hit(verdict: dict, slot: str) -> bool | None:
    """True/False if the slot was judged; None if the slot is absent
    (e.g. abstain gold has no arm_kinds verdict)."""
    slots = verdict.get("slots", {})
    entry = slots.get(slot)
    if entry is None:
        return None
    match = entry.get("match")
    if match is None:
        return None
    return bool(match)


def main() -> None:
    data = json.loads(D2_RESULTS.read_text())
    results = data["results"]

    # --- A. Per-slot accuracy split by n_atoms ---
    acc_by_natoms: dict[str, dict[str, list[bool]]] = {
        "n1": defaultdict(list),
        "n_gt1": defaultdict(list),
    }
    for r in results:
        gold = r["gold"]
        if gold.get("status") != "compile":
            continue
        n = gold.get("n_atoms")
        if isinstance(n, list):
            n = n[0] if n else 1
        bucket = "n1" if (n or 1) == 1 else "n_gt1"
        for slot in SLOT_KEYS:
            hit = slot_hit(r["verdict"], slot)
            if hit is not None:
                acc_by_natoms[bucket][slot].append(hit)

    def rate(lst: list[bool]) -> float:
        return round(sum(lst) / len(lst), 3) if lst else 0.0

    split_natoms = {
        bucket: {slot: {"n": len(lst), "acc": rate(lst)}
                 for slot, lst in slots.items()}
        for bucket, slots in acc_by_natoms.items()
    }

    # --- B. Cardinality collapse (multi-atom gold -> single-atom pred) ---
    collapse_stats = {"multi_atom_total": 0, "collapsed_to_1": 0,
                      "kept_multi": 0, "raised_to_multi": 0,
                      "single_atom_total": 0, "kept_single": 0}
    collapsed_ids: list[str] = []
    for r in results:
        gold = r["gold"]
        pred = r["predicted"]
        if gold.get("status") != "compile" or pred.get("status") != "compile":
            continue
        gn = gold.get("n_atoms")
        if isinstance(gn, list):
            gn = gn[0] if gn else 1
        pn = pred.get("n_atoms")
        if isinstance(pn, list):
            pn = pn[0] if pn else 1
        if (gn or 1) > 1:
            collapse_stats["multi_atom_total"] += 1
            if (pn or 1) == 1:
                collapse_stats["collapsed_to_1"] += 1
                collapsed_ids.append(r["id"])
            else:
                collapse_stats["kept_multi"] += 1
        else:
            collapse_stats["single_atom_total"] += 1
            if (pn or 1) == 1:
                collapse_stats["kept_single"] += 1
            else:
                collapse_stats["raised_to_multi"] += 1

    # --- C. Arm_kinds accuracy by claim type ---
    arm_acc_by_type: dict[str, list[bool]] = defaultdict(list)
    arm_miss_by_type: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        gold = r["gold"]
        if gold.get("status") != "compile":
            continue
        ctype = classify_claim(gold)
        hit = slot_hit(r["verdict"], "arm_kinds")
        if hit is None:
            continue
        arm_acc_by_type[ctype].append(hit)
        if not hit:
            arm_miss_by_type[ctype].append({
                "id": r["id"],
                "family": r["family"],
                "gold_kinds": gold.get("arm_kinds", []),
                "pred_kinds": (r["verdict"]["slots"].get("arm_kinds", {})
                               .get("pred", [])),
            })

    arm_by_type = {
        ctype: {
            "n": len(lst),
            "acc": rate(lst),
            "misses": len([x for x in lst if not x]),
        }
        for ctype, lst in arm_acc_by_type.items()
    }

    # --- D. Summary interpretation ---
    interp = []
    # D.1 n_atoms drop
    n1_arm = split_natoms["n1"].get("arm_kinds", {}).get("acc", 0)
    ngt1_arm = split_natoms["n_gt1"].get("arm_kinds", {}).get("acc", 0)
    n1_n = split_natoms["n1"].get("arm_kinds", {}).get("n", 0)
    ngt1_n = split_natoms["n_gt1"].get("arm_kinds", {}).get("n", 0)
    interp.append(
        f"arm_kinds accuracy: n_atoms=1 -> {n1_arm:.0%} ({n1_n}); "
        f"n_atoms>1 -> {ngt1_arm:.0%} ({ngt1_n})."
    )

    # D.2 cardinality collapse
    if collapse_stats["multi_atom_total"]:
        collapse_rate = (collapse_stats["collapsed_to_1"]
                         / collapse_stats["multi_atom_total"])
        interp.append(
            f"Cardinality collapse: {collapse_stats['collapsed_to_1']}/"
            f"{collapse_stats['multi_atom_total']} multi-atom golds "
            f"predicted as single-atom ({collapse_rate:.0%})."
        )

    # D.3 worst arm-kinds bucket
    worst = sorted(arm_by_type.items(),
                   key=lambda kv: kv[1]["acc"])[:3]
    if worst:
        interp.append(
            "Weakest arm_kinds buckets: " +
            ", ".join(f"{k}={v['acc']:.0%} ({v['n']})"
                      for k, v in worst)
        )

    out = {
        "generated_by": "scripts/suite2_diag_d2_split_analysis.py",
        "source": str(D2_RESULTS),
        "n_targets": len(results),
        "split_by_n_atoms": split_natoms,
        "cardinality_collapse": collapse_stats,
        "collapsed_ids": collapsed_ids,
        "arm_kinds_by_claim_type": arm_by_type,
        "arm_kinds_misses_by_type": arm_miss_by_type,
        "interpretation": interp,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False))

    # --- Console summary ---
    print("=== D2 split analysis ===\n")
    print("A. Per-slot accuracy by n_atoms:")
    print(f"  {'slot':<22} {'n_atoms=1':>14} {'n_atoms>1':>14}")
    for slot in SLOT_KEYS:
        a1 = split_natoms["n1"].get(slot, {})
        ag = split_natoms["n_gt1"].get(slot, {})
        s1 = f"{a1.get('acc', 0):.0%} ({a1.get('n', 0)})"
        sg = f"{ag.get('acc', 0):.0%} ({ag.get('n', 0)})"
        print(f"  {slot:<22} {s1:>14} {sg:>14}")

    print(f"\nB. Cardinality: {collapse_stats}")
    if collapsed_ids:
        print(f"   Collapsed ids: {collapsed_ids}")

    print("\nC. Arm_kinds by claim type:")
    for ctype, stats in sorted(arm_by_type.items(),
                                key=lambda kv: -kv[1]["n"]):
        print(f"  {ctype:<26} acc={stats['acc']:.0%} "
              f"(n={stats['n']}, misses={stats['misses']})")

    print("\nD. Interpretation:")
    for line in interp:
        print(f"  - {line}")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
