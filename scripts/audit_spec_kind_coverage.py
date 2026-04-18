"""Spec-kind coverage histogram for Suite 2 baseline v2.

No LLM. Pure structural analysis of compiler_specs vs gold_specs:
- distribution of measurement_kind / comparison_kind / assertion_kind / arm_kind
- joint distributions (measurement x assertion, query x measurement)
- per-world and per-category breakdowns
- mode collapse detection

Output:
    JSON with histograms + markdown-ready tables.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _spec_tuples(spec: dict[str, Any]) -> dict[str, Any]:
    """Extract kind tuples from a single spec."""
    arms = spec.get("arms") or []
    m = spec.get("measurement") or {}
    c = spec.get("comparison") or {}
    a = spec.get("assertion") or {}
    return {
        "arm_kinds": [str((arm.get("kind") or "?")).lower() for arm in arms],
        "n_arms": len(arms),
        "measurement_kind": str(m.get("kind") or "?").lower(),
        "comparison_kind": str(c.get("kind") or "?").lower(),
        "assertion_kind": str(a.get("kind") or "?").lower(),
    }


def _collect(entries: list[dict[str, Any]], specs_key: str) -> dict[str, Any]:
    histograms = {
        "arm_kind": Counter(),
        "n_arms_per_spec": Counter(),
        "measurement_kind": Counter(),
        "comparison_kind": Counter(),
        "assertion_kind": Counter(),
        "measurement_x_assertion": Counter(),
        "measurement_x_n_arms": Counter(),
        "arm_kind_x_measurement": Counter(),
        "specs_per_entry": Counter(),
    }
    # Per-world histograms (key = world)
    per_world: dict[str, dict[str, Counter]] = defaultdict(
        lambda: {
            "measurement_kind": Counter(),
            "assertion_kind": Counter(),
            "arm_kind": Counter(),
        }
    )
    # Per-category histograms (key = category)
    per_category: dict[str, dict[str, Counter]] = defaultdict(
        lambda: {
            "measurement_kind": Counter(),
            "assertion_kind": Counter(),
            "arm_kind": Counter(),
        }
    )

    total_specs = 0
    total_arms = 0

    for e in entries:
        world = e.get("world") or "unknown"
        cat = e.get("category") or "unknown"
        specs = e.get(specs_key) or []
        histograms["specs_per_entry"][len(specs)] += 1

        for spec in specs:
            total_specs += 1
            t = _spec_tuples(spec)
            histograms["measurement_kind"][t["measurement_kind"]] += 1
            histograms["comparison_kind"][t["comparison_kind"]] += 1
            histograms["assertion_kind"][t["assertion_kind"]] += 1
            histograms["n_arms_per_spec"][t["n_arms"]] += 1
            histograms["measurement_x_assertion"][
                (t["measurement_kind"], t["assertion_kind"])
            ] += 1
            histograms["measurement_x_n_arms"][
                (t["measurement_kind"], t["n_arms"])
            ] += 1

            per_world[world]["measurement_kind"][t["measurement_kind"]] += 1
            per_world[world]["assertion_kind"][t["assertion_kind"]] += 1
            per_category[cat]["measurement_kind"][t["measurement_kind"]] += 1
            per_category[cat]["assertion_kind"][t["assertion_kind"]] += 1

            for ak in t["arm_kinds"]:
                total_arms += 1
                histograms["arm_kind"][ak] += 1
                per_world[world]["arm_kind"][ak] += 1
                per_category[cat]["arm_kind"][ak] += 1
                histograms["arm_kind_x_measurement"][(ak, t["measurement_kind"])] += 1

    # Cast Counters to dicts for JSON serialization
    def _dictify(obj):
        if isinstance(obj, (Counter, dict)):
            return {
                (str(k) if not isinstance(k, tuple) else " | ".join(str(x) for x in k)):
                _dictify(v) for k, v in obj.items()
            }
        return obj

    return {
        "total_entries": len(entries),
        "total_specs": total_specs,
        "total_arms": total_arms,
        "histograms": {k: _dictify(v) for k, v in histograms.items()},
        "per_world": {w: {k: _dictify(v) for k, v in d.items()} for w, d in per_world.items()},
        "per_category": {
            c: {k: _dictify(v) for k, v in d.items()} for c, d in per_category.items()
        },
    }


def _print_table(title: str, hist: dict[str, int], total: int | None = None) -> None:
    if not hist:
        print(f"\n{title}: (empty)")
        return
    print(f"\n{title}:")
    items = sorted(hist.items(), key=lambda x: -x[1])
    for k, n in items:
        if total:
            pct = 100 * n / total
            print(f"  {str(k):35s}  {n:5d}  ({pct:.1f}%)")
        else:
            print(f"  {str(k):35s}  {n:5d}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--baseline",
        default="research/synthesis/compiler_baseline_full_dump_v2.json",
    )
    parser.add_argument("--out", default="./spec_kind_coverage_audit.json")
    args = parser.parse_args()

    baseline_path = Path(args.baseline).resolve()
    out_path = Path(args.out).resolve()

    with baseline_path.open(encoding="utf-8") as f:
        entries = json.load(f)
    print(f"Loaded {len(entries)} entries from {baseline_path}")

    compiler_cov = _collect(entries, "compiler_specs")
    gold_cov = _collect(entries, "gold_specs")

    out = {
        "meta": {
            "baseline": str(baseline_path),
            "total_entries": len(entries),
        },
        "compiler_specs": compiler_cov,
        "gold_specs": gold_cov,
    }
    out_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nWrote: {out_path}")

    # Pretty-print key tables
    print("\n" + "=" * 60)
    print("COMPILER SPECS (what LLM produces)")
    print("=" * 60)
    c = compiler_cov
    print(f"  total_specs={c['total_specs']}  total_arms={c['total_arms']}")
    _print_table("  arm_kind", c["histograms"]["arm_kind"], c["total_arms"])
    _print_table("  measurement_kind", c["histograms"]["measurement_kind"], c["total_specs"])
    _print_table("  comparison_kind", c["histograms"]["comparison_kind"], c["total_specs"])
    _print_table("  assertion_kind", c["histograms"]["assertion_kind"], c["total_specs"])
    _print_table("  n_arms_per_spec", c["histograms"]["n_arms_per_spec"], c["total_specs"])
    _print_table("  specs_per_entry", c["histograms"]["specs_per_entry"], c["total_entries"])

    print("\n" + "=" * 60)
    print("GOLD SPECS (what should have been)")
    print("=" * 60)
    g = gold_cov
    print(f"  total_specs={g['total_specs']}  total_arms={g['total_arms']}")
    _print_table("  arm_kind", g["histograms"]["arm_kind"], g["total_arms"])
    _print_table("  measurement_kind", g["histograms"]["measurement_kind"], g["total_specs"])
    _print_table("  comparison_kind", g["histograms"]["comparison_kind"], g["total_specs"])
    _print_table("  assertion_kind", g["histograms"]["assertion_kind"], g["total_specs"])
    _print_table("  n_arms_per_spec", g["histograms"]["n_arms_per_spec"], g["total_specs"])

    # Compute delta: what kinds does gold use that compiler doesn't?
    print("\n" + "=" * 60)
    print("MODE COLLAPSE DETECTION (kinds in gold but not compiler)")
    print("=" * 60)
    for field in ("measurement_kind", "comparison_kind", "assertion_kind", "arm_kind"):
        g_keys = set(g["histograms"][field].keys())
        c_keys = set(c["histograms"][field].keys())
        missing_in_compiler = g_keys - c_keys
        missing_in_gold = c_keys - g_keys
        if missing_in_compiler or missing_in_gold:
            print(f"\n  {field}:")
            if missing_in_compiler:
                print(f"    gold-only (compiler never produces): {sorted(missing_in_compiler)}")
            if missing_in_gold:
                print(f"    compiler-only (gold never uses): {sorted(missing_in_gold)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
