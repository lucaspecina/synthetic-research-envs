"""Realistic dataset generation from SCMWorld.

Transforms clean Monte Carlo samples into what a real researcher would see:
measurement noise, limited precision, missing data, outliers, and
multi-source dataset splits.

SCMWorld.sample() produces "perfect" data -- exact values from the structural
equations plus irreducible noise. Real data has additional imperfections from
the measurement process. This module adds those.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
import numpy as np
import pandas as pd

from sreg.world.scm import SCMWorld


@dataclass
class RealisticDataConfig:
    """Configuration for realistic data transformations.

    Controls measurement noise, rounding precision, missing data,
    and outlier injection. All rates are fractions in [0, 1].
    """

    noise_fraction: float = 0.05
    """Gaussian noise as fraction of each variable's empirical std."""

    missing_rate: float = 0.05
    """Base probability of a value being missing."""

    missing_mechanism: str = "mar"
    """'mcar' (uniform random) or 'mar' (depends on parent values)."""

    outlier_fraction: float = 0.01
    """Fraction of observations replaced with extreme values."""

    outlier_magnitude: float = 3.0
    """Outliers are placed this many std from the mean."""

    rounding: dict[str, int] | None = None
    """Override decimal places per variable. Auto-inferred if None."""

    seed: int = 0
    """Random seed for reproducibility."""


@dataclass
class DatasetArtifact:
    """A dataset with metadata, representing one data source."""

    name: str
    data: pd.DataFrame
    source: str
    description: str


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def apply_realism(
    df: pd.DataFrame,
    world: SCMWorld,
    *,
    noise_fraction: float = 0.05,
    missing_rate: float = 0.05,
    missing_mechanism: str = "mar",
    outlier_fraction: float = 0.01,
    outlier_magnitude: float = 3.0,
    target: str | None = None,
    rounding: dict[str, int] | None = None,
    seed: int = 0,
) -> pd.DataFrame:
    """Apply realistic measurement imperfections to clean SCM samples.

    Order: noise -> outliers -> rounding -> missing.
    Missing is last so NaN doesn't interfere with std calculations.
    Rounding is after outliers so outliers get rounded too.

    Args:
        df: Clean DataFrame from SCMWorld.sample().
        world: The SCM (used for graph structure in MAR + variable metadata).
        noise_fraction: Gaussian noise as fraction of variable std.
        missing_rate: Base missing probability.
        missing_mechanism: 'mcar' or 'mar'.
        outlier_fraction: Fraction of outlier observations.
        outlier_magnitude: Outlier distance in std deviations.
        target: Variable to protect from missing data. Last in topo order if None.
        rounding: Override decimal places. Auto-inferred if None.
        seed: Random seed.

    Returns:
        New DataFrame with realistic imperfections applied.
    """
    result = df.copy()
    rng = np.random.default_rng(seed)
    target = target or world.variables[-1]
    data_cols = [c for c in result.columns if c != "sample_id"]

    result = _apply_noise(result, data_cols, world, noise_fraction, rng)
    result = _apply_outliers(result, data_cols, outlier_fraction, outlier_magnitude, rng)
    result = _apply_rounding(result, data_cols, world, rounding)
    result = _apply_missing(
        result, data_cols, world, missing_rate, missing_mechanism, target, rng
    )

    return result


def realistic_sample(
    world: SCMWorld,
    n: int = 500,
    *,
    target: str | None = None,
    noise_fraction: float = 0.05,
    missing_rate: float = 0.05,
    missing_mechanism: str = "mar",
    outlier_fraction: float = 0.01,
    outlier_magnitude: float = 3.0,
    rounding: dict[str, int] | None = None,
    seed: int = 0,
) -> pd.DataFrame:
    """Sample from SCMWorld and apply realistic imperfections in one step.

    Convenience wrapper: world.sample() + apply_realism().
    """
    df = world.sample(n=n, seed=seed)
    return apply_realism(
        df,
        world,
        noise_fraction=noise_fraction,
        missing_rate=missing_rate,
        missing_mechanism=missing_mechanism,
        outlier_fraction=outlier_fraction,
        outlier_magnitude=outlier_magnitude,
        target=target,
        rounding=rounding,
        seed=seed + 100,
    )


def multi_dataset_sample(
    world: SCMWorld,
    config: RealisticDataConfig | None = None,
    target: str | None = None,
    n: int = 500,
) -> list[DatasetArtifact]:
    """Generate multi-source realistic datasets from an SCMWorld.

    Produces 2-3 DatasetArtifacts simulating independent data collection
    efforts with different quality, coverage, and size -- like what a real
    researcher would piece together.

    Artifacts:
        1. background_records: Large, few variables, low noise, some missing.
        2. field_survey: Medium, more variables, moderate noise + missing.
        3. detailed_analysis: Small, specialized variables, high precision.
           (Only if >= 2 secondary variables exist.)

    Each artifact is sampled independently (different seed), not sliced from
    the same pool.
    """
    config = config or RealisticDataConfig()
    target = target or world.variables[-1]
    primary_cols, secondary_cols = _split_columns(world, target)

    artifacts = []

    # --- Background: large, primary columns, low noise ---
    bg_n = max(n, 500)
    bg_df = world.sample(n=bg_n, seed=config.seed)
    bg_df = bg_df[primary_cols]
    bg_df = apply_realism(
        bg_df,
        world,
        noise_fraction=config.noise_fraction * 0.3,
        missing_rate=config.missing_rate * 0.5,
        missing_mechanism=config.missing_mechanism,
        outlier_fraction=config.outlier_fraction * 0.5,
        outlier_magnitude=config.outlier_magnitude,
        target=target,
        rounding=config.rounding,
        seed=config.seed + 1000,
    )
    bg_df.insert(0, "sample_id", range(1, len(bg_df) + 1))
    artifacts.append(
        DatasetArtifact(
            name="background_records",
            data=bg_df,
            source="historical records / administrative database",
            description=_describe(bg_df),
        )
    )

    # --- Field survey: medium, primary + overlap, moderate noise ---
    survey_n = max(n // 3, 50)
    overlap = secondary_cols[:1] if secondary_cols else []
    survey_cols = primary_cols + overlap
    survey_df = world.sample(n=survey_n, seed=config.seed + 10000)
    survey_df = survey_df[survey_cols]
    survey_df = apply_realism(
        survey_df,
        world,
        noise_fraction=config.noise_fraction,
        missing_rate=config.missing_rate,
        missing_mechanism=config.missing_mechanism,
        outlier_fraction=config.outlier_fraction,
        outlier_magnitude=config.outlier_magnitude,
        target=target,
        rounding=config.rounding,
        seed=config.seed + 2000,
    )
    survey_df.insert(0, "sample_id", range(1, len(survey_df) + 1))
    artifacts.append(
        DatasetArtifact(
            name="field_survey",
            data=survey_df,
            source="field survey / direct measurement campaign",
            description=_describe(survey_df),
        )
    )

    # --- Detailed: small, specialized, high precision (only if enough vars) ---
    if len(secondary_cols) >= 2:
        detail_n = max(n // 10, 20)
        seen: set[str] = set()
        detail_cols: list[str] = []
        for c in secondary_cols + [target]:
            if c not in seen:
                detail_cols.append(c)
                seen.add(c)

        detail_df = world.sample(n=detail_n, seed=config.seed + 20000)
        detail_df = detail_df[detail_cols]
        detail_df = apply_realism(
            detail_df,
            world,
            noise_fraction=config.noise_fraction * 0.2,
            missing_rate=0.0,
            outlier_fraction=0.0,
            target=target,
            rounding=config.rounding,
            seed=config.seed + 3000,
        )
        detail_df.insert(0, "sample_id", range(1, len(detail_df) + 1))
        artifacts.append(
            DatasetArtifact(
                name="detailed_analysis",
                data=detail_df,
                source="detailed laboratory / specialist analysis",
                description=_describe(detail_df),
            )
        )

    return artifacts


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _split_columns(
    world: SCMWorld,
    target: str,
) -> tuple[list[str], list[str]]:
    """Split variables into primary (close to target) and secondary (far)."""
    undirected = world.dag.to_undirected()
    distances: dict[str, int] = {}
    for var in world.variables:
        if var == target:
            continue
        try:
            distances[var] = nx.shortest_path_length(undirected, var, target)
        except nx.NetworkXNoPath:
            distances[var] = 999

    sorted_vars = sorted(distances.keys(), key=lambda v: distances[v])
    mid = max(len(sorted_vars) // 2, 1)

    primary = sorted_vars[:mid] + [target]
    secondary = sorted_vars[mid:]
    return primary, secondary


def _apply_noise(
    df: pd.DataFrame,
    columns: list[str],
    world: SCMWorld,
    noise_fraction: float,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Add Gaussian measurement noise proportional to each variable's std."""
    if noise_fraction <= 0:
        return df
    for col in columns:
        if col not in df.columns:
            continue
        col_std = df[col].std()
        if col_std > 0:
            noise = rng.normal(0, noise_fraction * col_std, size=len(df))
            values = df[col].values + noise
            meta = world.variable_meta.get(col)
            if meta:
                values = np.clip(values, meta.range[0], meta.range[1])
            df[col] = values
    return df


def _apply_rounding(
    df: pd.DataFrame,
    columns: list[str],
    world: SCMWorld,
    overrides: dict[str, int] | None,
) -> pd.DataFrame:
    """Round values to realistic precision."""
    overrides = overrides or {}
    for col in columns:
        if col not in df.columns:
            continue
        if col in overrides:
            decimals = overrides[col]
        else:
            decimals = _infer_precision(df[col], world.variable_meta.get(col))
        df[col] = df[col].round(decimals)
    return df


def _infer_precision(series: pd.Series, meta=None) -> int:
    """Infer decimal places from data range or variable metadata."""
    if meta and meta.range:
        range_width = abs(meta.range[1] - meta.range[0])
    else:
        range_width = series.max() - series.min()
        if pd.isna(range_width):
            return 2

    if range_width > 100:
        return 0
    if range_width > 10:
        return 1
    if range_width > 1:
        return 2
    return 3


def _apply_missing(
    df: pd.DataFrame,
    columns: list[str],
    world: SCMWorld,
    missing_rate: float,
    mechanism: str,
    target: str,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Apply missing data (NaN). Target is never made missing."""
    if missing_rate <= 0:
        return df

    for col in columns:
        if col not in df.columns or col == target:
            continue

        if mechanism == "mcar":
            mask = rng.random(len(df)) < missing_rate
        elif mechanism == "mar":
            parents = world.parents(col) if col in world.graph else []
            probs = np.full(len(df), missing_rate)
            for parent in parents:
                if parent not in df.columns:
                    continue
                parent_vals = df[parent].values.astype(float)
                valid = ~np.isnan(parent_vals)
                if valid.sum() == 0:
                    continue
                p_median = np.nanmedian(parent_vals)
                p_std = np.nanstd(parent_vals)
                if p_std > 0:
                    z_scores = np.abs((parent_vals - p_median) / p_std)
                    probs = np.where(
                        valid & (z_scores > 1.5), probs * 2, probs
                    )
            probs = np.clip(probs, 0, 0.5)
            mask = rng.random(len(df)) < probs
        else:
            raise ValueError(f"Unknown missing mechanism: {mechanism}")

        df.loc[mask, col] = np.nan

    return df


def _apply_outliers(
    df: pd.DataFrame,
    columns: list[str],
    outlier_fraction: float,
    outlier_magnitude: float,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Inject occasional outliers (extreme values)."""
    if outlier_fraction <= 0:
        return df
    for col in columns:
        if col not in df.columns:
            continue
        n_outliers = max(int(len(df) * outlier_fraction), 0)
        if n_outliers == 0:
            continue
        col_std = df[col].std()
        col_mean = df[col].mean()
        if pd.isna(col_std) or col_std == 0:
            continue
        indices = rng.choice(len(df), size=n_outliers, replace=False)
        directions = rng.choice([-1, 1], size=n_outliers)
        outlier_vals = col_mean + directions * outlier_magnitude * col_std
        for i, idx in enumerate(indices):
            df.iat[idx, df.columns.get_loc(col)] = outlier_vals[i]
    return df


def _describe(df: pd.DataFrame) -> str:
    """Generate a human-readable description for a dataset artifact."""
    cols = [c for c in df.columns if c != "sample_id"]
    n_rows = len(df)
    total_cells = n_rows * len(cols)
    missing_cells = df[cols].isna().sum().sum()
    missing_pct = (missing_cells / total_cells * 100) if total_cells > 0 else 0

    desc = f"Dataset with {n_rows} samples. Columns: {', '.join(cols)}."
    if missing_pct > 1:
        desc += f" Missing data: {missing_pct:.0f}%."
    return desc


__all__ = [
    "DatasetArtifact",
    "RealisticDataConfig",
    "apply_realism",
    "multi_dataset_sample",
    "realistic_sample",
]
