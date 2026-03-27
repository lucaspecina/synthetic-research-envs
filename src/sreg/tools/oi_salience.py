"""Salience map generator: enumerate significant truths from an SCMWorld.

Given an SCMWorld + a brief (target variable + research question), this module
enumerates the significant true claims, groups them into families, and builds
a SalienceMap for coverage scoring.

The map is brief-anchored (starts from target + ancestors), effect-size filtered,
and capped at ~30 families. No LLM needed — pure algorithmic enumeration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import networkx as nx
import numpy as np

from sreg.models.open_investigation import (
    MAX_FAMILIES,
    Assertion,
    AssertionKind,
    AtomicSpec,
    Comparison,
    ComparisonKind,
    FamilyAtom,
    FamilyKey,
    Measurement,
    MeasurementKind,
    QueryArm,
    QueryKind,
    SalienceFamily,
    SalienceMap,
)
from sreg.solver.scm_solver import SCMSolver
from sreg.world.scm import SCMWorld

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Effect size thresholds (normalized by sd(Y))
# ---------------------------------------------------------------------------

EFFECT_THRESHOLDS: dict[str, float] = {
    "causal_effect": 0.15,
    "observational_association": 0.15,
    "heterogeneity": 0.10,
    "interaction": 0.10,
    "mediation": 0.15,
    "tail_risk": 0.05,
    "variance_effect": 0.10,
    "effect_ranking": 0.10,
}

# Max families per pattern class
PATTERN_CAPS: dict[str, int] = {
    "causal_effect": 8,
    "observational_association": 3,
    "heterogeneity": 4,
    "interaction": 3,
    "mediation": 3,
    "tail_risk": 2,
    "variance_effect": 2,
    "effect_ranking": 1,
}


@dataclass
class CandidateTruth:
    """A candidate truth discovered by enumeration."""

    family_key: FamilyKey
    atoms: list[FamilyAtom]
    effect_size: float
    pattern_class: str
    salience: float = 0.0


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def build_salience_map(
    world: SCMWorld,
    target: str,
    n_mc: int = 50_000,
    seed: int = 42,
    max_families: int = MAX_FAMILIES,
) -> SalienceMap:
    """Build a brief-anchored salience map for an SCMWorld.

    Args:
        world: The SCMWorld to analyze.
        target: The primary target variable (from the brief).
        n_mc: Monte Carlo samples per estimation.
        seed: Random seed for reproducibility.
        max_families: Maximum families in the map.

    Returns:
        A SalienceMap with significant, grouped truths.
    """
    solver = SCMSolver(world, n_mc=n_mc)
    obs = set(world.observable_variables)
    ancestors = nx.ancestors(world.dag, target) & obs
    frontier = sorted(ancestors)

    # Compute baseline stats for normalization
    y_samples = world.observational_distribution(target, n=n_mc, seed=seed)
    y_std = max(float(np.std(y_samples)), 1e-6)

    candidates: list[CandidateTruth] = []

    # 1. Causal effects: ATE for each ancestor -> target
    candidates.extend(_enumerate_causal_effects(world, solver, frontier, target, y_std, seed))

    # 2. Heterogeneity: ATE varies by stratum of another ancestor
    candidates.extend(_enumerate_heterogeneity(world, solver, frontier, target, y_std, seed))

    # 3. Mediation: indirect effects through intermediate nodes
    candidates.extend(_enumerate_mediations(world, solver, frontier, target, y_std, seed))

    # 4. Tail risk: effect on extreme outcomes
    candidates.extend(_enumerate_tail_risks(world, solver, frontier, target, y_std, seed))

    # 5. Variance effects: interventions that change variability
    candidates.extend(_enumerate_variance_effects(world, solver, frontier, target, y_std, seed))

    # 6. Observational associations: partial correlations
    candidates.extend(_enumerate_observational_associations(world, frontier, target, n_mc, seed))

    # 7. Effect ranking: which ancestor has strongest effect on target
    candidates.extend(_enumerate_effect_ranking(world, solver, frontier, target, y_std, seed))

    # Filter by effect size threshold
    candidates = [
        c for c in candidates if c.effect_size >= EFFECT_THRESHOLDS.get(c.pattern_class, 0.10)
    ]

    # Compute salience scores
    for c in candidates:
        c.salience = _compute_salience(c, world, target)

    # Sort by salience descending
    candidates.sort(key=lambda c: c.salience, reverse=True)

    # Apply pattern caps
    candidates = _apply_pattern_caps(candidates)

    # Take top N
    candidates = candidates[:max_families]

    # Convert to SalienceFamily
    families = [
        SalienceFamily(
            family_id=f"f_{i}_{c.pattern_class}",
            key=c.family_key,
            atoms=tuple(c.atoms),
            salience=c.salience,
        )
        for i, c in enumerate(candidates)
    ]

    return SalienceMap(
        world_id=world.id,
        brief_target=target,
        families=families,
    )


# ---------------------------------------------------------------------------
# Enumeration: causal effects
# ---------------------------------------------------------------------------


def _enumerate_causal_effects(
    world: SCMWorld,
    solver: SCMSolver,
    frontier: list[str],
    target: str,
    y_std: float,
    seed: int,
) -> list[CandidateTruth]:
    """Enumerate ATEs for each ancestor -> target.

    Each family is ENRICHED with qualifier atoms:
    - Main atom: the ATE itself (material=True)
    - Heterogeneity atom: if ATE varies by some modifier (material=True)
    - Mediation atom: if effect operates through a mediator (material=False, bonus)

    This enables the anti-simplification scoring to operate:
    "X causes Y" covers 1 atom; "X causes Y, especially when Z is high,
    operating through M" covers 3 atoms and scores higher.
    """
    candidates = []
    dag = world.dag

    for x in frontier:
        try:
            x_samples = world.observational_distribution(x, n=10_000, seed=seed)
            v_lo = float(np.percentile(x_samples, 25))
            v_hi = float(np.percentile(x_samples, 75))
            if abs(v_hi - v_lo) < 1e-6:
                continue

            ate_val = solver.ate(x, target, v_hi, v_lo, seed=seed)
            effect_size = abs(ate_val) / y_std
            if effect_size < EFFECT_THRESHOLDS["causal_effect"]:
                continue

            direction = AssertionKind.POSITIVE if ate_val > 0 else AssertionKind.NEGATIVE
            main_spec = AtomicSpec(
                spec_id=f"ate_{x}_{target}",
                arms=(
                    QueryArm(label="hi", kind=QueryKind.INTERVENE, values={x: v_hi}),
                    QueryArm(label="lo", kind=QueryKind.INTERVENE, values={x: v_lo}),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target=target),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
                assertion=Assertion(kind=direction),
            )

            atoms = [
                FamilyAtom(atom_id=main_spec.spec_id, spec=main_spec, weight=1.0, material=True)
            ]

            # Enrich: look for strongest heterogeneity qualifier
            best_het = _find_strongest_heterogeneity(
                world, solver, x, target, v_hi, v_lo, frontier, seed
            )
            if best_het is not None:
                atoms.append(best_het)

            # Enrich: look for mediation qualifier
            best_med = _find_strongest_mediation(world, solver, x, target, v_hi, v_lo, dag, seed)
            if best_med is not None:
                atoms.append(best_med)

            candidates.append(
                CandidateTruth(
                    family_key=FamilyKey(
                        brief_target=target,
                        focus_signature=tuple(sorted([x, target])),
                        pattern_class="causal_effect",
                        scope_class="global",
                    ),
                    atoms=atoms,
                    effect_size=effect_size,
                    pattern_class="causal_effect",
                )
            )
        except Exception as e:
            logger.debug("Skipping causal effect %s->%s: %s", x, target, e)

    return candidates


def _find_strongest_heterogeneity(
    world: SCMWorld,
    solver: SCMSolver,
    x: str,
    target: str,
    v_hi: float,
    v_lo: float,
    frontier: list[str],
    seed: int,
) -> FamilyAtom | None:
    """Find the strongest heterogeneity qualifier for X->target."""
    best_range = 0.0
    best_atom = None

    for z in frontier:
        if z == x:
            continue
        try:
            result = solver.detect_interaction(
                treatment=x,
                outcome=target,
                modifier=z,
                v_high=v_hi,
                v_low=v_lo,
                seed=seed,
            )
            rel_range = result.get("relative_range", 0)
            if rel_range > best_range and rel_range > 0.10:
                best_range = rel_range
                z_samples = world.observational_distribution(z, n=5000, seed=seed)
                z_hi = float(np.percentile(z_samples, 75))
                z_lo = float(np.percentile(z_samples, 25))

                het_spec = AtomicSpec(
                    spec_id=f"het_{x}_{z}_{target}",
                    arms=(
                        QueryArm(
                            label="hi_zhi",
                            kind=QueryKind.INTERVENE,
                            values={x: v_hi},
                            condition_on={z: z_hi},
                        ),
                        QueryArm(
                            label="lo_zhi",
                            kind=QueryKind.INTERVENE,
                            values={x: v_lo},
                            condition_on={z: z_hi},
                        ),
                        QueryArm(
                            label="hi_zlo",
                            kind=QueryKind.INTERVENE,
                            values={x: v_hi},
                            condition_on={z: z_lo},
                        ),
                        QueryArm(
                            label="lo_zlo",
                            kind=QueryKind.INTERVENE,
                            values={x: v_lo},
                            condition_on={z: z_lo},
                        ),
                    ),
                    measurement=Measurement(kind=MeasurementKind.MEAN, target=target),
                    comparison=Comparison(kind=ComparisonKind.CONTRAST_DIFF),
                    assertion=Assertion(kind=AssertionKind.SIGN_FLIP, tolerance=0.05),
                )
                best_atom = FamilyAtom(
                    atom_id=het_spec.spec_id, spec=het_spec, weight=0.7, material=True
                )
        except Exception:
            continue

    return best_atom


def _find_strongest_mediation(
    world: SCMWorld,
    solver: SCMSolver,
    x: str,
    target: str,
    v_hi: float,
    v_lo: float,
    dag: nx.DiGraph,
    seed: int,
) -> FamilyAtom | None:
    """Find the strongest mediation path for X->target."""
    children_of_x = set(dag.successors(x))
    ancestors_of_target = nx.ancestors(dag, target)
    mediators = children_of_x & ancestors_of_target & set(world.observable_variables)

    best_frac = 0.0
    best_atom = None

    for m in mediators:
        try:
            result = solver.mediation_analysis(
                treatment=x,
                mediator=m,
                outcome=target,
                v_high=v_hi,
                v_low=v_lo,
                seed=seed,
            )
            frac = abs(result.get("fraction_mediated", 0))
            if frac > best_frac and frac > 0.15:
                best_frac = frac
                # Mediation atom: bonus (not material — discovering it is extra credit)
                med_spec = AtomicSpec(
                    spec_id=f"med_{x}_{m}_{target}",
                    arms=(
                        QueryArm(label="total", kind=QueryKind.INTERVENE, values={x: v_hi}),
                        QueryArm(label="base", kind=QueryKind.INTERVENE, values={x: v_lo}),
                    ),
                    measurement=Measurement(kind=MeasurementKind.MEAN, target=target),
                    comparison=Comparison(kind=ComparisonKind.PROPORTION),
                    assertion=Assertion(kind=AssertionKind.POSITIVE),
                )
                best_atom = FamilyAtom(
                    atom_id=med_spec.spec_id, spec=med_spec, weight=0.5, material=False
                )
        except Exception:
            continue

    return best_atom


# ---------------------------------------------------------------------------
# Enumeration: heterogeneity
# ---------------------------------------------------------------------------


def _enumerate_heterogeneity(
    world: SCMWorld,
    solver: SCMSolver,
    frontier: list[str],
    target: str,
    y_std: float,
    seed: int,
) -> list[CandidateTruth]:
    """Find treatment effects that vary by stratum of a modifier."""
    candidates = []

    for x in frontier:
        x_samples = world.observational_distribution(x, n=10_000, seed=seed)
        v_lo_x = float(np.percentile(x_samples, 25))
        v_hi_x = float(np.percentile(x_samples, 75))
        if abs(v_hi_x - v_lo_x) < 1e-6:
            continue

        for z in frontier:
            if z == x:
                continue
            try:
                result = solver.detect_interaction(
                    treatment=x,
                    outcome=target,
                    modifier=z,
                    v_high=v_hi_x,
                    v_low=v_lo_x,
                    seed=seed,
                )
                rel_range = result.get("relative_range", 0)
                if rel_range < EFFECT_THRESHOLDS["heterogeneity"]:
                    continue

                spec = AtomicSpec(
                    spec_id=f"het_{x}_{z}_{target}",
                    arms=(
                        QueryArm(
                            label="hi_hi",
                            kind=QueryKind.INTERVENE,
                            values={x: v_hi_x},
                            condition_on={
                                z: float(
                                    np.percentile(
                                        world.observational_distribution(z, n=5000, seed=seed), 75
                                    )
                                )
                            },
                        ),
                        QueryArm(
                            label="lo_hi",
                            kind=QueryKind.INTERVENE,
                            values={x: v_lo_x},
                            condition_on={
                                z: float(
                                    np.percentile(
                                        world.observational_distribution(z, n=5000, seed=seed), 75
                                    )
                                )
                            },
                        ),
                        QueryArm(
                            label="hi_lo",
                            kind=QueryKind.INTERVENE,
                            values={x: v_hi_x},
                            condition_on={
                                z: float(
                                    np.percentile(
                                        world.observational_distribution(z, n=5000, seed=seed), 25
                                    )
                                )
                            },
                        ),
                        QueryArm(
                            label="lo_lo",
                            kind=QueryKind.INTERVENE,
                            values={x: v_lo_x},
                            condition_on={
                                z: float(
                                    np.percentile(
                                        world.observational_distribution(z, n=5000, seed=seed), 25
                                    )
                                )
                            },
                        ),
                    ),
                    measurement=Measurement(kind=MeasurementKind.MEAN, target=target),
                    comparison=Comparison(kind=ComparisonKind.CONTRAST_DIFF),
                    assertion=Assertion(
                        kind=AssertionKind.SIGN_FLIP
                        if result.get("interaction_detected", False)
                        else AssertionKind.NEAR_ZERO,
                        tolerance=0.05,
                    ),
                )

                candidates.append(
                    CandidateTruth(
                        family_key=FamilyKey(
                            brief_target=target,
                            focus_signature=tuple(sorted([x, z, target])),
                            pattern_class="heterogeneity",
                            scope_class=f"by_{z}",
                        ),
                        atoms=[
                            FamilyAtom(atom_id=spec.spec_id, spec=spec, weight=1.0, material=True)
                        ],
                        effect_size=rel_range,
                        pattern_class="heterogeneity",
                    )
                )
            except Exception as e:
                logger.debug("Skipping heterogeneity %s|%s->%s: %s", x, z, target, e)

    return candidates


# ---------------------------------------------------------------------------
# Enumeration: mediation
# ---------------------------------------------------------------------------


def _enumerate_mediations(
    world: SCMWorld,
    solver: SCMSolver,
    frontier: list[str],
    target: str,
    y_std: float,
    seed: int,
) -> list[CandidateTruth]:
    """Find mediation effects: X -> M -> target."""
    candidates = []
    dag = world.dag

    for x in frontier:
        x_samples = world.observational_distribution(x, n=10_000, seed=seed)
        v_lo = float(np.percentile(x_samples, 25))
        v_hi = float(np.percentile(x_samples, 75))
        if abs(v_hi - v_lo) < 1e-6:
            continue

        # Find potential mediators: children of x that are ancestors of target
        children_of_x = set(dag.successors(x))
        ancestors_of_target = nx.ancestors(dag, target)
        mediators = children_of_x & ancestors_of_target & set(world.observable_variables)

        for m in mediators:
            try:
                result = solver.mediation_analysis(
                    treatment=x, mediator=m, outcome=target, v_high=v_hi, v_low=v_lo, seed=seed
                )
                frac = result.get("fraction_mediated", 0)
                if abs(frac) < EFFECT_THRESHOLDS["mediation"]:
                    continue

                spec = AtomicSpec(
                    spec_id=f"med_{x}_{m}_{target}",
                    arms=(
                        QueryArm(label="total", kind=QueryKind.INTERVENE, values={x: v_hi}),
                        QueryArm(label="base", kind=QueryKind.INTERVENE, values={x: v_lo}),
                    ),
                    measurement=Measurement(kind=MeasurementKind.MEAN, target=target),
                    comparison=Comparison(kind=ComparisonKind.PROPORTION),
                    assertion=Assertion(kind=AssertionKind.POSITIVE),
                )

                candidates.append(
                    CandidateTruth(
                        family_key=FamilyKey(
                            brief_target=target,
                            focus_signature=tuple(sorted([x, m, target])),
                            pattern_class="mediation",
                            scope_class=f"via_{m}",
                        ),
                        atoms=[
                            FamilyAtom(atom_id=spec.spec_id, spec=spec, weight=1.0, material=True)
                        ],
                        effect_size=abs(frac),
                        pattern_class="mediation",
                    )
                )
            except Exception as e:
                logger.debug("Skipping mediation %s->%s->%s: %s", x, m, target, e)

    return candidates


# ---------------------------------------------------------------------------
# Enumeration: tail risk
# ---------------------------------------------------------------------------


def _enumerate_tail_risks(
    world: SCMWorld,
    solver: SCMSolver,
    frontier: list[str],
    target: str,
    y_std: float,
    seed: int,
) -> list[CandidateTruth]:
    """Find interventions that change extreme outcome probability."""
    candidates = []
    y_samples = world.observational_distribution(target, n=50_000, seed=seed)
    p90 = float(np.percentile(y_samples, 90))

    for x in frontier:
        try:
            x_samples = world.observational_distribution(x, n=10_000, seed=seed)
            v_lo = float(np.percentile(x_samples, 25))
            v_hi = float(np.percentile(x_samples, 75))
            if abs(v_hi - v_lo) < 1e-6:
                continue

            y_hi = solver.interventional_samples(target, do={x: v_hi}, n=20_000, seed=seed)
            seed_lo = (seed + 7) if seed is not None else None
            y_lo = solver.interventional_samples(target, do={x: v_lo}, n=20_000, seed=seed_lo)

            p_tail_hi = float(np.mean(y_hi > p90))
            p_tail_lo = float(np.mean(y_lo > p90))
            tail_diff = abs(p_tail_hi - p_tail_lo)

            if tail_diff < EFFECT_THRESHOLDS["tail_risk"]:
                continue

            direction = AssertionKind.POSITIVE if p_tail_hi > p_tail_lo else AssertionKind.NEGATIVE
            spec = AtomicSpec(
                spec_id=f"tail_{x}_{target}",
                arms=(
                    QueryArm(label="hi", kind=QueryKind.INTERVENE, values={x: v_hi}),
                    QueryArm(label="lo", kind=QueryKind.INTERVENE, values={x: v_lo}),
                ),
                measurement=Measurement(
                    kind=MeasurementKind.TAIL_PROB, target=target, threshold=p90
                ),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
                assertion=Assertion(kind=direction),
            )

            candidates.append(
                CandidateTruth(
                    family_key=FamilyKey(
                        brief_target=target,
                        focus_signature=tuple(sorted([x, target])),
                        pattern_class="tail_risk",
                        scope_class="p90",
                    ),
                    atoms=[FamilyAtom(atom_id=spec.spec_id, spec=spec, weight=1.0, material=True)],
                    effect_size=tail_diff,
                    pattern_class="tail_risk",
                )
            )
        except Exception as e:
            logger.debug("Skipping tail risk %s->%s: %s", x, target, e)

    return candidates


# ---------------------------------------------------------------------------
# Enumeration: variance effects
# ---------------------------------------------------------------------------


def _enumerate_variance_effects(
    world: SCMWorld,
    solver: SCMSolver,
    frontier: list[str],
    target: str,
    y_std: float,
    seed: int,
) -> list[CandidateTruth]:
    """Find interventions that change outcome variability."""
    candidates = []
    y_base_var = float(y_std**2)

    for x in frontier:
        try:
            x_samples = world.observational_distribution(x, n=10_000, seed=seed)
            v_lo = float(np.percentile(x_samples, 25))
            v_hi = float(np.percentile(x_samples, 75))
            if abs(v_hi - v_lo) < 1e-6:
                continue

            y_hi = solver.interventional_samples(target, do={x: v_hi}, n=20_000, seed=seed)
            seed_lo = (seed + 11) if seed is not None else None
            y_lo = solver.interventional_samples(target, do={x: v_lo}, n=20_000, seed=seed_lo)

            var_hi = float(np.var(y_hi))
            var_lo = float(np.var(y_lo))
            var_diff = abs(var_hi - var_lo) / max(y_base_var, 1e-6)

            if var_diff < EFFECT_THRESHOLDS["variance_effect"]:
                continue

            direction = AssertionKind.POSITIVE if var_hi > var_lo else AssertionKind.NEGATIVE
            spec = AtomicSpec(
                spec_id=f"var_{x}_{target}",
                arms=(
                    QueryArm(label="hi", kind=QueryKind.INTERVENE, values={x: v_hi}),
                    QueryArm(label="lo", kind=QueryKind.INTERVENE, values={x: v_lo}),
                ),
                measurement=Measurement(kind=MeasurementKind.VARIANCE, target=target),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
                assertion=Assertion(kind=direction),
            )

            candidates.append(
                CandidateTruth(
                    family_key=FamilyKey(
                        brief_target=target,
                        focus_signature=tuple(sorted([x, target])),
                        pattern_class="variance_effect",
                        scope_class="global",
                    ),
                    atoms=[FamilyAtom(atom_id=spec.spec_id, spec=spec, weight=1.0, material=True)],
                    effect_size=var_diff,
                    pattern_class="variance_effect",
                )
            )
        except Exception as e:
            logger.debug("Skipping variance effect %s->%s: %s", x, target, e)

    return candidates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_salience(candidate: CandidateTruth, world: SCMWorld, target: str) -> float:
    """Compute salience score for a candidate truth.

    Combines effect size, proximity to target, and actionability.
    """
    dag = world.dag
    focus_vars = set(candidate.family_key.focus_signature) - {target}

    # Proximity: average shortest path to target
    proximities = []
    for v in focus_vars:
        try:
            path_len = nx.shortest_path_length(dag, v, target)
            proximities.append(1.0 / (1.0 + path_len))
        except nx.NetworkXNoPath:
            proximities.append(0.1)
    proximity = sum(proximities) / max(len(proximities), 1)

    # Combine: 50% effect size + 30% proximity + 20% pattern novelty
    pattern_novelty = {
        "causal_effect": 0.3,
        "observational_association": 0.5,
        "heterogeneity": 0.7,
        "interaction": 0.7,
        "mediation": 0.6,
        "tail_risk": 0.8,
        "variance_effect": 0.8,
        "effect_ranking": 0.4,
    }.get(candidate.pattern_class, 0.5)

    effect_norm = min(candidate.effect_size / 0.5, 1.0)  # normalize to [0,1]
    return 0.50 * effect_norm + 0.30 * proximity + 0.20 * pattern_novelty


def _apply_pattern_caps(candidates: list[CandidateTruth]) -> list[CandidateTruth]:
    """Apply per-pattern-class caps to candidate list."""
    counts: dict[str, int] = {}
    result = []
    for c in candidates:
        cap = PATTERN_CAPS.get(c.pattern_class, 4)
        current = counts.get(c.pattern_class, 0)
        if current < cap:
            result.append(c)
            counts[c.pattern_class] = current + 1
    return result


# ---------------------------------------------------------------------------
# Enumeration: observational associations
# ---------------------------------------------------------------------------


def _enumerate_observational_associations(
    world: SCMWorld,
    frontier: list[str],
    target: str,
    n_mc: int,
    seed: int,
) -> list[CandidateTruth]:
    """Find significant partial correlations between ancestors and target.

    These are OBSERVATIONAL claims: "X and Y are correlated controlling for Z".
    This is first-class observational science, not interventional.
    """
    candidates = []
    df = world.sample(n=n_mc, seed=seed)

    for x in frontier:
        if x not in df.columns or target not in df.columns:
            continue
        # Simple correlation first
        raw_corr = abs(float(df[x].corr(df[target])))
        if raw_corr < EFFECT_THRESHOLDS["observational_association"]:
            continue

        # Find conditioning set: other ancestors that could confound
        other_ancestors = [z for z in frontier if z != x]
        cond_set = tuple(other_ancestors[:3])  # limit to 3 for tractability

        # Compute partial correlation
        if cond_set:
            from numpy.linalg import lstsq

            cols = [x, target] + list(cond_set)
            sub = df[cols].dropna()
            if len(sub) < 50:
                continue
            Z = sub[list(cond_set)].values
            Z = np.column_stack([Z, np.ones(len(Z))])
            x_vals = sub[x].values
            y_vals = sub[target].values
            coef_x, _, _, _ = lstsq(Z, x_vals, rcond=None)
            coef_y, _, _, _ = lstsq(Z, y_vals, rcond=None)
            resid_x = x_vals - Z @ coef_x
            resid_y = y_vals - Z @ coef_y
            denom = np.std(resid_x) * np.std(resid_y)
            if denom < 1e-10:
                continue
            pcorr = float(np.corrcoef(resid_x, resid_y)[0, 1])
        else:
            pcorr = float(df[x].corr(df[target]))

        if abs(pcorr) < EFFECT_THRESHOLDS["observational_association"]:
            continue

        direction = AssertionKind.POSITIVE if pcorr > 0 else AssertionKind.NEGATIVE
        spec = AtomicSpec(
            spec_id=f"pcor_{x}_{target}",
            arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
            measurement=Measurement(
                kind=MeasurementKind.PARTIAL_CORRELATION,
                lhs=x,
                rhs=target,
                cond_set=cond_set,
            ),
            comparison=Comparison(kind=ComparisonKind.IDENTITY),
            assertion=Assertion(kind=direction),
        )

        candidates.append(
            CandidateTruth(
                family_key=FamilyKey(
                    brief_target=target,
                    focus_signature=tuple(sorted([x, target])),
                    pattern_class="observational_association",
                    scope_class=f"controlling_{','.join(cond_set)}" if cond_set else "marginal",
                ),
                atoms=[FamilyAtom(atom_id=spec.spec_id, spec=spec, weight=1.0, material=True)],
                effect_size=abs(pcorr),
                pattern_class="observational_association",
            )
        )

    return candidates


# ---------------------------------------------------------------------------
# Enumeration: effect ranking
# ---------------------------------------------------------------------------


def _enumerate_effect_ranking(
    world: SCMWorld,
    solver: SCMSolver,
    frontier: list[str],
    target: str,
    y_std: float,
    seed: int,
) -> list[CandidateTruth]:
    """Find the ranking of ancestor effects on target.

    Produces one family: "which variable has the strongest effect on Y?"
    This is a meta-claim that a good investigator should make.
    """
    if len(frontier) < 2:
        return []

    effect_sizes = {}
    for x in frontier:
        try:
            x_samples = world.observational_distribution(x, n=10_000, seed=seed)
            v_lo = float(np.percentile(x_samples, 25))
            v_hi = float(np.percentile(x_samples, 75))
            if abs(v_hi - v_lo) < 1e-6:
                continue
            ate_val = solver.ate(x, target, v_hi, v_lo, seed=seed)
            effect_sizes[x] = abs(ate_val) / y_std
        except Exception:
            continue

    if len(effect_sizes) < 2:
        return []

    # Sort by effect size descending
    ranked = sorted(effect_sizes.items(), key=lambda kv: kv[1], reverse=True)
    top_2 = ranked[:2]

    # Only create ranking if the gap between #1 and #2 is meaningful
    gap = top_2[0][1] - top_2[1][1]
    if gap < EFFECT_THRESHOLDS["effect_ranking"]:
        return []

    # Create a ranking spec: compare top 2-3 effects
    top_vars = [v for v, _ in ranked[:3]]
    arms = []
    for v in top_vars:
        x_samples = world.observational_distribution(v, n=5000, seed=seed)
        v_hi = float(np.percentile(x_samples, 75))
        v_lo = float(np.percentile(x_samples, 25))
        arms.append(QueryArm(label=f"ate_{v}", kind=QueryKind.INTERVENE, values={v: v_hi}))

    spec = AtomicSpec(
        spec_id=f"rank_{'_'.join(top_vars)}_{target}",
        arms=tuple(arms),
        measurement=Measurement(kind=MeasurementKind.MEAN, target=target),
        comparison=Comparison(kind=ComparisonKind.RANKING),
        assertion=Assertion(
            kind=AssertionKind.RANK_ORDER,
            order=tuple(f"ate_{v}" for v in top_vars),
        ),
    )

    return [
        CandidateTruth(
            family_key=FamilyKey(
                brief_target=target,
                focus_signature=tuple(sorted(top_vars + [target])),
                pattern_class="effect_ranking",
                scope_class="global",
            ),
            atoms=[FamilyAtom(atom_id=spec.spec_id, spec=spec, weight=1.0, material=True)],
            effect_size=gap,
            pattern_class="effect_ranking",
        )
    ]


__all__ = ["build_salience_map", "CandidateTruth"]
