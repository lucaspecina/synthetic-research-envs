"""Delta analysis: v3 (baseline) vs v4 (post Task #3.5 Recipe E+G) Suite 2 dump.

Internal variable names still say `v2`/`v3` (verbatim from the v2_v3 script)
but the labels "v3" and "v4" below refer to the loaded payloads.

Compares per-target bucket transitions and produces a summary of:
  - Targets that improved (e.g. stage1_fail -> full_pass).
  - Targets that regressed (e.g. full_pass -> verdict_wrong).
  - Unchanged buckets.
  - Abstention honesty delta (lucky fallback -> deliberate).

Reads:
  research/synthesis/compiler_baseline_full_dump_v4.json
  research/synthesis/compiler_baseline_full_dump_v4.json

Writes:
  research/synthesis/compiler_baseline_delta_v3_v4.json
  research/synthesis/compiler_baseline_delta_v3_v4.md (human-readable)
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

V2_PATH = Path("research/synthesis/compiler_baseline_full_dump_v3.json")
V3_PATH = Path("research/synthesis/compiler_baseline_full_dump_v4.json")
OUT_JSON = Path("research/synthesis/compiler_baseline_delta_v3_v4.json")
OUT_MD = Path("research/synthesis/compiler_baseline_delta_v3_v4.md")

BUCKET_ORDER = [
    "full_pass", "adjust_swap", "real_struct_err", "verdict_wrong", "stage1_fail",
]


def _rank(bucket: str) -> int:
    try:
        return BUCKET_ORDER.index(bucket)
    except ValueError:
        return len(BUCKET_ORDER)


def _load(path: Path) -> dict[str, dict]:
    entries = json.loads(path.read_text(encoding="utf-8"))
    return {e["id"]: e for e in entries}


def main() -> None:
    v2 = _load(V2_PATH)
    v3 = _load(V3_PATH)

    all_ids = sorted(set(v2) | set(v3))

    transitions: list[dict] = []
    for eid in all_ids:
        v2e = v2.get(eid)
        v3e = v3.get(eid)
        if v2e is None or v3e is None:
            continue
        b2, b3 = v2e["category"], v3e["category"]
        row = {
            "id": eid,
            "claim": v2e.get("claim"),
            "gold_status": v2e.get("gold_status"),
            "fact_id": v2e.get("fact_id"),
            "v2_bucket": b2,
            "v3_bucket": b3,
            "delta": "improved" if _rank(b3) < _rank(b2)
                    else ("regressed" if _rank(b3) > _rank(b2) else "same"),
            "v2_deliberate_abstention": v2e.get("deliberate_abstention"),
            "v3_deliberate_abstention": v3e.get("deliberate_abstention"),
        }
        transitions.append(row)

    n = len(transitions)
    improved = [t for t in transitions if t["delta"] == "improved"]
    regressed = [t for t in transitions if t["delta"] == "regressed"]
    same = [t for t in transitions if t["delta"] == "same"]

    c2 = Counter(t["v2_bucket"] for t in transitions)
    c3 = Counter(t["v3_bucket"] for t in transitions)

    strict_v2 = c2.get("full_pass", 0)
    strict_v3 = c3.get("full_pass", 0)
    eff_v2 = c2.get("full_pass", 0) + c2.get("adjust_swap", 0)
    eff_v3 = c3.get("full_pass", 0) + c3.get("adjust_swap", 0)

    # Honesty metric delta
    gold_abs_ids = [t["id"] for t in transitions if t["gold_status"] == "abstain"]

    def _honesty_count(entries_by_id: dict[str, dict], ids: list[str]) -> dict:
        stage1_ok = 0
        deliberate = 0
        fallback = 0
        for eid in ids:
            e = entries_by_id[eid]
            if e.get("stage1_ok"):
                stage1_ok += 1
                if e.get("deliberate_abstention"):
                    deliberate += 1
                else:
                    fallback += 1
        return {"stage1_ok": stage1_ok, "deliberate": deliberate, "fallback": fallback}

    v2_honesty = _honesty_count(v2, gold_abs_ids)
    v3_honesty = _honesty_count(v3, gold_abs_ids)

    payload = {
        "n_targets": n,
        "bucket_counts_v2": dict(c2),
        "bucket_counts_v3": dict(c3),
        "strict_full_pass_rate_v2": strict_v2 / n if n else 0,
        "strict_full_pass_rate_v3": strict_v3 / n if n else 0,
        "effective_pass_rate_v2": eff_v2 / n if n else 0,
        "effective_pass_rate_v3": eff_v3 / n if n else 0,
        "improved": improved,
        "regressed": regressed,
        "same_count": len(same),
        "gold_abstain": {
            "ids": gold_abs_ids,
            "v2": v2_honesty,
            "v3": v3_honesty,
        },
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Markdown report
    lines: list[str] = []
    lines.append("# Suite 2 Compiler Baseline Delta — v3 vs v4")
    lines.append("")
    lines.append(f"Targets compared: {n}")
    lines.append("")
    lines.append("## Pass rates")
    lines.append("")
    lines.append("| metric | v3 | v4 | Delta (pp) |")
    lines.append("|---|---|---|---|")
    lines.append(
        f"| strict_full_pass_rate | {strict_v2}/{n} ({strict_v2/n*100:.1f}%) | "
        f"{strict_v3}/{n} ({strict_v3/n*100:.1f}%) | "
        f"{(strict_v3 - strict_v2) / n * 100:+.1f} |"
    )
    lines.append(
        f"| effective_pass_rate | {eff_v2}/{n} ({eff_v2/n*100:.1f}%) | "
        f"{eff_v3}/{n} ({eff_v3/n*100:.1f}%) | "
        f"{(eff_v3 - eff_v2) / n * 100:+.1f} |"
    )
    lines.append("")
    lines.append("## Bucket distribution")
    lines.append("")
    lines.append("| bucket | v3 | v4 | Delta |")
    lines.append("|---|---|---|---|")
    for b in BUCKET_ORDER:
        v2c, v3c = c2.get(b, 0), c3.get(b, 0)
        lines.append(f"| {b} | {v2c} | {v3c} | {v3c - v2c:+d} |")
    lines.append("")
    lines.append(f"## Transitions: improved={len(improved)}, regressed={len(regressed)}, same={len(same)}")
    lines.append("")
    if improved:
        lines.append("### Improved")
        lines.append("")
        lines.append("| id | v3 | v4 | claim |")
        lines.append("|---|---|---|---|")
        for t in improved:
            lines.append(
                f"| {t['id']} | {t['v2_bucket']} | {t['v3_bucket']} | "
                f"{(t['claim'] or '')[:80]} |"
            )
        lines.append("")
    if regressed:
        lines.append("### Regressed")
        lines.append("")
        lines.append("| id | v3 | v4 | claim |")
        lines.append("|---|---|---|---|")
        for t in regressed:
            lines.append(
                f"| {t['id']} | {t['v2_bucket']} | {t['v3_bucket']} | "
                f"{(t['claim'] or '')[:80]} |"
            )
        lines.append("")
    lines.append("## Abstention honesty (gold_status='abstain')")
    lines.append("")
    lines.append(f"IDs: {', '.join(gold_abs_ids)}")
    lines.append("")
    lines.append("| metric | v3 | v4 |")
    lines.append("|---|---|---|")
    lines.append(
        f"| stage1_ok (compiler correctly abstained) | "
        f"{v2_honesty['stage1_ok']}/{len(gold_abs_ids)} | "
        f"{v3_honesty['stage1_ok']}/{len(gold_abs_ids)} |"
    )
    lines.append(
        f"| deliberate (honest abstention) | "
        f"{v2_honesty['deliberate']} | {v3_honesty['deliberate']} |"
    )
    lines.append(
        f"| fallback (lucky — crash/parse fail) | "
        f"{v2_honesty['fallback']} | {v3_honesty['fallback']} |"
    )
    lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    print()
    print(f"strict: {strict_v2}/{n} -> {strict_v3}/{n}  ({(strict_v3 - strict_v2)/n*100:+.1f}pp)")
    print(f"eff:    {eff_v2}/{n} -> {eff_v3}/{n}  ({(eff_v3 - eff_v2)/n*100:+.1f}pp)")
    print(f"improved: {len(improved)}  regressed: {len(regressed)}  same: {len(same)}")


if __name__ == "__main__":
    main()
