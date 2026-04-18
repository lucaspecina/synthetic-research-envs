"""Audit SQ<->DAG coherence on generated SRCs.

Implements D1 of Issue #42 (ex local I-024). For each generated SRC, check
whether the sub_questions emitted by the orchestrator LLM are structurally
coherent with the DAG the same orchestrator just built.

Three coherence levels, per sub-question verification spec:
  L1. Variable existence: every variable referenced in arms, measurement,
      assertion, focus_variables must exist in world.graph.
  L2. Causal path: for arms with treatment+outcome, treatment must be an
      ancestor of outcome (i.e., a directed T->...->Y path exists).
  L3. Adjust set validity: for arms with non-empty adjust_set, the set
      must d-separate treatment from outcome in the mutilated graph
      (standard backdoor criterion).

Usage:
    python scripts/audit_sq_dag_coherence.py --results-dir <path> [--json <out>]

If --results-dir omitted, defaults to ../../results/p05_canonical_batch/.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import networkx as nx


# ------------------------- DAG construction ------------------------- #


def build_dag(world: dict[str, Any]) -> nx.DiGraph:
    g = nx.DiGraph()
    # Include latent variables too so we catch references to latents.
    all_nodes = list(world.get("variables", [])) + list(world.get("latent_variables", []))
    g.add_nodes_from(all_nodes)
    graph_map: dict[str, list[str]] = world.get("graph", {})
    for child, parents in graph_map.items():
        for parent in parents:
            g.add_edge(parent, child)
    return g


# ------------------- Reference extraction ------------------- #


_ARM_VAR_FIELDS = [
    "treatment",
    "outcome",
    "sweep_var",
]
_ARM_LIST_FIELDS = [
    "adjust_set",
    "observed_vars",
]
_MEAS_VAR_FIELDS = [
    "lhs",
    "rhs",
    "treatment",
    "outcome",
]
_MEAS_LIST_FIELDS = [
    "cond_set",
    "candidate_causes",
    "candidate_adjust_set",
]


def _collect_strs(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, str):
        return [val]
    if isinstance(val, list):
        return [v for v in val if isinstance(v, str)]
    if isinstance(val, dict):
        return [k for k in val.keys() if isinstance(k, str)]
    return []


def spec_variable_refs(spec: dict[str, Any]) -> list[tuple[str, str]]:
    """Return list of (source_path, var_name) for every variable reference in spec."""
    refs: list[tuple[str, str]] = []
    arms = spec.get("arms") or []
    for i, arm in enumerate(arms):
        for fld in _ARM_VAR_FIELDS:
            for v in _collect_strs(arm.get(fld)):
                refs.append((f"arms[{i}].{fld}", v))
        for fld in _ARM_LIST_FIELDS:
            for v in _collect_strs(arm.get(fld)):
                refs.append((f"arms[{i}].{fld}[]", v))
        # condition_on is dict {var: val}
        for v in _collect_strs(arm.get("condition_on") or {}):
            refs.append((f"arms[{i}].condition_on.{{key}}", v))
        # values dict is similar for intervene arms
        for v in _collect_strs(arm.get("values") or {}):
            refs.append((f"arms[{i}].values.{{key}}", v))
    meas = spec.get("measurement") or {}
    for fld in _MEAS_VAR_FIELDS:
        for v in _collect_strs(meas.get(fld)):
            refs.append((f"measurement.{fld}", v))
    for fld in _MEAS_LIST_FIELDS:
        for v in _collect_strs(meas.get(fld)):
            refs.append((f"measurement.{fld}[]", v))
    return refs


# ------------------- Coherence checks ------------------- #


def check_existence(spec: dict[str, Any], dag: nx.DiGraph) -> list[dict[str, str]]:
    """L1: every referenced var must exist in DAG."""
    missing = []
    nodes = set(dag.nodes)
    for path, var in spec_variable_refs(spec):
        if var not in nodes:
            missing.append({"where": path, "var": var})
    return missing


def check_causal_path(spec: dict[str, Any], dag: nx.DiGraph) -> list[dict[str, Any]]:
    """L2: for arms with treatment+outcome, T must be an ancestor of Y."""
    violations = []
    for i, arm in enumerate(spec.get("arms") or []):
        t = arm.get("treatment")
        y = arm.get("outcome")
        if not t or not y:
            continue
        if t not in dag.nodes or y not in dag.nodes:
            continue  # covered by L1
        if not nx.has_path(dag, t, y):
            violations.append(
                {
                    "arm_idx": i,
                    "arm_kind": arm.get("kind"),
                    "treatment": t,
                    "outcome": y,
                    "reason": "no directed path T->...->Y in DAG",
                }
            )
    # Also check measurement.treatment -> measurement.outcome
    meas = spec.get("measurement") or {}
    t = meas.get("treatment")
    y = meas.get("outcome")
    if t and y and t in dag.nodes and y in dag.nodes:
        if not nx.has_path(dag, t, y):
            violations.append(
                {
                    "arm_idx": None,
                    "arm_kind": "measurement",
                    "treatment": t,
                    "outcome": y,
                    "reason": "no directed path T->...->Y in DAG (measurement)",
                }
            )
    return violations


def check_adjust_set(spec: dict[str, Any], dag: nx.DiGraph) -> list[dict[str, Any]]:
    """L3: for arms with non-empty adjust_set, it must d-separate T from Y in mutilated graph."""
    violations = []
    for i, arm in enumerate(spec.get("arms") or []):
        adjust = arm.get("adjust_set") or []
        if not adjust:
            continue
        t = arm.get("treatment")
        y = arm.get("outcome")
        if not t or not y:
            violations.append(
                {
                    "arm_idx": i,
                    "arm_kind": arm.get("kind"),
                    "adjust_set": adjust,
                    "reason": "adjust_set non-empty but treatment/outcome missing",
                }
            )
            continue
        if t not in dag.nodes or y not in dag.nodes:
            continue  # covered by L1
        z_set = set(v for v in adjust if v in dag.nodes)
        mutilated = dag.copy()
        mutilated.remove_edges_from(list(mutilated.out_edges(t)))
        # Descendant check: adjust vars must not be descendants of T
        descendants = nx.descendants(dag, t)
        bad = z_set & descendants
        if bad:
            violations.append(
                {
                    "arm_idx": i,
                    "arm_kind": arm.get("kind"),
                    "adjust_set": sorted(adjust),
                    "treatment": t,
                    "outcome": y,
                    "reason": f"adjust_set contains descendants of T: {sorted(bad)}",
                }
            )
            continue
        try:
            sep = nx.is_d_separator(mutilated, {t}, {y}, z_set)
        except Exception as e:
            violations.append(
                {
                    "arm_idx": i,
                    "arm_kind": arm.get("kind"),
                    "adjust_set": sorted(adjust),
                    "treatment": t,
                    "outcome": y,
                    "reason": f"d-separation check error: {e}",
                }
            )
            continue
        if not sep:
            violations.append(
                {
                    "arm_idx": i,
                    "arm_kind": arm.get("kind"),
                    "adjust_set": sorted(adjust),
                    "treatment": t,
                    "outcome": y,
                    "reason": "adjust_set does not d-separate T from Y (backdoor paths open)",
                }
            )
    return violations


# ------------------- Case audit ------------------- #


def audit_case(case_dir: Path) -> dict[str, Any]:
    src_path = case_dir / "src.json"
    if not src_path.exists():
        return {"case": case_dir.name, "error": "missing src.json"}
    src = json.loads(src_path.read_text(encoding="utf-8"))
    world = src.get("world") or {}
    dag = build_dag(world)
    sqs = src.get("sub_questions_v2") or []

    per_sq = []
    total_specs = 0
    specs_l1_fail = 0
    specs_l2_fail = 0
    specs_l3_fail = 0

    for sq in sqs:
        sq_id = sq.get("sq_id", "?")
        sq_text = (sq.get("text_gloss") or "")[:180]
        tier = sq.get("tier")
        focus = sq.get("focus_variables") or []
        # focus_variables may be a list or a dict. Collect ref vars.
        focus_refs = _collect_strs(focus)
        # Existence of focus variables
        focus_missing = [v for v in focus_refs if v not in dag.nodes]
        sq_spec_results = []
        for j, vspec in enumerate(sq.get("verification_specs") or []):
            spec = vspec.get("spec") or {}
            spec_id = spec.get("spec_id", f"spec[{j}]")
            missing = check_existence(spec, dag)
            path_violations = check_causal_path(spec, dag)
            adjust_violations = check_adjust_set(spec, dag)
            total_specs += 1
            if missing:
                specs_l1_fail += 1
            if path_violations:
                specs_l2_fail += 1
            if adjust_violations:
                specs_l3_fail += 1
            sq_spec_results.append(
                {
                    "spec_id": spec_id,
                    "role": vspec.get("role"),
                    "L1_missing_vars": missing,
                    "L2_no_causal_path": path_violations,
                    "L3_invalid_adjust_set": adjust_violations,
                    "is_coherent": not (missing or path_violations or adjust_violations),
                }
            )
        per_sq.append(
            {
                "sq_id": sq_id,
                "tier": tier,
                "text": sq_text,
                "focus_variables": focus_refs,
                "focus_missing": focus_missing,
                "specs": sq_spec_results,
            }
        )

    summary = {
        "case": case_dir.name,
        "num_variables": dag.number_of_nodes(),
        "num_edges": dag.number_of_edges(),
        "num_sqs": len(sqs),
        "num_specs": total_specs,
        "specs_L1_fail": specs_l1_fail,
        "specs_L2_fail": specs_l2_fail,
        "specs_L3_fail": specs_l3_fail,
        "specs_any_fail": sum(
            1 for sq in per_sq for s in sq["specs"] if not s["is_coherent"]
        ),
    }
    return {"summary": summary, "per_sq": per_sq}


# ------------------- CLI ------------------- #


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--results-dir",
        default="../../../results/p05_canonical_batch",
        help="Directory containing case subdirs, each with a src.json",
    )
    ap.add_argument("--json", dest="json_out", help="Optional JSON output path")
    args = ap.parse_args()

    root = Path(args.results_dir)
    if not root.is_dir():
        print(f"ERROR: results dir not found: {root}", file=sys.stderr)
        sys.exit(2)

    case_dirs = sorted([p for p in root.iterdir() if p.is_dir()])
    reports = []
    for cd in case_dirs:
        r = audit_case(cd)
        reports.append(r)

    # Aggregate
    agg = {
        "total_cases": len(reports),
        "total_specs": 0,
        "L1_fail": 0,
        "L2_fail": 0,
        "L3_fail": 0,
        "any_fail": 0,
    }
    for r in reports:
        s = r.get("summary") or {}
        agg["total_specs"] += s.get("num_specs", 0)
        agg["L1_fail"] += s.get("specs_L1_fail", 0)
        agg["L2_fail"] += s.get("specs_L2_fail", 0)
        agg["L3_fail"] += s.get("specs_L3_fail", 0)
        agg["any_fail"] += s.get("specs_any_fail", 0)

    # Report
    print("=" * 76)
    print(f"SQ<->DAG COHERENCE AUDIT ({root})")
    print("=" * 76)
    print()
    print(f"{'case':<20} {'V':>3} {'E':>3} {'SQs':>4} {'Specs':>6} {'L1':>3} {'L2':>3} {'L3':>3} {'any':>4}")
    print("-" * 76)
    for r in reports:
        s = r.get("summary") or {}
        name = r.get("case") or s.get("case") or "?"
        print(
            f"{name:<20} {s.get('num_variables', 0):>3} {s.get('num_edges', 0):>3} "
            f"{s.get('num_sqs', 0):>4} {s.get('num_specs', 0):>6} "
            f"{s.get('specs_L1_fail', 0):>3} {s.get('specs_L2_fail', 0):>3} "
            f"{s.get('specs_L3_fail', 0):>3} {s.get('specs_any_fail', 0):>4}"
        )
    print("-" * 76)
    print(
        f"{'TOTAL':<20} {'':>3} {'':>3} {'':>4} {agg['total_specs']:>6} "
        f"{agg['L1_fail']:>3} {agg['L2_fail']:>3} {agg['L3_fail']:>3} {agg['any_fail']:>4}"
    )
    if agg["total_specs"]:
        print()
        print(f"Incoherence rate: {agg['any_fail']}/{agg['total_specs']} = "
              f"{100*agg['any_fail']/agg['total_specs']:.1f}%")
        print(f"  L1 (missing var): {agg['L1_fail']}/{agg['total_specs']} = "
              f"{100*agg['L1_fail']/agg['total_specs']:.1f}%")
        print(f"  L2 (no T->Y path): {agg['L2_fail']}/{agg['total_specs']} = "
              f"{100*agg['L2_fail']/agg['total_specs']:.1f}%")
        print(f"  L3 (bad adjust_set): {agg['L3_fail']}/{agg['total_specs']} = "
              f"{100*agg['L3_fail']/agg['total_specs']:.1f}%")

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps({"aggregate": agg, "per_case": reports}, indent=2),
            encoding="utf-8",
        )
        print(f"\nFull JSON: {args.json_out}")


if __name__ == "__main__":
    main()
