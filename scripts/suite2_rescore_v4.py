"""Re-score v4 dump against updated gold (Task #5 H6 gold hygiene).

Task #5 H6 fix: W2_F02_GOLDS changed
  MeasurementKind.PARTIAL_CORRELATION (cond_set=()) -> CORRELATION
  structural_contract.required_measurement_kind
    "partial_correlation" -> "correlation"

This is an objective benchmark correction: partial_correlation with an
empty conditioning set is mathematically identical to correlation. The
compiler was producing `correlation`, which the old gold rejected at
stage 2.

No LLM re-run needed. We re-run stage 2 / stage 3 checks against the
already-compiled v4 specs.

Outputs:
  - research/synthesis/compiler_baseline_full_dump_v5.json
  - research/synthesis/compiler_baseline_full_dump_v5.jsonl
  - research/synthesis/compiler_baseline_failures_v5.json

v5 differs from v4 only in categorization of W2_F02_s0/s1/s2 (and any
other affected target).
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv

load_dotenv()

from sreg.models.open_investigation import AtomicSpec
from tests.eval.suite2_translation.gold_targets import ALL_GOLD_TARGETS

V4_PATH = Path("research/synthesis/compiler_baseline_full_dump_v4.jsonl")
OUT_JSON = Path("research/synthesis/compiler_baseline_full_dump_v5.json")
OUT_JSONL = Path("research/synthesis/compiler_baseline_full_dump_v5.jsonl")
OUT_FAIL = Path("research/synthesis/compiler_baseline_failures_v5.json")

_ARM_KIND_ERROR_RE = re.compile(
    r"spec\[\d+\] arm_kinds: (\[.*?\]) not subset of (\[.*?\])"
)


def _gold_target_id(gt) -> str:
    return f"{gt.fact_id}_s{gt.surface_form_index}"


GOLD_BY_ID = {_gold_target_id(gt): gt for gt in ALL_GOLD_TARGETS}


def rebuild_specs(entry: dict) -> list[AtomicSpec]:
    specs_dicts = entry.get("compiler_specs") or []
    return [AtomicSpec.model_validate(d) for d in specs_dicts]


def check_stage2_from_entry(gt, entry: dict) -> dict:
    """Redo stage 2 using the entry's stored specs + updated gold contract."""
    if gt.status == "abstain" or not entry.get("compiler_compiled"):
        return {"pass": True, "reason": "abstain (no contract to check)"}

    sc = gt.structural_contract
    if sc is None:
        return {"pass": True, "reason": "no contract defined"}

    try:
        specs = rebuild_specs(entry)
    except Exception as e:
        return {"pass": False, "errors": [f"spec rebuild failed: {e}"]}

    errors: list[str] = []

    if isinstance(sc.n_atoms, int):
        if len(specs) != sc.n_atoms:
            errors.append(f"n_atoms: expected {sc.n_atoms}, got {len(specs)}")
    elif isinstance(sc.n_atoms, tuple):
        lo, hi = sc.n_atoms
        if not (lo <= len(specs) <= hi):
            errors.append(f"n_atoms: expected {lo}-{hi}, got {len(specs)}")

    for i, spec in enumerate(specs):
        arm_kinds = {a.kind.value for a in spec.arms}
        if not arm_kinds.issubset(sc.allowed_arm_kinds):
            errors.append(
                f"spec[{i}] arm_kinds: {sorted(arm_kinds)} not subset of "
                f"{sorted(sc.allowed_arm_kinds)}"
            )
        if spec.measurement.kind.value != sc.required_measurement_kind:
            errors.append(
                f"spec[{i}] measurement: {spec.measurement.kind.value} "
                f"!= {sc.required_measurement_kind}"
            )
        if spec.comparison.kind.value != sc.required_comparison_kind:
            errors.append(
                f"spec[{i}] comparison: {spec.comparison.kind.value} "
                f"!= {sc.required_comparison_kind}"
            )
        if spec.assertion.kind.value != sc.required_assertion_polarity:
            errors.append(
                f"spec[{i}] assertion: {spec.assertion.kind.value} "
                f"!= {sc.required_assertion_polarity}"
            )

    if sc.required_role_vars and specs:
        all_vars = set()
        for spec in specs:
            for arm in spec.arms:
                all_vars.update(arm.values.keys())
                all_vars.update(arm.condition_on.keys())
            if spec.measurement.target:
                t = spec.measurement.target
                if isinstance(t, str):
                    all_vars.add(t)
                else:
                    all_vars.update(t)
            for attr in ("lhs", "rhs", "treatment", "outcome"):
                v = getattr(spec.measurement, attr, None)
                if v:
                    all_vars.add(v)
        for role, var in sc.required_role_vars.items():
            if var not in all_vars:
                errors.append(f"role_var '{role}={var}' not found in specs")

    return {"pass": len(errors) == 0, "errors": errors}


def is_adjust_swap(stage2_errors: list[str]) -> bool:
    """Mirrors suite2_full_dump_v4.py exactly.

    Conservative: require (a) every error is an arm_kind error, and (b) every
    arm_kind error is exactly `['adjust']` vs a contract set that contains
    `intervene` (possibly with other kinds). If anything else is off —
    measurement / comparison / assertion / role_var / n_atoms / other arm_kind —
    it's a real structural error, not adjust_swap.
    """
    if not stage2_errors:
        return False
    for err in stage2_errors:
        m = _ARM_KIND_ERROR_RE.search(err)
        if not m:
            return False
        got_literal, allowed_literal = m.group(1), m.group(2)
        try:
            got = set(json.loads(got_literal.replace("'", '"')))
            allowed = set(json.loads(allowed_literal.replace("'", '"')))
        except Exception:
            return False
        if got != {"adjust"}:
            return False
        if "intervene" not in allowed:
            return False
    return True


def bucket_of(s1_ok: bool, s2: dict, s3: dict) -> str:
    if not s1_ok:
        return "stage1_fail"
    if not s3.get("pass"):
        return "verdict_wrong"
    if s2.get("pass"):
        return "full_pass"
    errors = s2.get("errors") or []
    if is_adjust_swap(errors):
        return "adjust_swap"
    return "real_struct_err"


def main() -> None:
    entries = [
        json.loads(line)
        for line in V4_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    out_entries = []
    changed = []
    for entry in entries:
        eid = entry["id"]
        gt = GOLD_BY_ID.get(eid)
        if gt is None:
            out_entries.append(entry)
            continue

        new_s2 = check_stage2_from_entry(gt, entry)
        s1_ok = entry.get("stage1_ok", False)
        s3 = entry.get("stage3", {})
        new_bucket = bucket_of(s1_ok, new_s2, s3)

        new_entry = dict(entry)
        if new_bucket != entry.get("category") or new_s2 != entry.get("stage2"):
            new_entry["stage2"] = new_s2
            new_entry["category"] = new_bucket
            changed.append({
                "id": eid,
                "old_category": entry.get("category"),
                "new_category": new_bucket,
                "old_stage2_errors": entry.get("stage2", {}).get("errors", []),
                "new_stage2_errors": new_s2.get("errors", []),
            })
        out_entries.append(new_entry)

    OUT_JSON.write_text(json.dumps(out_entries, indent=2), encoding="utf-8")
    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for e in out_entries:
            f.write(json.dumps(e) + "\n")

    fails = [e for e in out_entries if e["category"] not in ("full_pass", "adjust_swap")]
    OUT_FAIL.write_text(json.dumps(fails, indent=2), encoding="utf-8")

    counts = Counter(e["category"] for e in out_entries)
    n = len(out_entries)

    print("=" * 60)
    print("v5 rescore summary (Task #5 H6 gold hygiene)")
    print("=" * 60)
    for cat in ("full_pass", "adjust_swap", "real_struct_err", "verdict_wrong", "stage1_fail"):
        c = counts.get(cat, 0)
        print(f"  {cat:20s} {c:3d}  ({c/n*100:4.1f}%)")
    effective = counts.get("full_pass", 0) + counts.get("adjust_swap", 0)
    strict = counts.get("full_pass", 0)
    print()
    print(f"  strict_full_pass_rate  = {strict}/{n} = {strict/n*100:.1f}%")
    print(f"  effective_pass_rate    = {effective}/{n} = {effective/n*100:.1f}%")
    print()
    print(f"Changed categorizations: {len(changed)}")
    for c in changed:
        print(f"  {c['id']}: {c['old_category']} -> {c['new_category']}")
    print()
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_JSONL}")
    print(f"Wrote {OUT_FAIL}  ({len(fails)} entries)")


if __name__ == "__main__":
    main()
