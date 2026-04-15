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
    ClaimVerdict,
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
    """Filter dataframe by condition predicates (P1: supports range/quantile/in_set).

    Raises ValueError for missing columns or numeric predicates on
    non-numeric columns (#10 P1.5). verify_atom catches the exception
    and converts it to score=0.0.
    """
    mask = pd.Series(True, index=df.index)
    for var, pred in conditions.items():
        if var not in df.columns:
            logger.warning(
                "_filter_condition: column %r not in DataFrame "
                "(available: %s). Spec references a non-existent variable.",
                var, sorted(df.columns.tolist()),
            )
            raise ValueError(
                f"Condition references non-existent column {var!r}. "
                f"Available: {sorted(df.columns.tolist())}"
            )
        # Dispatch by predicate kind (ConditionPredicate objects)
        kind = getattr(pred, "kind", None)
        if kind in ("approx_eq", "range", "quantile_range"):
            if not pd.api.types.is_numeric_dtype(df[var]):
                logger.warning(
                    "_filter_condition: numeric predicate %r on "
                    "non-numeric column %r (dtype=%s).",
                    kind, var, df[var].dtype,
                )
                raise ValueError(
                    f"Numeric predicate {kind!r} on non-numeric "
                    f"column {var!r} (dtype={df[var].dtype})"
                )
        if kind == "approx_eq":
            col_std = df[var].std()
            tol = max(pred.tol_std * col_std, 0.01)
            mask &= (df[var] - float(pred.value)).abs() <= tol
        elif kind == "range":
            mask &= (df[var] >= pred.lo) & (df[var] <= pred.hi)
        elif kind == "quantile_range":
            lo_val = df[var].quantile(pred.q_lo)
            hi_val = df[var].quantile(pred.q_hi)
            mask &= (df[var] >= lo_val) & (df[var] <= hi_val)
        elif kind == "in_set":
            mask &= df[var].isin(pred.values)
        elif isinstance(pred, (int, float)):
            # Legacy fallback: raw scalar (shouldn't happen after model_validator)
            if not pd.api.types.is_numeric_dtype(df[var]):
                raise ValueError(
                    f"Numeric predicate (raw scalar) on non-numeric "
                    f"column {var!r} (dtype={df[var].dtype})"
                )
            col_std = df[var].std()
            tol = max(tolerance * col_std, 0.01)
            mask &= (df[var] - float(pred)).abs() <= tol
        else:
            # Legacy fallback: raw string/bool
            mask &= df[var] == pred
    result = df[mask]
    if len(result) < 30:
        logger.warning(
            "Conditioning left only %d rows (need 30+). Results may be unreliable.",
            len(result),
        )
    return result


def _find_backdoor_set(
    world: SCMWorld, treatment: str, outcome: str,
) -> tuple[str, ...] | None:
    """Find a minimal valid backdoor adjustment set from the DAG.

    Returns a tuple of variable names (sorted for determinism), or None
    if no valid set exists. Only uses observable variables and excludes
    descendants of the treatment.
    """
    import networkx as nx

    dag = world.dag
    obs = set(world.observable_variables)

    if treatment not in dag.nodes or outcome not in dag.nodes:
        return None

    mutilated = dag.copy()
    out_edges = list(mutilated.out_edges(treatment))
    mutilated.remove_edges_from(out_edges)

    desc_treatment = nx.descendants(dag, treatment)

    def _is_valid(z_set: set[str]) -> bool:
        if z_set & desc_treatment:
            return False
        try:
            return nx.is_d_separator(mutilated, {treatment}, {outcome}, z_set)
        except Exception:
            return False

    # Strategy 1: parents of treatment (minimal, common sufficient set)
    parents = set(dag.predecessors(treatment)) & obs
    if parents and _is_valid(parents):
        return tuple(sorted(parents))

    # Strategy 2: non-descendant observable ancestors of outcome
    anc_outcome = nx.ancestors(dag, outcome) & obs
    candidate = anc_outcome - desc_treatment - {treatment}
    if candidate and _is_valid(candidate):
        return tuple(sorted(candidate))

    # Empty set: no backdoor paths need blocking.  Covers the obvious
    # case (treatment is a root node) AND the subtler case where treatment
    # has parents that do not open any backdoor path to outcome (e.g. all
    # confounders are latent and unobservable, or paths do not reach outcome).
    if _is_valid(set()):
        return ()

    return None


def _is_valid_backdoor_set(
    world: SCMWorld, treatment: str, outcome: str, adjust_set: tuple[str, ...],
) -> bool:
    """Check if a specific set of variables is a valid backdoor adjustment set.

    A valid backdoor set Z must:
    1. Not contain any descendants of the treatment.
    2. Block all backdoor paths (non-causal paths) from treatment to outcome.
    """
    import networkx as nx

    dag = world.dag
    if treatment not in dag.nodes or outcome not in dag.nodes:
        return False

    # No descendants of treatment allowed in adjustment set
    desc_treatment = nx.descendants(dag, treatment)
    if set(adjust_set) & desc_treatment:
        return False

    # Check d-separation in the mutilated graph (remove outgoing edges of treatment)
    mutilated = dag.copy()
    mutilated.remove_edges_from(list(mutilated.out_edges(treatment)))
    try:
        return nx.is_d_separator(mutilated, {treatment}, {outcome}, set(adjust_set))
    except Exception:
        return False


def _run_adjustment(
    arm: QueryArm,
    world: SCMWorld,
    solver: SCMSolver,
    n_mc: int,
    seed: int | None,
) -> dict[str, Any]:
    """Backdoor adjustment: verify the adjustment set, then use do() for truth.

    The verifier is NOT a data scientist estimating from observational data —
    it is the oracle (God-mode). It validates that the adjustment strategy is
    sound (valid backdoor set), then computes exact E[Y | do(X=x)] via the
    SCM's interventional_samples().

    If adjust_set is empty, auto-computes a valid set from the DAG.
    Returns kind="adjust_invalid" if no valid backdoor set exists.
    """
    if not arm.treatment or not arm.outcome:
        raise ValueError("adjust arm requires treatment and outcome")

    x_val = float(arm.values.get(arm.treatment, 0.0))

    # Step 1: Resolve and validate the adjustment set
    if arm.adjust_set:
        adjust_set = tuple(sorted(arm.adjust_set))
        if not _is_valid_backdoor_set(world, arm.treatment, arm.outcome, adjust_set):
            logger.warning(
                "adjust %s->%s: provided set %s is NOT a valid backdoor set.",
                arm.treatment, arm.outcome, adjust_set,
            )
            return {
                "samples": np.array([]),
                "kind": "adjust_invalid",
                "treatment_val": x_val,
                "adjust_set": list(adjust_set),
                "reason": "provided adjustment set is not a valid backdoor set",
            }
    else:
        auto_set = _find_backdoor_set(world, arm.treatment, arm.outcome)
        if auto_set is None:
            logger.warning(
                "adjust %s->%s: no valid backdoor set exists in the DAG.",
                arm.treatment, arm.outcome,
            )
            return {
                "samples": np.array([]),
                "kind": "adjust_invalid",
                "treatment_val": x_val,
                "adjust_set": [],
                "reason": "no valid backdoor adjustment set exists",
            }
        adjust_set = auto_set
        if adjust_set:
            logger.info(
                "adjust %s->%s: auto-computed backdoor set from DAG: %s",
                arm.treatment, arm.outcome, list(adjust_set),
            )
        else:
            logger.info(
                "adjust %s->%s: no backdoor paths, empty adjustment set is valid.",
                arm.treatment, arm.outcome,
            )

    # Step 2: Compute exact truth via SCM do-calculus
    samples = solver.interventional_samples(
        arm.outcome, do={arm.treatment: x_val}, n=n_mc, seed=seed
    )

    return {
        "samples": samples,
        "kind": "adjust",
        "treatment_val": x_val,
        "adjust_set": list(adjust_set),
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

        if result.get("kind") == "adjust_invalid":
            values[label] = float("nan")
            continue

        if result.get("kind") in ("adjust", "adjust_fallback"):
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
    """Measure from raw numpy samples (for adjust arms).

    Adjust arms produce 1-D samples of the OUTCOME variable only
    (E[Y | do(X=x)]). They do NOT carry the treatment, conditioning vars,
    or any other column. So measurements that need a multivariate context
    (correlation, partial_correlation, distribution comparisons) are NOT
    computable from these samples and must signal incompatibility (NaN)
    rather than silently fall back to mean(samples). The previous fallback
    caused a silent failure mode in the policy_equity P06 forensics:
    spec(adjust+partial_correlation) returned mean(Y_under_do(X=0)) and
    the assertion was applied as if it were a partial correlation.
    """
    if measurement.kind == MeasurementKind.MEAN:
        return float(np.mean(samples))
    if measurement.kind == MeasurementKind.VARIANCE:
        return float(np.var(samples))
    if measurement.kind == MeasurementKind.QUANTILE and measurement.q is not None:
        return float(np.quantile(samples, measurement.q))
    if measurement.kind == MeasurementKind.TAIL_PROB and measurement.threshold is not None:
        return float(np.mean(samples > measurement.threshold))

    # Incompatible: measurement.kind needs a DataFrame (correlation,
    # partial_correlation, distribution) or is missing a required field
    # (QUANTILE without q, TAIL_PROB without threshold). Return NaN so the
    # incoherent spec is surfaced via holds=False instead of a meaningless
    # value masquerading as a real measurement.
    logger.warning(
        "Adjust arm samples are 1-D outcome only; measurement.kind=%s is not "
        "computable from them. Returning NaN.",
        measurement.kind,
    )
    return float("nan")


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
    """Check if a causal effect is identifiable from the DAG + observed vars.

    Uses the backdoor criterion via _find_backdoor_set(). If a candidate set
    is provided in the measurement, validates it directly instead.
    """
    import networkx as nx

    if not measurement.treatment or not measurement.outcome:
        return False

    dag = world.dag
    obs = set(world.observable_variables)
    treatment = measurement.treatment
    outcome = measurement.outcome

    if treatment not in dag.nodes or outcome not in dag.nodes:
        return False

    # Check candidate set if provided (validate specific set)
    if measurement.candidate_adjust_set:
        adjust = set(measurement.candidate_adjust_set)
        if not adjust.issubset(obs):
            return False
        # Validate via mutilated graph
        mutilated = dag.copy()
        out_edges = list(mutilated.out_edges(treatment))
        mutilated.remove_edges_from(out_edges)
        desc_treatment = nx.descendants(dag, treatment)
        if adjust & desc_treatment:
            return False
        try:
            return nx.is_d_separator(mutilated, {treatment}, {outcome}, adjust)
        except Exception:
            return False

    # No candidate: check if ANY valid set exists
    result = _find_backdoor_set(world, treatment, outcome)
    return result is not None


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


def _extract_scalar(comparison_result: dict[str, Any]) -> float:
    """Extract the main scalar value from any comparison result.

    Checks keys in priority order so assertions work with all comparison types
    (DIFFERENCE, CONTRAST_DIFF, PROPORTION, RATIO, GAP, IDENTITY).
    """
    for key in ("difference", "contrast_diff", "proportion", "ratio", "gap", "value"):
        v = comparison_result.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    return 0.0


def _assert(
    assertion: Assertion, comparison_result: dict[str, Any]
) -> tuple[bool, float | bool | str]:
    """Check if the assertion holds given the comparison result."""
    kind = assertion.kind
    tol = assertion.tolerance

    if kind == AssertionKind.POSITIVE:
        val = comparison_result.get("value")
        if isinstance(val, bool):
            return val, val
        val = _extract_scalar(comparison_result)
        return val > tol, val

    if kind == AssertionKind.NEGATIVE:
        val = _extract_scalar(comparison_result)
        return val < -tol, val

    if kind == AssertionKind.NEAR_ZERO:
        val = _extract_scalar(comparison_result)
        return abs(val) <= tol, val

    if kind == AssertionKind.GREATER_THAN:
        val = _extract_scalar(comparison_result)
        return val > assertion.threshold, val

    if kind == AssertionKind.LESS_THAN:
        val = _extract_scalar(comparison_result)
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
        # Direction-agnostic materiality: abs(value) > threshold
        # Works with GAP comparison (gap key), DIFFERENCE (difference key),
        # and IDENTITY (value key). Used for confounding specs where the
        # claim's direction may differ from ground truth (Simpson's paradox).
        gap = comparison_result.get("gap")
        if gap is not None:
            min_gap = 0.10  # default
            return float(gap) > min_gap, float(gap)
        val = _extract_scalar(comparison_result)
        min_gap = assertion.tolerance if assertion.tolerance > 0 else 0.05
        return abs(val) > min_gap, val

    if kind in (AssertionKind.IDENTIFIABLE, AssertionKind.NOT_IDENTIFIABLE):
        val = comparison_result.get("value", False)
        if kind == AssertionKind.IDENTIFIABLE:
            return bool(val), bool(val)
        return not bool(val), bool(val)

    if kind in (AssertionKind.DISTINGUISHABLE, AssertionKind.NOT_DISTINGUISHABLE):
        # Two valid pairings:
        # (a) IDENTITY + IDENTIFIABILITY_CHECK → comparison_result has bool "value".
        # (b) DIFFERENCE / GAP / CONTRAST_DIFF → comparison_result has a scalar under
        #     "difference" / "gap" / "contrast_diff". Distinguishable means the
        #     scalar's magnitude exceeds tolerance (direction-agnostic).
        val = comparison_result.get("value")
        if isinstance(val, bool):
            is_distinguishable = val
            ground_truth: float | bool = val
        else:
            scalar = _extract_scalar(comparison_result)
            is_distinguishable = abs(scalar) > tol
            ground_truth = scalar
        if kind == AssertionKind.DISTINGUISHABLE:
            return is_distinguishable, ground_truth
        return not is_distinguishable, ground_truth

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
    n_matches = len(claim_matches)
    scores = [s for _, s in claim_matches]
    correctness = sum(scores) / max(n_matches, 1)

    # Coverage: best score per family
    best_by_family: dict[str, float] = {}
    for (family_id, _), s in zip(claim_matches, scores):
        best_by_family[family_id] = max(best_by_family.get(family_id, 0.0), s)

    families_hit = sum(
        1
        for f in families
        if best_by_family.get(f.family_id, 0.0) >= FAMILY_HIT_THRESHOLD
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


def score_episode_v2(
    claim_verdicts: list[ClaimVerdict],
    families: list[SalienceFamily],
    n_claims: int,
    claim_budget: int = MAX_CLAIMS,
) -> EpisodeScore:
    """Compute episode-level score from claim verdicts (v2 scoring).

    Key differences from v1:
    - Correctness = mean of effective_scores (truth * relevance * warrant)
    - Coverage uses family_id from verdicts, not from claim_matches tuples
    - Per-claim scoring (not per-spec)
    - ClaimVerdicts carry all needed info (truth, relevance, effective)
    """

    if not claim_verdicts:
        return EpisodeScore(
            correctness=0.0,
            coverage=0.0,
            efficiency=1.0,
            total=0.10,
            claim_verdicts=claim_verdicts,
            families_hit=0,
            families_total=len(families),
        )

    # Correctness: mean of effective scores across all claims
    effective_scores = [cv.effective_score for cv in claim_verdicts]
    correctness = sum(effective_scores) / len(effective_scores)

    # Coverage: which families were hit by claims with sufficient TRUTH score
    # (not effective_score — coverage should not depend on relevance weighting)
    best_by_family: dict[str, float] = {}
    for cv in claim_verdicts:
        if cv.matched_family_id and cv.matched_family_id not in (
            "__unmatched__", "__abstention__"
        ):
            best_by_family[cv.matched_family_id] = max(
                best_by_family.get(cv.matched_family_id, 0.0),
                cv.truth_score,
            )

    families_hit = sum(
        1
        for f in families
        if best_by_family.get(f.family_id, 0.0) >= FAMILY_HIT_THRESHOLD
    )
    coverage = families_hit / max(len(families), 1)

    # Precision gate: if correctness too low, no coverage credit
    precision_gate = correctness < EPISODE_PRECISION_GATE
    if precision_gate:
        coverage = 0.0

    # Efficiency: penalty for exceeding claim budget
    overflow = max(0, n_claims - claim_budget)
    efficiency = max(0.0, 1.0 - (overflow / max(claim_budget, 1)))

    total = 0.60 * correctness + 0.30 * coverage + 0.10 * efficiency

    return EpisodeScore(
        correctness=correctness,
        coverage=coverage,
        efficiency=efficiency,
        total=total,
        claim_verdicts=claim_verdicts,
        families_hit=families_hit,
        families_total=len(families),
        precision_gate_active=precision_gate,
    )


__all__ = [
    "verify_atom",
    "score_claim_against_family",
    "score_episode",
    "score_episode_v2",
]
