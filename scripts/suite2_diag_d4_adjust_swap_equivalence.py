"""Suite 2 diagnostic D4 — adjust_swap equivalence under the current verifier.

Offline check (zero LLM calls) sobre los 10 `adjust_swap` entries en
`compiler_baseline_full_dump_v2.json`. Para cada entry:

1. Reconstruir gold_spec y compiler_spec desde los dicts del dump.
2. Correr verify_atom de ambos contra el SCM del mundo.
3. Comparar 5 atributos (criterio Codex 2026-04-15):
   - mismo n_atoms
   - misma measurement.kind / comparison.kind / assertion.kind
   - mismo `solver_assertion_holds` por átomo
   - misma `ground_truth` escalar dentro de tol (0.05)
4. Marcar como 'equivalent' si los 5 criterios se cumplen. 'structural_diff' si
   la estructura core cambia (medida/compare/assert). 'numerical_diff' si solo
   difiere ground_truth. 'arm_only' se descarta explícitamente porque la idea
   es que la ÚNICA diferencia sea arm kinds.

Output: research/synthesis/suite2_diag_d4_results.json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.getcwd())

from sreg.models.open_investigation import (
    Assertion,
    AssertionKind,
    AtomicSpec,
    Comparison,
    ComparisonKind,
    Measurement,
    MeasurementKind,
    QueryArm,
    QueryKind,
)
from sreg.solver.scm_solver import SCMSolver
from sreg.tools.oi_verifier import verify_atom

from tests.eval.suite2_translation.worlds import ALL_WORLDS

TOL = 0.05
N_MC = 50_000
SEED = 42


def spec_from_dict(d: dict) -> AtomicSpec:
    """Reverse of AtomicSpec.model_dump(mode='json')."""
    return AtomicSpec.model_validate(d)


def summarize_spec(s: AtomicSpec) -> dict:
    return {
        "n_atoms": 1,  # AtomicSpec is atomic by definition
        "arm_kinds": [a.kind.value for a in s.arms],
        "measurement": s.measurement.kind.value,
        "comparison": s.comparison.kind.value,
        "assertion": s.assertion.kind.value,
    }


def compare_verdicts(gold_verdict, compiler_verdict) -> dict:
    g_holds = bool(gold_verdict.solver_assertion_holds)
    c_holds = bool(compiler_verdict.solver_assertion_holds)
    g_gt = gold_verdict.ground_truth
    c_gt = compiler_verdict.ground_truth
    same_holds = g_holds == c_holds
    # ground_truth can be float or bool; normalize to float for comparison
    try:
        g_f = float(g_gt) if g_gt is not None else None
        c_f = float(c_gt) if c_gt is not None else None
        if g_f is None or c_f is None:
            gt_diff = None
            same_gt = g_f == c_f
        else:
            gt_diff = abs(g_f - c_f)
            same_gt = gt_diff <= TOL
    except (TypeError, ValueError):
        gt_diff = None
        same_gt = str(g_gt) == str(c_gt)
    return {
        "gold_holds": g_holds,
        "compiler_holds": c_holds,
        "same_holds": same_holds,
        "gold_ground_truth": g_gt if isinstance(g_gt, (int, float, bool)) else str(g_gt),
        "compiler_ground_truth": c_gt if isinstance(c_gt, (int, float, bool)) else str(c_gt),
        "gt_diff": gt_diff,
        "same_gt_within_tol": same_gt,
    }


def classify(gold_summary: dict, comp_summary: dict, verdict_cmp: dict) -> str:
    """Return one of: equivalent, structural_diff, numerical_diff, holds_diff."""
    if (
        gold_summary["measurement"] != comp_summary["measurement"]
        or gold_summary["comparison"] != comp_summary["comparison"]
        or gold_summary["assertion"] != comp_summary["assertion"]
    ):
        return "structural_diff"
    if not verdict_cmp["same_holds"]:
        return "holds_diff"
    if not verdict_cmp["same_gt_within_tol"]:
        return "numerical_diff"
    return "equivalent"


def main() -> None:
    dump_path = Path("research/synthesis/compiler_baseline_full_dump_v2.json")
    entries = json.loads(dump_path.read_text(encoding="utf-8"))

    adjust_swap_entries = [e for e in entries if e["category"] == "adjust_swap"]
    print(f"Processing {len(adjust_swap_entries)} adjust_swap entries")
    print("=" * 70)

    solver_cache: dict[str, tuple] = {}

    def get_world_solver(wk: str):
        if wk not in solver_cache:
            w = ALL_WORLDS[wk]
            solver_cache[wk] = (w, SCMSolver(w, n_mc=N_MC))
        return solver_cache[wk]

    results = []

    for entry in adjust_swap_entries:
        entry_id = entry["id"]
        world_key = entry["world"]
        world, solver = get_world_solver(world_key)

        gold_specs = entry.get("gold_specs", [])
        comp_specs = entry.get("compiler_specs", [])

        if len(gold_specs) != len(comp_specs):
            results.append({
                "id": entry_id,
                "classification": "atom_count_mismatch",
                "gold_n": len(gold_specs),
                "compiler_n": len(comp_specs),
            })
            print(f"[ATOM_COUNT] {entry_id}: gold={len(gold_specs)} compiler={len(comp_specs)}")
            continue

        per_atom = []
        for i, (g_dict, c_dict) in enumerate(zip(gold_specs, comp_specs)):
            try:
                g_spec = spec_from_dict(g_dict)
            except Exception as e:
                per_atom.append({"atom_idx": i, "error": f"gold reconstruct failed: {e}"})
                continue
            try:
                c_spec = spec_from_dict(c_dict)
            except Exception as e:
                per_atom.append({"atom_idx": i, "error": f"compiler reconstruct failed: {e}"})
                continue

            g_summary = summarize_spec(g_spec)
            c_summary = summarize_spec(c_spec)

            g_verdict = verify_atom(g_spec, world, solver, n_mc=N_MC, seed=SEED)
            c_verdict = verify_atom(c_spec, world, solver, n_mc=N_MC, seed=SEED)

            verdict_cmp = compare_verdicts(g_verdict, c_verdict)
            classification = classify(g_summary, c_summary, verdict_cmp)

            per_atom.append({
                "atom_idx": i,
                "gold_summary": g_summary,
                "compiler_summary": c_summary,
                "verdict_cmp": verdict_cmp,
                "classification": classification,
            })

        overall = "equivalent"
        reasons = []
        for a in per_atom:
            if "error" in a:
                overall = "error"
                reasons.append(f"atom{a['atom_idx']}: {a['error']}")
                continue
            if a["classification"] != "equivalent":
                overall = a["classification"]  # take first non-equiv
                reasons.append(f"atom{a['atom_idx']}: {a['classification']}")

        arm_kinds_differ = any(
            a.get("gold_summary", {}).get("arm_kinds")
            != a.get("compiler_summary", {}).get("arm_kinds")
            for a in per_atom
            if "gold_summary" in a
        )

        results.append({
            "id": entry_id,
            "world": world_key,
            "overall": overall,
            "arm_kinds_differ": arm_kinds_differ,
            "reasons": reasons,
            "per_atom": per_atom,
        })

        tag = "OK" if overall == "equivalent" else overall.upper()
        reason_str = f" [{', '.join(reasons)}]" if reasons else ""
        print(f"[{tag:16s}] {entry_id:15s} arm_kinds_differ={arm_kinds_differ}{reason_str}")

    # Aggregate
    counts: dict[str, int] = {}
    for r in results:
        counts[r["overall"]] = counts.get(r["overall"], 0) + 1

    equivalent_ids = [r["id"] for r in results if r["overall"] == "equivalent"]
    non_equivalent_ids = [r["id"] for r in results if r["overall"] != "equivalent"]

    print()
    print("=" * 70)
    print("D4 Summary")
    print("=" * 70)
    for cat in ("equivalent", "holds_diff", "numerical_diff", "structural_diff", "error", "atom_count_mismatch"):
        if counts.get(cat, 0) > 0:
            print(f"  {cat:22s}: {counts[cat]}")
    print()
    print(f"Equivalent under verifier semantics: {len(equivalent_ids)}/{len(results)}")
    if equivalent_ids:
        print(f"  IDs: {equivalent_ids}")
    if non_equivalent_ids:
        print(f"Non-equivalent IDs: {non_equivalent_ids}")

    # Interpretation
    n = len(results)
    eq = len(equivalent_ids)
    if eq == n:
        interp = (
            f"All {n} adjust_swap entries are equivalent under the current verifier "
            "semantics. Formalizing the equivalence in `alternative_atoms` would "
            f"reclassify them as strict_full_pass, raising strict_full_pass_rate "
            f"from 13% (7/55) to {(7+n)*100/55:.0f}% ({7+n}/55)."
        )
    else:
        interp = (
            f"Only {eq}/{n} adjust_swap entries are equivalent. The remaining "
            f"{n-eq} reveal hidden compiler errors previously masked by the "
            "adjust_swap label. They should be reclassified as real_struct_err."
        )

    summary = {
        "generated_by": "scripts/suite2_diag_d4_adjust_swap_equivalence.py",
        "source": str(dump_path),
        "criterion": {
            "n_atoms_match": True,
            "measurement_kind_match": True,
            "comparison_kind_match": True,
            "assertion_kind_match": True,
            "solver_assertion_holds_match": True,
            "ground_truth_within_tol": TOL,
            "scope_note": "Equivalence is under the CURRENT verifier semantics, not abstract causal equivalence.",
        },
        "counts": counts,
        "equivalent_ids": equivalent_ids,
        "non_equivalent_ids": non_equivalent_ids,
        "n_mc": N_MC,
        "seed": SEED,
        "interpretation": interp,
        "per_entry": results,
    }

    out_path = Path("research/synthesis/suite2_diag_d4_results.json")
    out_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print()
    print(f"Wrote {out_path}")
    print()
    print("Interpretation:")
    print(f"  {interp}")


if __name__ == "__main__":
    main()
