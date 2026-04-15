"""Suite 2 diagnostic — split stage1_fail into decision vs crash (I-027 item 7).

Re-bucketing OFFLINE sobre compiler_baseline_full_dump_v2.json. Zero LLM calls.

Modos de falla dentro de `stage1_fail`:
- `decision_fail`: compiler_compiled=True pero gold_status=abstain (o inversa).
  El compiler tomó una decisión compile/abstain equivocada. Modo original del bucket.
- `crash`: compiler_compiled=False pero gold_status=compile. El compiler no
  produjo specs cuando debía — runtime/schema crash (ej. I-028).

Output:
- research/synthesis/suite2_stage1_split.json — resumen con IDs por sub-modo.
- Print en consola.

El dump v2 se deja intacto; este doc es una vista derivada.
"""
from __future__ import annotations

import json
from pathlib import Path


def classify_stage1(entry: dict) -> str:
    compiled = bool(entry.get("compiler_compiled"))
    gold_status = entry.get("gold_status")
    if compiled and gold_status == "abstain":
        return "decision_fail"
    if compiled and gold_status == "compile":
        # Shouldn't happen for stage1_fail bucket, but guard.
        return "decision_fail"
    if not compiled and gold_status == "compile":
        return "crash"
    if not compiled and gold_status == "abstain":
        return "decision_fail"  # should have compiled abstain_reason, fell through
    return "unknown"


def main() -> None:
    in_path = Path("research/synthesis/compiler_baseline_full_dump_v2.json")
    entries = json.loads(in_path.read_text(encoding="utf-8"))

    stage1_entries = [e for e in entries if e["category"] == "stage1_fail"]

    decision_fails: list[dict] = []
    crashes: list[dict] = []
    unknown: list[dict] = []

    for e in stage1_entries:
        mode = classify_stage1(e)
        row = {
            "id": e["id"],
            "fact_id": e["fact_id"],
            "world": e["world"],
            "gold_status": e["gold_status"],
            "compiler_compiled": e["compiler_compiled"],
            "compiler_abstain_reason": e.get("compiler_abstain_reason"),
            "difficulty": e.get("difficulty"),
        }
        if mode == "decision_fail":
            decision_fails.append(row)
        elif mode == "crash":
            crashes.append(row)
        else:
            unknown.append(row)

    summary = {
        "generated_by": "scripts/suite2_diag_stage1_split.py",
        "source": str(in_path),
        "stage1_fail_total": len(stage1_entries),
        "decision_fail": {
            "count": len(decision_fails),
            "definition": "compiler_compiled did not match gold_status (most commonly: compiled when gold said abstain)",
            "entries": decision_fails,
        },
        "crash": {
            "count": len(crashes),
            "definition": "compiler_compiled=False but gold_status=compile; runtime/schema failure",
            "entries": crashes,
            "cross_ref": "I-028 (sweep_values as list inside arm.values)",
        },
        "unknown": {
            "count": len(unknown),
            "entries": unknown,
        },
        "interpretation": {
            "before_split": f"stage1_fail conflates {len(stage1_entries)} entries of two different failure modes.",
            "after_split": f"{len(decision_fails)} decision errors + {len(crashes)} runtime crashes. Downstream analyses should treat them separately.",
        },
    }

    out_path = Path("research/synthesis/suite2_stage1_split.json")
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("=" * 60)
    print("Suite 2 — stage1_fail sub-mode split")
    print("=" * 60)
    print(f"Total stage1_fail: {len(stage1_entries)}")
    print()
    print(f"decision_fail ({len(decision_fails)}):")
    for r in decision_fails:
        print(f"  {r['id']:15s} gold={r['gold_status']:8s} compiled={r['compiler_compiled']}")
    print()
    print(f"crash ({len(crashes)}):")
    for r in crashes:
        print(f"  {r['id']:15s} gold={r['gold_status']:8s} compiled={r['compiler_compiled']}")
    if unknown:
        print()
        print(f"unknown ({len(unknown)}):")
        for r in unknown:
            print(f"  {r['id']:15s}")
    print()
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
