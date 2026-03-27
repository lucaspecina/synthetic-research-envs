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
class PanelConfig:
    """Configuration for panel / longitudinal structure.

    Transforms IID samples into data that looks like it was collected
    across multiple sites over multiple measurement waves.  Adds
    within-site clustering (random effects), temporal drift, site
    dropout, and proxy (nuisance) columns.
    """

    n_sites: int = 8
    """Number of collection sites / clusters."""

    n_waves: int = 3
    """Number of measurement waves (time periods)."""

    site_effect_std: float = 0.3
    """Std of site random intercept as fraction of variable std.
    Loading varies per variable (multiplied by a per-var factor in [0.5, 1.5]).
    0.3 yields ICC ~ 0.08 on average."""

    wave_trend: float = 0.0
    """Linear drift per wave as fraction of variable std. 0 = none."""

    dropout_rate: float = 0.10
    """Per-wave probability that a site drops out (cumulative)."""

    n_proxy_columns: int = 2
    """Number of correlated proxy / nuisance columns to inject."""

    proxy_noise_std: float = 0.5
    """Noise level for proxy columns relative to source std."""

    seed: int = 0


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
    structural_cols: list[str] | None = None,
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
        structural_cols: Extra columns to skip (e.g. site_id, wave, proxies).
        seed: Random seed.

    Returns:
        New DataFrame with realistic imperfections applied.
    """
    result = df.copy()
    rng = np.random.default_rng(seed)
    target = target or world.variables[-1]
    skip = {"sample_id"} | set(structural_cols or [])
    data_cols = [c for c in result.columns if c not in skip]

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


def apply_panel_structure(
    df: pd.DataFrame,
    world: SCMWorld,
    config: PanelConfig,
    target: str | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Transform IID samples into panel-structured data.

    Assigns rows to (site, wave) cells, adds site-level random effects
    for within-cluster correlation, applies wave trend and site dropout,
    and injects proxy columns.

    Returns:
        (panel_df, proxy_column_names).  panel_df has ``site_id`` and
        ``wave`` as the first two columns plus any proxy columns.
    """
    rng = np.random.default_rng(config.seed)
    target = target or world.variables[-1]
    data_cols = [c for c in df.columns if c != "sample_id"]
    n = len(df)
    n_cells = config.n_sites * config.n_waves

    # --- 1. Assign rows to (site, wave) cells ---
    indices = rng.permutation(n)
    site_ids = np.empty(n, dtype=object)
    wave_ids = np.empty(n, dtype=int)
    for i, idx in enumerate(indices):
        cell = i % n_cells
        site_ids[idx] = f"S{(cell % config.n_sites) + 1:02d}"
        wave_ids[idx] = cell // config.n_sites

    result = df.copy()
    result["site_id"] = site_ids
    result["wave"] = wave_ids

    # --- 2. Site random effects (variable-specific loadings) ---
    var_loadings = {
        col: rng.uniform(0.5, 1.5) for col in data_cols
    }
    for s in range(config.n_sites):
        site_label = f"S{s + 1:02d}"
        site_mask = result["site_id"] == site_label
        for col in data_cols:
            col_std = df[col].std()
            if col_std <= 0 or pd.isna(col_std):
                continue
            effect = rng.normal(
                0, config.site_effect_std * var_loadings[col] * col_std
            )
            result.loc[site_mask, col] += effect

    # --- 3. Wave trend ---
    if config.wave_trend != 0:
        for col in data_cols:
            col_std = df[col].std()
            if col_std <= 0 or pd.isna(col_std):
                continue
            for w in range(config.n_waves):
                wave_mask = result["wave"] == w
                result.loc[wave_mask, col] += config.wave_trend * w * col_std

    # --- 4. Clip to variable ranges ---
    for col in data_cols:
        meta = world.variable_meta.get(col)
        if meta:
            result[col] = result[col].clip(meta.range[0], meta.range[1])

    # --- 5. Site dropout ---
    if config.dropout_rate > 0:
        for s in range(config.n_sites):
            site_label = f"S{s + 1:02d}"
            dropped = False
            for w in range(1, config.n_waves):
                if dropped or rng.random() < config.dropout_rate:
                    dropped = True
                    mask = (result["site_id"] == site_label) & (result["wave"] == w)
                    for col in data_cols:
                        if col != target:
                            result.loc[mask, col] = np.nan

    # --- 6. Proxy columns ---
    proxy_names: list[str] = []
    if config.n_proxy_columns > 0:
        result, proxy_names = _add_proxy_columns(
            result, world, config.n_proxy_columns,
            config.proxy_noise_std, target, rng,
        )

    # --- 7. Reorder columns ---
    front = ["site_id", "wave"]
    rest = [c for c in result.columns if c not in front]
    result = result[front + rest]
    result = result.sort_values(["site_id", "wave"]).reset_index(drop=True)

    return result, proxy_names


def _add_proxy_columns(
    df: pd.DataFrame,
    world: SCMWorld,
    n_proxies: int,
    noise_std: float,
    target: str,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, list[str]]:
    """Add correlated proxy / nuisance columns.

    Each proxy is ``alpha * source + noise`` where source is a randomly
    selected SCM variable and alpha ~ U(0.3, 0.9).
    """
    _SUFFIXES = ["_index", "_reading", "_score", "_level", "_measure"]
    obs = [v for v in world.observable_variables if v != target]
    if not obs:
        return df, []

    sources = list(rng.choice(obs, size=min(n_proxies, len(obs)), replace=False))
    while len(sources) < n_proxies:
        sources.append(rng.choice(obs))

    proxy_names: list[str] = []
    for src in sources:
        alpha = float(rng.uniform(0.3, 0.9))
        col_std = df[src].std()
        if pd.isna(col_std) or col_std <= 0:
            continue
        noise = rng.normal(0, noise_std * col_std, size=len(df))
        values = alpha * df[src].values + noise
        meta = world.variable_meta.get(src)
        if meta:
            values = np.clip(values, meta.range[0], meta.range[1])

        suffix = rng.choice(_SUFFIXES)
        name = f"{src}{suffix}"
        # Avoid collision (bounded attempts)
        for _attempt in range(20):
            if name not in df.columns and name not in proxy_names:
                break
            suffix = rng.choice(_SUFFIXES)
            name = f"{src}_{_attempt}{suffix}"
        if name in df.columns or name in proxy_names:
            continue  # skip this proxy if still colliding
        proxy_names.append(name)

        # Insert at random position (not always at the end)
        pos = int(rng.integers(2, len(df.columns)))
        df.insert(pos, name, values)

    return df, proxy_names


def multi_dataset_sample(
    world: SCMWorld,
    config: RealisticDataConfig | None = None,
    target: str | None = None,
    n: int = 500,
    panel: PanelConfig | None = None,
) -> list[DatasetArtifact]:
    """Generate multi-source realistic datasets from an SCMWorld.

    Produces 2-3 DatasetArtifacts representing different views of the same
    study.  When *panel* is provided, the **master sample** gets panel
    structure (site_id, wave, proxy columns, informative missingness) and
    the secondary artifacts are row/column subsets of that master -- so
    they share observations and feel like parts of one investigation.

    Without *panel*, falls back to the legacy behaviour where each
    artifact is sampled independently.
    """
    config = config or RealisticDataConfig()
    target = target or world.variables[-1]
    primary_cols, secondary_cols = _split_columns(world, target)

    # ----------------------------------------------------------------
    # Panel path: shared study frame
    # ----------------------------------------------------------------
    if panel is not None:
        return _multi_dataset_panel(
            world, config, panel, target, n, primary_cols, secondary_cols,
        )

    # ----------------------------------------------------------------
    # Legacy path (no panel): independent samples per artifact
    # ----------------------------------------------------------------
    artifacts: list[DatasetArtifact] = []

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

    # --- Detailed: small, specialized, high precision ---
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


def _multi_dataset_panel(
    world: SCMWorld,
    config: RealisticDataConfig,
    panel: PanelConfig,
    target: str,
    n: int,
    primary_cols: list[str],
    secondary_cols: list[str],
) -> list[DatasetArtifact]:
    """Panel path: one master sample, artifacts as views."""
    # 1. Sample ONE master frame with all observable variables
    master_n = max(n, 500)
    obs = world.observable_variables
    master = world.sample(n=master_n, seed=config.seed)
    master = master[[c for c in master.columns if c in obs]]
    master.insert(0, "sample_id", range(1, master_n + 1))

    # 2. Apply panel structure to master
    panel_df, proxy_names = apply_panel_structure(master, world, panel, target)

    # Structural columns to skip in apply_realism
    struct_cols = ["sample_id", "site_id", "wave"] + proxy_names

    # 3. Background: full panel frame, moderate noise + missing
    bg_df = panel_df.copy()
    scm_cols = [c for c in bg_df.columns if c in obs]
    bg_df = apply_realism(
        bg_df,
        world,
        noise_fraction=config.noise_fraction * 0.3,
        missing_rate=config.missing_rate * 3.0,  # higher for panel (target: 15%)
        missing_mechanism=config.missing_mechanism,
        outlier_fraction=config.outlier_fraction * 0.5,
        outlier_magnitude=config.outlier_magnitude,
        target=target,
        rounding=config.rounding,
        structural_cols=struct_cols,
        seed=config.seed + 1000,
    )
    artifacts: list[DatasetArtifact] = [
        DatasetArtifact(
            name="background_records",
            data=bg_df,
            source="multi-site longitudinal study / administrative records",
            description=_describe(bg_df),
        )
    ]

    # 4. Field survey: subset of rows from post-panel data, flat view
    rng = np.random.default_rng(config.seed + 5000)
    survey_n = max(n // 3, 50)
    survey_ids = sorted(rng.choice(master_n, size=min(survey_n, master_n), replace=False))

    overlap = secondary_cols[:1] if secondary_cols else []
    survey_want = ["sample_id"] + primary_cols + overlap
    # Use post-panel values (site effects baked in) but drop panel columns
    survey_avail = [c for c in survey_want if c in panel_df.columns]
    survey_df = panel_df.iloc[survey_ids][survey_avail].copy().reset_index(drop=True)
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
    artifacts.append(
        DatasetArtifact(
            name="field_survey",
            data=survey_df,
            source="field survey / direct measurement campaign",
            description=_describe(survey_df),
        )
    )

    # 5. Detailed: smaller subset, secondary cols + target
    if len(secondary_cols) >= 2:
        detail_n = max(n // 10, 20)
        detail_ids = sorted(
            rng.choice(master_n, size=min(detail_n, master_n), replace=False)
        )
        seen: set[str] = set()
        detail_cols_ordered: list[str] = ["sample_id"]
        for c in secondary_cols + [target]:
            if c not in seen and c in master.columns:
                detail_cols_ordered.append(c)
                seen.add(c)

        detail_avail = [c for c in detail_cols_ordered if c in panel_df.columns]
        detail_df = panel_df.iloc[detail_ids][detail_avail].copy()
        detail_df = detail_df.reset_index(drop=True)
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
    _STRUCTURAL = {"sample_id", "site_id", "wave"}
    cols = [c for c in df.columns if c not in _STRUCTURAL]
    n_rows = len(df)
    n_cols = len(cols)

    # Vary the opening phrase based on data characteristics
    n_sites = int(df["site_id"].nunique()) if "site_id" in df.columns else 0
    n_waves = int(df["wave"].nunique()) if "wave" in df.columns else 0

    if n_sites > 0 and n_waves > 1:
        desc = (
            f"Panel dataset: {n_rows} records from {n_sites} sites "
            f"across {n_waves} measurement waves. "
            f"{n_cols} variables measured."
        )
    elif n_sites > 0:
        desc = (
            f"Cross-sectional survey from {n_sites} collection sites. "
            f"{n_rows} records, {n_cols} variables."
        )
    else:
        desc = f"Dataset with {n_rows} observations and {n_cols} variables."

    # Report missing data if significant
    total_cells = n_rows * n_cols
    missing_cells = df[cols].isna().sum().sum()
    missing_pct = (missing_cells / total_cells * 100) if total_cells > 0 else 0
    if missing_pct > 5:
        desc += f" Incomplete records: {missing_pct:.0f}% missing values."
    elif missing_pct > 1:
        desc += f" Some missing values ({missing_pct:.0f}%)."

    return desc


__all__ = [
    "DatasetArtifact",
    "PanelConfig",
    "RealisticDataConfig",
    "apply_panel_structure",
    "apply_realism",
    "multi_dataset_sample",
    "realistic_sample",
]
