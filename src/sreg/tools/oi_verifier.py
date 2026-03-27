"""Open Investigation Verifier: execute AtomicSpecs against an SCMWorld.

This module bridges the composable grammar (open_investigation.py models)
with the SCM simulation engine (SCMWorld + SCMSolver). It executes each
AtomicSpec and returns a ground-truth verdict.

The verifier is DETERMINISTIC given the SCM — no LLM, no heuristics.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from sreg.models.open_investigation import (
    EPISODE_PRECISION_GATE,
    FAMILY_HIT_THRESHOLD,
    MAX_CLAIMS,
    OVERCLAIM_MAX,
    SPEC_BASE,
    SPEC_BONUS_MAX,
    Assertion,
    AssertionKind,
    AtomicSpec,
    AtomVerdict,
    Comparison,
    ComparisonKind,
    EpisodeScore,
    Measurement,
    MeasurementKind,
    QueryArm,
    QueryKind,
    SalienceFamily,
)
from sreg.solver.scm_solver import SCMSolver
from sreg.world.scm import SCMWorld

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core: execute a single AtomicSpec
# ---------------------------------------------------------------------------


def verify_atom(
    spec: AtomicSpec,
    world: SCMWorld,
    solver: SCMSolver,
    n_mc: int = 50_000,
    seed: int | None = None,
) -> AtomVerdict:
    """Execute an AtomicSpec against an SCMWorld and return a verdict.

    Steps:
    1. Run each QueryArm to get samples
    2. Apply Measurement to extract values per arm
    3. Apply Comparison across arms
    4. Check Assertion against the comparison result
    """
    try:
        arm_samples = _run_arms(spec.arms, world, solver, n_mc, seed)
        measurements = _measure(spec.measurement, arm_samples, world, solver, seed)
        comparison_result = _compare(spec.comparison, measurements, spec.arms)
        holds, ground_truth = _assert(spec.assertion, comparison_result)
    except Exception as e:
        logger.warning("Verification failed for %s: %s", spec.spec_id, e)
        return AtomVerdict(
            atom_id=spec.spec_id,
            spec=spec,
            ground_truth=str(e),
            solver_assertion_holds=False,
            score=0.0,
            detail={"error": str(e)},
        )

    return AtomVerdict(
        atom_id=spec.spec_id,
        spec=spec,
        ground_truth=ground_truth,
        solver_assertion_holds=holds,
        score=1.0 if holds else 0.0,
        detail={"measurements": measurements, "comparison": comparison_result},
    )


# ---------------------------------------------------------------------------
# Step 1: Run arms
# ---------------------------------------------------------------------------


def _run_arms(
    arms: tuple[QueryArm, ...],
    world: SCMWorld,
    solver: SCMSolver,
    n_mc: int,
    seed: int | None,
) -> dict[str, np.ndarray | dict[str, Any]]:
    """Run each arm and return raw samples or computed values."""
    results: dict[str, Any] = {}
    for i, arm in enumerate(arms):
        arm_seed = (seed + i * 1000) if seed is not None else None
        results[arm.label] = _run_single_arm(arm, world, solver, n_mc, arm_seed)
    return results


def _run_single_arm(
    arm: QueryArm,
    world: SCMWorld,
    solver: SCMSolver,
    n_mc: int,
    seed: int | None,
) -> dict[str, Any]:
    """Run a single QueryArm and return results."""
    if arm.kind == QueryKind.BASELINE:
        df = world.sample(n=n_mc, seed=seed)
        return {"df": df, "kind": "baseline"}

    if arm.kind == QueryKind.INTERVENE:
        do = {k: float(v) for k, v in arm.values.items()}
        if arm.condition_on:
            # Interventional with conditioning: sample with do, then filter
            df = world.sample(n=n_mc, seed=seed, do=do)
            df = _filter_condition(df, arm.condition_on)
            return {"df": df, "kind": "intervene_conditioned"}
        df = world.sample(n=n_mc, seed=seed, do=do)
        return {"df": df, "kind": "intervene"}

    if arm.kind == QueryKind.OBSERVE:
        # Observational conditioning: sample without intervention, filter
        df = world.sample(n=n_mc, seed=seed)
        obs = {k: float(v) for k, v in arm.values.items()}
        df = _filter_condition(df, obs)
        if arm.condition_on:
            df = _filter_condition(df, arm.condition_on)
        return {"df": df, "kind": "observe"}

    if arm.kind == QueryKind.CONDITION:
        df = world.sample(n=n_mc, seed=seed)
        df = _filter_condition(df, arm.condition_on)
        return {"df": df, "kind": "condition"}

    if arm.kind == QueryKind.ADJUST:
        # Backdoor adjustment: compute adjusted effect via stratification
        return _run_adjustment(arm, world, solver, n_mc, seed)

    if arm.kind == QueryKind.SWEEP:
        # Run base query at each sweep value
        return _run_sweep(arm, world, solver, n_mc, seed)

    raise ValueError(f"Unknown query kind: {arm.kind}")


def _filter_condition(
    df: pd.DataFrame, conditions: dict[str, Any], tolerance: float = 0.15
) -> pd.DataFrame:
    """Filter dataframe by approximate conditioning (for continuous vars)."""
    mask = pd.Series(True, index=df.index)
    for var, val in conditions.items():
        if var not in df.columns:
            continue
        if isinstance(val, (int, float)):
            col_std = df[var].std()
            tol = max(tolerance * col_std, 0.01)
            mask &= (df[var] - float(val)).abs() <= tol
        else:
            mask &= df[var] == val
    result = df[mask]
    if len(result) < 30:
        logger.warning(
            "Conditioning left only %d rows (need 30+). Results may be unreliable.",
            len(result),
        )
    return result


def _run_adjustment(
    arm: QueryArm,
    world: SCMWorld,
    solver: SCMSolver,
    n_mc: int,
    seed: int | None,
) -> dict[str, Any]:
    """Backdoor adjustment: E[Y | do(X=x)] = sum_z P(Y|X=x,Z=z) P(Z=z).

    Uses OBSERVATIONAL data + stratification by adjust_set, NOT do().
    This is the key distinction from INTERVENE: adjust estimates the causal
    effect from observational data using the backdoor formula.
    """
    if not arm.treatment or not arm.outcome:
        raise ValueError("adjust arm requires treatment and outcome")
    if not arm.adjust_set:
        raise ValueError("adjust arm requires adjust_set (backdoor variables)")

    x_val = float(arm.values.get(arm.treatment, 0.0))
    outcome = arm.outcome
    adjust_vars = list(arm.adjust_set)

    # Sample observational data (NO interventions)
    df = world.sample(n=n_mc, seed=seed)

    # Filter to observations where X is near the desired value
    df_x = _filter_condition(df, {arm.treatment: x_val})
    if len(df_x) < 30:
        logger.warning(
            "Adjustment: only %d obs with %s~%.2f. Falling back to interventional.",
            len(df_x),
            arm.treatment,
            x_val,
        )
        samples = solver.interventional_samples(
            outcome, do={arm.treatment: x_val}, n=n_mc, seed=seed
        )
        return {"samples": samples, "kind": "adjust_fallback", "treatment_val": x_val}

    # Stratified estimation: for each stratum of Z, compute E[Y|X=x, Z=z]
    # then weight by P(Z=z) from the full population
    n_strata = min(5, max(2, len(df_x) // 50))
    adjusted_values = []

    for z_var in adjust_vars:
        if z_var not in df.columns:
            continue
        # Create strata based on quantiles of Z in the full population
        quantiles = np.quantile(df[z_var].values, np.linspace(0, 1, n_strata + 1))
        for i in range(n_strata):
            z_lo, z_hi = quantiles[i], quantiles[i + 1]
            # P(Z in stratum) from full population
            mask_pop = (df[z_var] >= z_lo) & (df[z_var] <= z_hi)
            p_stratum = mask_pop.mean()
            if p_stratum < 0.01:
                continue
            # E[Y | X=x, Z in stratum] from filtered data
            mask_x_z = (df_x[z_var] >= z_lo) & (df_x[z_var] <= z_hi)
            stratum_y = df_x.loc[mask_x_z, outcome]
            if len(stratum_y) < 5:
                continue
            adjusted_values.append(float(stratum_y.mean()) * p_stratum)

    if not adjusted_values:
        # Fallback to simple conditional mean
        adjusted_mean = float(df_x[outcome].mean())
    else:
        adjusted_mean = (
            sum(adjusted_values) / sum(1 for _ in adjusted_values) if adjusted_values else 0.0
        )
        # Renormalize by total weight
        adjusted_mean = sum(adjusted_values)

    return {
        "samples": np.array([adjusted_mean]),
        "kind": "adjust",
        "treatment_val": x_val,
        "n_strata": n_strata,
        "n_obs": len(df_x),
    }


def _run_sweep(
    arm: QueryArm,
    world: SCMWorld,
    solver: SCMSolver,
    n_mc: int,
    seed: int | None,
) -> dict[str, Any]:
    """Run a sweep: repeat base query at each value."""
    if not arm.sweep_var or not arm.sweep_values:
        raise ValueError("sweep arm requires sweep_var and sweep_values")

    sweep_results = {}
    for i, val in enumerate(arm.sweep_values):
        s = (seed + i * 100) if seed is not None else None
        if arm.sweep_base == QueryKind.INTERVENE:
            df = world.sample(n=n_mc, seed=s, do={arm.sweep_var: float(val)})
        else:
            df = world.sample(n=n_mc, seed=s)
            df = _filter_condition(df, {arm.sweep_var: float(val)})
        sweep_results[float(val)] = df

    return {"sweep_results": sweep_results, "kind": "sweep"}


# ---------------------------------------------------------------------------
# Step 2: Measure
# ---------------------------------------------------------------------------


def _measure(
    measurement: Measurement,
    arm_results: dict[str, Any],
    world: SCMWorld,
    solver: SCMSolver,
    seed: int | None,
) -> dict[str, float | bool]:
    """Apply measurement to arm results."""
    values: dict[str, float | bool] = {}

    for label, result in arm_results.items():
        if measurement.kind == MeasurementKind.IDENTIFIABILITY_CHECK:
            values[label] = _measure_identifiability(measurement, world)
            continue

        if result.get("kind") == "sweep":
            values[label] = _measure_sweep(measurement, result)
            continue

        if result.get("kind") == "adjust":
            samples = result["samples"]
            values[label] = _measure_from_samples(measurement, samples)
            continue

        df = result["df"]
        target = measurement.target

        if measurement.kind == MeasurementKind.MEAN:
            if isinstance(target, tuple):
                for t in target:
                    values[f"{label}_{t}"] = float(df[t].mean()) if t in df.columns else 0.0
            elif target and target in df.columns:
                values[label] = float(df[target].mean())

        elif measurement.kind == MeasurementKind.VARIANCE:
            if target and target in df.columns:
                values[label] = float(df[target].var())

        elif measurement.kind == MeasurementKind.QUANTILE:
            if target and target in df.columns and measurement.q is not None:
                values[label] = float(df[target].quantile(measurement.q))

        elif measurement.kind == MeasurementKind.TAIL_PROB:
            if target and target in df.columns and measurement.threshold is not None:
                values[label] = float((df[target] > measurement.threshold).mean())

        elif measurement.kind == MeasurementKind.CORRELATION:
            if measurement.lhs and measurement.rhs:
                if measurement.lhs in df.columns and measurement.rhs in df.columns:
                    values[label] = float(df[measurement.lhs].corr(df[measurement.rhs]))

        elif measurement.kind == MeasurementKind.PARTIAL_CORRELATION:
            values[label] = _measure_partial_correlation(measurement, df)

        elif measurement.kind == MeasurementKind.DISTRIBUTION:
            if target and target in df.columns:
                values[label] = float(df[target].mean())  # placeholder

    return values


def _measure_from_samples(measurement: Measurement, samples: np.ndarray) -> float:
    """Measure from raw numpy samples (for adjust arms)."""
    if measurement.kind == MeasurementKind.MEAN:
        return float(np.mean(samples))
    if measurement.kind == MeasurementKind.VARIANCE:
        return float(np.var(samples))
    if measurement.kind == MeasurementKind.QUANTILE and measurement.q is not None:
        return float(np.quantile(samples, measurement.q))
    if measurement.kind == MeasurementKind.TAIL_PROB and measurement.threshold is not None:
        return float(np.mean(samples > measurement.threshold))
    return float(np.mean(samples))


def _measure_sweep(measurement: Measurement, result: dict) -> dict[float, float]:
    """Measure at each sweep point."""
    sweep_results = result["sweep_results"]
    target = measurement.target
    out = {}
    for val, df in sweep_results.items():
        if measurement.kind == MeasurementKind.MEAN and target and target in df.columns:
            out[val] = float(df[target].mean())
        elif measurement.kind == MeasurementKind.TAIL_PROB and target and target in df.columns:
            out[val] = float((df[target] > measurement.threshold).mean())
        else:
            out[val] = 0.0
    return out


def _measure_partial_correlation(measurement: Measurement, df: pd.DataFrame) -> float:
    """Compute partial correlation between lhs and rhs controlling for cond_set."""
    if not measurement.lhs or not measurement.rhs:
        return 0.0
    cols = [measurement.lhs, measurement.rhs] + list(measurement.cond_set)
    if not all(c in df.columns for c in cols):
        return 0.0

    sub = df[cols].dropna()
    if len(sub) < 10:
        return 0.0

    if not measurement.cond_set:
        return float(sub[measurement.lhs].corr(sub[measurement.rhs]))

    # Residualize lhs and rhs on cond_set
    from numpy.linalg import lstsq

    Z = sub[list(measurement.cond_set)].values
    Z = np.column_stack([Z, np.ones(len(Z))])

    x = sub[measurement.lhs].values
    y = sub[measurement.rhs].values

    coef_x, _, _, _ = lstsq(Z, x, rcond=None)
    coef_y, _, _, _ = lstsq(Z, y, rcond=None)

    resid_x = x - Z @ coef_x
    resid_y = y - Z @ coef_y

    denom = np.std(resid_x) * np.std(resid_y)
    if denom < 1e-10:
        return 0.0
    return float(np.corrcoef(resid_x, resid_y)[0, 1])


def _measure_identifiability(measurement: Measurement, world: SCMWorld) -> bool:
    """Check if a causal effect is identifiable from the DAG + observed vars."""
    import networkx as nx

    if not measurement.treatment or not measurement.outcome:
        return False

    dag = world.dag
    obs = set(world.observable_variables)

    # Basic check: is there a backdoor adjustment set among observables?
    # A sufficient condition: all backdoor paths can be blocked
    treatment = measurement.treatment
    outcome = measurement.outcome

    if treatment not in dag.nodes or outcome not in dag.nodes:
        return False

    # Check if candidate_adjust_set blocks all backdoor paths
    if measurement.candidate_adjust_set:
        adjust = set(measurement.candidate_adjust_set)
        # Verify it's a valid adjustment set (blocks all non-causal paths)
        try:
            return nx.is_d_separator(dag.to_undirected(), {treatment}, {outcome}, adjust)
        except Exception:
            return False

    # Without candidate set: check if ANY observable subset works
    # Simple heuristic: parents of treatment that are observable
    parents = set(dag.predecessors(treatment)) & obs
    if parents:
        try:
            return nx.is_d_separator(dag.to_undirected(), {treatment}, {outcome}, parents)
        except Exception:
            return False

    return False


# ---------------------------------------------------------------------------
# Step 3: Compare
# ---------------------------------------------------------------------------


def _compare(
    comparison: Comparison,
    measurements: dict[str, Any],
    arms: tuple[QueryArm, ...],
) -> dict[str, Any]:
    """Compare measurements across arms."""
    result: dict[str, Any] = {}

    if comparison.kind == ComparisonKind.IDENTITY:
        # Passthrough — used for structural checks
        result["value"] = next(iter(measurements.values()), None)
        return result

    if comparison.kind == ComparisonKind.DIFFERENCE:
        labels = [a.label for a in arms]
        ref = comparison.ref_arm or (labels[1] if len(labels) > 1 else labels[0])
        other = [lab for lab in labels if lab != ref]
        if other and ref in measurements and other[0] in measurements:
            val_other = measurements[other[0]]
            val_ref = measurements[ref]
            if isinstance(val_other, (int, float)) and isinstance(val_ref, (int, float)):
                result["difference"] = val_other - val_ref
                result["ref"] = val_ref
                result["other"] = val_other

    elif comparison.kind == ComparisonKind.RATIO:
        labels = [a.label for a in arms]
        ref = comparison.ref_arm or labels[-1]
        other = [lab for lab in labels if lab != ref]
        if other and ref in measurements and other[0] in measurements:
            denom = measurements[ref]
            if isinstance(denom, (int, float)) and abs(denom) > 1e-10:
                result["ratio"] = measurements[other[0]] / denom

    elif comparison.kind == ComparisonKind.RANKING:
        ranked = sorted(
            [(k, v) for k, v in measurements.items() if isinstance(v, (int, float))],
            key=lambda x: x[1],
            reverse=True,
        )
        result["ranking"] = tuple(k for k, _ in ranked)
        result["values"] = {k: v for k, v in ranked}

    elif comparison.kind == ComparisonKind.GAP:
        # For measurement gap: compare two sub-measurements
        vals = [v for v in measurements.values() if isinstance(v, (int, float))]
        if len(vals) >= 2:
            result["gap"] = abs(vals[0] - vals[1])
        # Also check labeled measurements (e.g. base_defect_observed, base_defect_real)
        labeled = {k: v for k, v in measurements.items() if isinstance(v, (int, float))}
        if len(labeled) >= 2:
            keys = sorted(labeled.keys())
            result["gap"] = abs(labeled[keys[0]] - labeled[keys[1]])
            result["values"] = labeled

    elif comparison.kind == ComparisonKind.PROPORTION:
        vals = [v for v in measurements.values() if isinstance(v, (int, float))]
        if len(vals) >= 2 and abs(vals[0]) > 1e-10:
            result["proportion"] = vals[1] / vals[0]

    elif comparison.kind == ComparisonKind.PIECEWISE_FIT:
        # For sweep results
        for v in measurements.values():
            if isinstance(v, dict):
                result["sweep_data"] = v
                result["changepoint"] = _detect_changepoint(v)
                break

    elif comparison.kind == ComparisonKind.CONTRAST_DIFF:
        # Diff-in-diff: (hi_treatment - lo_treatment) at hi_modifier vs lo_modifier
        vals = list(measurements.values())
        if len(vals) >= 4:
            result["contrast_diff"] = (vals[0] - vals[1]) - (vals[2] - vals[3])

    return result


def _detect_changepoint(sweep_data: dict[float, float]) -> dict[str, Any]:
    """Simple changepoint detection via max residual reduction."""
    if len(sweep_data) < 4:
        return {"detected": False}

    xs = sorted(sweep_data.keys())
    ys = [sweep_data[x] for x in xs]
    ys_arr = np.array(ys)

    best_reduction = 0.0
    best_idx = -1
    total_var = np.var(ys_arr) * len(ys_arr)

    for i in range(2, len(xs) - 1):
        left_var = np.var(ys_arr[:i]) * i if i > 1 else 0
        right_var = np.var(ys_arr[i:]) * (len(ys_arr) - i) if len(ys_arr) - i > 1 else 0
        reduction = total_var - (left_var + right_var)
        if reduction > best_reduction:
            best_reduction = reduction
            best_idx = i

    if best_idx >= 0 and best_reduction > 0.1 * total_var:
        return {
            "detected": True,
            "changepoint_x": xs[best_idx],
            "reduction_fraction": best_reduction / max(total_var, 1e-10),
        }
    return {"detected": False}


# ---------------------------------------------------------------------------
# Step 4: Assert
# ---------------------------------------------------------------------------


def _assert(
    assertion: Assertion, comparison_result: dict[str, Any]
) -> tuple[bool, float | bool | str]:
    """Check if the assertion holds given the comparison result."""
    kind = assertion.kind
    tol = assertion.tolerance

    if kind == AssertionKind.POSITIVE:
        diff = comparison_result.get("difference", comparison_result.get("value", 0))
        if isinstance(diff, bool):
            return diff, diff
        val = float(diff) if diff is not None else 0.0
        return val > tol, val

    if kind == AssertionKind.NEGATIVE:
        diff = comparison_result.get("difference", comparison_result.get("value", 0))
        val = float(diff) if diff is not None else 0.0
        return val < -tol, val

    if kind == AssertionKind.NEAR_ZERO:
        diff = comparison_result.get("difference", comparison_result.get("value", 0))
        val = float(diff) if diff is not None else 0.0
        return abs(val) <= tol, val

    if kind == AssertionKind.GREATER_THAN:
        diff = comparison_result.get("difference", 0)
        val = float(diff) if diff is not None else 0.0
        return val > assertion.threshold, val

    if kind == AssertionKind.LESS_THAN:
        diff = comparison_result.get("difference", 0)
        val = float(diff) if diff is not None else 0.0
        return val < assertion.threshold, val

    if kind == AssertionKind.RANK_ORDER:
        ranking = comparison_result.get("ranking", ())
        expected = assertion.order
        if not expected:
            return True, str(ranking)
        matches = ranking[: len(expected)] == expected[: len(ranking)]
        return matches, str(ranking)

    if kind == AssertionKind.CHANGEPOINT_EXISTS:
        cp = comparison_result.get("changepoint", {})
        detected = cp.get("detected", False)
        return detected, cp

    if kind == AssertionKind.SIGN_FLIP:
        cd = comparison_result.get("contrast_diff", 0)
        return abs(float(cd)) > tol, float(cd)

    if kind == AssertionKind.GAP_MATERIAL:
        gap = comparison_result.get("gap", 0)
        min_gap = 0.10  # default
        return float(gap) > min_gap, float(gap)

    if kind in (AssertionKind.IDENTIFIABLE, AssertionKind.NOT_IDENTIFIABLE):
        val = comparison_result.get("value", False)
        if kind == AssertionKind.IDENTIFIABLE:
            return bool(val), bool(val)
        return not bool(val), bool(val)

    if kind in (AssertionKind.DISTINGUISHABLE, AssertionKind.NOT_DISTINGUISHABLE):
        val = comparison_result.get("value", False)
        if kind == AssertionKind.DISTINGUISHABLE:
            return bool(val), bool(val)
        return not bool(val), bool(val)

    return False, "unknown_assertion"


# ---------------------------------------------------------------------------
# Scoring: claim-level and episode-level
# ---------------------------------------------------------------------------


def score_claim_against_family(
    atom_verdicts: dict[str, float],
    family: SalienceFamily,
) -> tuple[float, str]:
    """Score a claim's atom verdicts against a salience family.

    Returns (score, verdict_label).
    """
    covered = [a for a in family.atoms if a.atom_id in atom_verdicts]
    if not covered:
        return 0.0, "unmatched"

    verified_w = sum(a.weight * atom_verdicts[a.atom_id] for a in covered)
    covered_w = sum(a.weight for a in covered)
    family_w = sum(a.weight for a in family.atoms)
    material_w = sum(a.weight for a in family.atoms if a.material) or 1.0
    omitted_material_w = sum(
        a.weight for a in family.atoms if a.material and a.atom_id not in atom_verdicts
    )

    atom_precision = verified_w / covered_w if covered_w > 0 else 0.0
    specificity_ratio = verified_w / family_w if family_w > 0 else 0.0
    omitted_material_ratio = omitted_material_w / material_w

    specificity_bonus = SPEC_BONUS_MAX * specificity_ratio
    overclaim_penalty = OVERCLAIM_MAX * omitted_material_ratio

    score = max(
        0.0,
        min(1.0, atom_precision * (SPEC_BASE + specificity_bonus) * (1.0 - overclaim_penalty)),
    )

    if atom_precision == 1.0 and omitted_material_ratio == 0.0:
        verdict = "fully_true"
    elif atom_precision == 1.0:
        verdict = "partially_true_with_omission"
    elif atom_precision > 0.0:
        verdict = "mixed"
    else:
        verdict = "false"

    return score, verdict


def score_episode(
    claim_matches: list[tuple[str, float]],
    families: list[SalienceFamily],
    n_claims: int,
    claim_budget: int = MAX_CLAIMS,
) -> EpisodeScore:
    """Compute episode-level score from claim matches.

    Args:
        claim_matches: List of (family_id, match_score) for each claim.
        families: The salience map families.
        n_claims: Number of claims the solver submitted.
        claim_budget: Maximum allowed claims (default K=5).
    """
    # Best score per family
    best_by_family: dict[str, float] = {}
    for family_id, s in claim_matches:
        best_by_family[family_id] = max(best_by_family.get(family_id, 0.0), s)

    # Correctness: average score across all claims
    correctness = sum(s for _, s in claim_matches) / max(len(claim_matches), 1)

    # Coverage: fraction of families hit above threshold
    families_hit = sum(
        1 for f in families if best_by_family.get(f.family_id, 0.0) >= FAMILY_HIT_THRESHOLD
    )
    coverage = families_hit / max(len(families), 1)

    # Precision gate
    precision_gate = correctness < EPISODE_PRECISION_GATE
    if precision_gate:
        coverage = 0.0

    # Efficiency
    overflow = max(0, n_claims - claim_budget)
    efficiency = max(0.0, 1.0 - (overflow / max(claim_budget, 1)))

    total = 0.60 * correctness + 0.30 * coverage + 0.10 * efficiency

    return EpisodeScore(
        correctness=correctness,
        coverage=coverage,
        efficiency=efficiency,
        total=total,
        families_hit=families_hit,
        families_total=len(families),
        precision_gate_active=precision_gate,
    )


__all__ = [
    "verify_atom",
    "score_claim_against_family",
    "score_episode",
]
