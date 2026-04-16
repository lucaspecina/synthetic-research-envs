"""Closure item (5) of Suite 2 diagnostic battery — per-family × per-slot D2.

D2 results ya tienen `per_family_accuracy` como agregado (matches/total
sumado sobre slots). Esto oculta qué slot falla dentro de cada family.
Surface la vista per-family × per-slot para input directo al diseño
de exemplars I-026.

Usa:
- `research/synthesis/suite2_diag_d2_results.json` (per-id, per-slot verdicts)
- `research/synthesis/compiler_baseline_full_dump_v2.json` (bucket por family)

Produce:
- Tabla per-family × per-slot match rate
- Marcador del "weakest slot" por family (para priorizar exemplars)
- Anotación con baseline bucket mix por family (full_pass / verdict_wrong / ...)

Markdown-ready para splicear en strategy doc §7.10.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


BASELINE = Path("research/synthesis/compiler_baseline_full_dump_v2.json")
D2 = Path("research/synthesis/suite2_diag_d2_results.json")
OUT = Path("research/synthesis/suite2_diag_d2_per_family_slots.json")
OUT_MD = Path("research/synthesis/suite2_diag_d2_per_family_slots.md")

SLOT_KEYS = [
    "status",
    "n_atoms",
    "arm_kinds",
    "role_vars",
    "measurement_kind",
    "comparison_kind",
    "assertion_polarity",
]


def slot_hit(verdict: dict, slot: str) -> bool | None:
    entry = verdict.get("slots", {}).get(slot)
    if entry is None:
        return None
    match = entry.get("match")
    if match is None:
        return None
    return bool(match)


def main() -> None:
    baseline = json.loads(BASELINE.read_text())
    d2 = json.loads(D2.read_text())
    d2_results = d2["results"]

    b_by_id = {b["id"]: b for b in baseline}

    # family -> slot -> list[bool]
    fam_slot: dict[str, dict[str, list[bool]]] = defaultdict(
        lambda: defaultdict(list))
    fam_bucket: dict[str, Counter] = defaultdict(Counter)
    fam_targets: dict[str, int] = defaultdict(int)

    for r in d2_results:
        family = r.get("family")
        if family is None:
            continue
        fam_targets[family] += 1
        bucket = b_by_id.get(r["id"], {}).get("category", "unknown")
        fam_bucket[family][bucket] += 1
        for slot in SLOT_KEYS:
            hit = slot_hit(r["verdict"], slot)
            if hit is not None:
                fam_slot[family][slot].append(hit)

    def rate(lst: list[bool]) -> float | None:
        if not lst:
            return None
        return round(sum(lst) / len(lst), 3)

    per_family: dict[str, dict] = {}
    for family, slots in fam_slot.items():
        slot_accs = {s: rate(lst) for s, lst in slots.items()}
        # Weakest slot (ignore None and status which dominates)
        scored = [(s, a) for s, a in slot_accs.items()
                  if a is not None and s != "status"]
        scored.sort(key=lambda kv: kv[1])
        weakest = scored[0] if scored else None
        top2_weak = scored[:2] if scored else []
        # bucket_mix failure rate (non-full_pass / total)
        buckets = fam_bucket[family]
        total = sum(buckets.values())
        n_fail = total - buckets.get("full_pass", 0)
        fail_rate = round(n_fail / total, 3) if total else 0.0
        per_family[family] = {
            "n_targets": fam_targets[family],
            "slot_acc": slot_accs,
            "weakest_non_status": weakest,
            "top2_weak_slots": top2_weak,
            "bucket_mix": dict(buckets),
            "bucket_failure_rate": fail_rate,
        }

    # Sort families by: worst weakest_slot first (prioritize for exemplars)
    ordered = sorted(
        per_family.items(),
        key=lambda kv: (kv[1]["weakest_non_status"][1]
                         if kv[1]["weakest_non_status"] else 1.0,
                         -kv[1]["n_targets"])
    )

    out = {
        "generated_by": "scripts/suite2_diag_d2_per_family_slots.py",
        "sources": {"baseline": str(BASELINE), "d2": str(D2)},
        "per_family": per_family,
        "ordered_by_worst_slot": [k for k, _ in ordered],
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False))

    # --- Console table ---
    print("=== D2 per-family × per-slot ===\n")
    header = (
        f"{'family':<8} {'n':>3} "
        f"{'stat':>5} {'n_at':>5} {'arm_k':>6} {'role':>5} "
        f"{'meas':>5} {'comp':>5} {'asrt':>5} | "
        f"{'weakest':<10} {'buckets'}"
    )
    print(header)
    print("-" * len(header))

    def fmt(v: float | None) -> str:
        return "-" if v is None else f"{int(v * 100)}%"

    for family, info in ordered:
        sa = info["slot_acc"]
        weak = info["weakest_non_status"]
        weak_str = f"{weak[0]}:{int(weak[1] * 100)}%" if weak else "-"
        buckets = info["bucket_mix"]
        bk_str = ",".join(f"{k[:4]}={v}" for k, v in
                           sorted(buckets.items(), key=lambda kv: -kv[1]))
        row = (
            f"{family:<8} {info['n_targets']:>3} "
            f"{fmt(sa.get('status')):>5} {fmt(sa.get('n_atoms')):>5} "
            f"{fmt(sa.get('arm_kinds')):>6} {fmt(sa.get('role_vars')):>5} "
            f"{fmt(sa.get('measurement_kind')):>5} "
            f"{fmt(sa.get('comparison_kind')):>5} "
            f"{fmt(sa.get('assertion_polarity')):>5} | "
            f"{weak_str:<10} {bk_str}"
        )
        print(row)

    # --- Markdown output ---
    md_lines = [
        "### D2 per-family × per-slot accuracy\n",
        "| family | n | status | n_atoms | arm_kinds | role_vars | "
        "meas_kind | comp_kind | assert | top-2 weak | fail rate | bucket mix |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for family, info in ordered:
        sa = info["slot_acc"]
        top2 = info["top2_weak_slots"]
        top2_str = ", ".join(
            f"`{s}` {int(a * 100)}%" for s, a in top2) if top2 else "—"
        buckets = info["bucket_mix"]
        bk_str = ", ".join(f"{k}={v}" for k, v in
                            sorted(buckets.items(), key=lambda kv: -kv[1]))
        fr = info["bucket_failure_rate"]
        md_lines.append(
            f"| {family} | {info['n_targets']} | "
            f"{fmt(sa.get('status'))} | {fmt(sa.get('n_atoms'))} | "
            f"**{fmt(sa.get('arm_kinds'))}** | "
            f"{fmt(sa.get('role_vars'))} | "
            f"{fmt(sa.get('measurement_kind'))} | "
            f"{fmt(sa.get('comparison_kind'))} | "
            f"{fmt(sa.get('assertion_polarity'))} | "
            f"{top2_str} | {int(fr * 100)}% | {bk_str} |"
        )
    OUT_MD.write_text("\n".join(md_lines))

    print(f"\nWrote {OUT}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
