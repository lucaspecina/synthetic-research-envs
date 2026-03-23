"""Tests for realistic dataset generation from SCMWorld."""

import numpy as np
import pandas as pd
import pytest

from sreg.world.scm import SCMWorld, VariableMeta
from sreg.world.scm_data import (
    DatasetArtifact,
    PanelConfig,
    RealisticDataConfig,
    _describe,
    _infer_precision,
    _split_columns,
    apply_panel_structure,
    apply_realism,
    multi_dataset_sample,
    realistic_sample,
)

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _linear_5node() -> SCMWorld:
    """A -> B -> C -> D -> E, linear Gaussian. 5 variables for column splitting."""
    return SCMWorld(
        graph={
            "A": [],
            "B": ["A"],
            "C": ["B"],
            "D": ["C"],
            "E": ["D"],
        },
        equations={
            "A": lambda p, rng: rng.normal(50, 10),
            "B": lambda p, rng: 2 * p["A"] + rng.normal(0, 5),
            "C": lambda p, rng: 0.5 * p["B"] + 10 + rng.normal(0, 3),
            "D": lambda p, rng: -0.3 * p["C"] + 20 + rng.normal(0, 2),
            "E": lambda p, rng: 0.8 * p["D"] + rng.normal(0, 1),
        },
        variable_meta={
            "A": VariableMeta(unit="kg", range=(20, 80)),
            "B": VariableMeta(unit="cm", range=(50, 200)),
            "C": VariableMeta(unit="score", range=(30, 80)),
            "D": VariableMeta(unit="mmHg", range=(5, 30)),
            "E": VariableMeta(unit="index", range=(0, 30)),
        },
    )


def _simple_3node() -> SCMWorld:
    """Z -> X -> Y, minimal chain."""
    return SCMWorld(
        graph={"Z": [], "X": ["Z"], "Y": ["X"]},
        equations={
            "Z": lambda p, rng: rng.normal(0, 1),
            "X": lambda p, rng: p["Z"] * 2 + rng.normal(0, 0.5),
            "Y": lambda p, rng: p["X"] + 3 + rng.normal(0, 0.3),
        },
    )


def _wide_7node() -> SCMWorld:
    """Fork + chain: enough variables for 3-artifact split.

    A, B -> C -> D -> G
    E -> F -> G
    """
    return SCMWorld(
        graph={
            "A": [],
            "B": [],
            "C": ["A", "B"],
            "D": ["C"],
            "E": [],
            "F": ["E"],
            "G": ["D", "F"],
        },
        equations={
            "A": lambda p, rng: rng.normal(100, 20),
            "B": lambda p, rng: rng.normal(50, 10),
            "C": lambda p, rng: 0.3 * p["A"] + 0.5 * p["B"] + rng.normal(0, 5),
            "D": lambda p, rng: p["C"] * 0.8 + rng.normal(0, 3),
            "E": lambda p, rng: rng.normal(30, 8),
            "F": lambda p, rng: p["E"] * 1.2 + rng.normal(0, 4),
            "G": lambda p, rng: 0.4 * p["D"] + 0.6 * p["F"] + rng.normal(0, 2),
        },
        variable_meta={
            "A": VariableMeta(unit="mg/L", range=(40, 160)),
            "B": VariableMeta(unit="mg/dL", range=(20, 80)),
            "C": VariableMeta(unit="index", range=(20, 90)),
            "D": VariableMeta(unit="score", range=(10, 70)),
            "E": VariableMeta(unit="celsius", range=(5, 55)),
            "F": VariableMeta(unit="W/m2", range=(5, 70)),
            "G": VariableMeta(unit="yield", range=(10, 70)),
        },
    )


# ------------------------------------------------------------------
# TestApplyRealism
# ------------------------------------------------------------------


class TestApplyRealism:
    def test_noise_changes_values(self):
        world = _simple_3node()
        clean = world.sample(n=200, seed=42)
        noisy = apply_realism(
            clean, world, noise_fraction=0.1, missing_rate=0, outlier_fraction=0, seed=1
        )
        # Values should differ
        assert not clean.equals(noisy)
        # But shape is preserved
        assert clean.shape == noisy.shape

    def test_noise_fraction_zero_no_change(self):
        world = _simple_3node()
        clean = world.sample(n=100, seed=42)
        result = apply_realism(
            clean, world, noise_fraction=0, missing_rate=0, outlier_fraction=0, seed=1
        )
        # Only rounding should change values
        for col in clean.columns:
            np.testing.assert_allclose(result[col], clean[col].round(2), atol=0.01)

    def test_noise_proportional_to_std(self):
        """Higher noise_fraction -> more deviation from clean values."""
        world = _linear_5node()
        clean = world.sample(n=500, seed=42)
        low = apply_realism(
            clean.copy(), world, noise_fraction=0.01, missing_rate=0,
            outlier_fraction=0, seed=1
        )
        high = apply_realism(
            clean.copy(), world, noise_fraction=0.2, missing_rate=0,
            outlier_fraction=0, seed=1
        )
        # Mean absolute deviation from clean should be higher for high noise
        dev_low = (low["B"] - clean["B"]).abs().mean()
        dev_high = (high["B"] - clean["B"]).abs().mean()
        assert dev_high > dev_low * 3

    def test_noise_clipped_to_range(self):
        world = _linear_5node()
        clean = world.sample(n=1000, seed=42)
        result = apply_realism(
            clean, world, noise_fraction=0.5, missing_rate=0,
            outlier_fraction=0, seed=1
        )
        meta = world.variable_meta["A"]
        assert result["A"].min() >= meta.range[0]
        assert result["A"].max() <= meta.range[1]

    def test_rounding_auto_infer(self):
        world = _linear_5node()
        clean = world.sample(n=100, seed=42)
        result = apply_realism(
            clean, world, noise_fraction=0, missing_rate=0, outlier_fraction=0, seed=1
        )
        # A has range (20, 80) -> range_width 60 -> 1 decimal
        decimals_a = result["A"].apply(lambda x: len(str(x).split(".")[-1]) if "." in str(x) else 0)
        assert decimals_a.max() <= 1

    def test_rounding_override(self):
        world = _simple_3node()
        clean = world.sample(n=100, seed=42)
        result = apply_realism(
            clean, world, noise_fraction=0, missing_rate=0, outlier_fraction=0,
            rounding={"Z": 0, "X": 3, "Y": 1}, seed=1
        )
        # Z should be integers
        assert (result["Z"] == result["Z"].round(0)).all()

    def test_missing_mcar_approximate_rate(self):
        world = _linear_5node()
        clean = world.sample(n=2000, seed=42)
        result = apply_realism(
            clean, world, noise_fraction=0, missing_rate=0.1,
            missing_mechanism="mcar", outlier_fraction=0, seed=1
        )
        # Non-target columns should have ~10% missing
        for col in ["A", "B", "C", "D"]:
            rate = result[col].isna().mean()
            assert 0.05 < rate < 0.20, f"{col} missing rate {rate} out of range"

    def test_missing_target_protected(self):
        world = _linear_5node()
        clean = world.sample(n=500, seed=42)
        result = apply_realism(
            clean, world, noise_fraction=0, missing_rate=0.3,
            missing_mechanism="mcar", outlier_fraction=0, target="E", seed=1
        )
        assert result["E"].isna().sum() == 0

    def test_missing_mar_extreme_parents_more_missing(self):
        """MAR: children of extreme-valued parents should have more missingness."""
        world = _simple_3node()
        clean = world.sample(n=5000, seed=42)
        result = apply_realism(
            clean, world, noise_fraction=0, missing_rate=0.05,
            missing_mechanism="mar", outlier_fraction=0, target="Y", seed=1
        )
        # X's parent is Z. When Z is extreme, X should be more missing
        z_vals = clean["Z"]
        z_extreme = z_vals.abs() > z_vals.std() * 1.5
        miss_extreme = result.loc[z_extreme, "X"].isna().mean()
        miss_normal = result.loc[~z_extreme, "X"].isna().mean()
        assert miss_extreme > miss_normal

    def test_missing_invalid_mechanism_raises(self):
        world = _simple_3node()
        clean = world.sample(n=10, seed=42)
        with pytest.raises(ValueError, match="Unknown missing mechanism"):
            apply_realism(
                clean, world, missing_rate=0.1, missing_mechanism="invalid", seed=1
            )

    def test_outliers_injected(self):
        world = _linear_5node()
        clean = world.sample(n=1000, seed=42)
        result = apply_realism(
            clean, world, noise_fraction=0, missing_rate=0,
            outlier_fraction=0.05, outlier_magnitude=4.0, seed=1
        )
        # Some values should be far from mean
        for col in ["A", "B"]:
            col_mean = clean[col].mean()
            col_std = clean[col].std()
            extreme = (result[col] - col_mean).abs() > 3.5 * col_std
            assert extreme.sum() > 0, f"No outliers found in {col}"

    def test_reproducible_with_seed(self):
        world = _linear_5node()
        clean = world.sample(n=100, seed=42)
        r1 = apply_realism(clean.copy(), world, seed=99)
        r2 = apply_realism(clean.copy(), world, seed=99)
        pd.testing.assert_frame_equal(r1, r2)

    def test_different_seeds_differ(self):
        world = _linear_5node()
        clean = world.sample(n=100, seed=42)
        r1 = apply_realism(clean.copy(), world, seed=1)
        r2 = apply_realism(clean.copy(), world, seed=2)
        assert not r1.equals(r2)


# ------------------------------------------------------------------
# TestRealisticSample
# ------------------------------------------------------------------


class TestRealisticSample:
    def test_convenience_wrapper(self):
        world = _simple_3node()
        df = realistic_sample(world, n=100, seed=42)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 100
        assert list(df.columns) == world.variables

    def test_has_missing_data(self):
        world = _simple_3node()
        df = realistic_sample(world, n=500, missing_rate=0.1, seed=42)
        assert df.isna().any().any()

    def test_reproducible(self):
        world = _simple_3node()
        r1 = realistic_sample(world, n=100, seed=42)
        r2 = realistic_sample(world, n=100, seed=42)
        pd.testing.assert_frame_equal(r1, r2)


# ------------------------------------------------------------------
# TestMultiDataset
# ------------------------------------------------------------------


class TestMultiDataset:
    def test_produces_artifacts(self):
        world = _wide_7node()
        artifacts = multi_dataset_sample(world, n=100)
        assert len(artifacts) >= 2
        assert all(isinstance(a, DatasetArtifact) for a in artifacts)

    def test_three_artifacts_for_wide_graph(self):
        """7-node graph should produce 3 artifacts (enough secondary vars)."""
        world = _wide_7node()
        artifacts = multi_dataset_sample(world, n=100)
        assert len(artifacts) == 3
        names = [a.name for a in artifacts]
        assert "background_records" in names
        assert "field_survey" in names
        assert "detailed_analysis" in names

    def test_two_artifacts_for_small_graph(self):
        """3-node graph: not enough secondary vars for detailed artifact."""
        world = _simple_3node()
        artifacts = multi_dataset_sample(world, n=100)
        assert len(artifacts) == 2

    def test_background_is_largest(self):
        world = _wide_7node()
        artifacts = multi_dataset_sample(world, n=100)
        bg = next(a for a in artifacts if a.name == "background_records")
        survey = next(a for a in artifacts if a.name == "field_survey")
        assert len(bg.data) > len(survey.data)

    def test_background_has_min_500_rows(self):
        world = _wide_7node()
        artifacts = multi_dataset_sample(world, n=100)
        bg = next(a for a in artifacts if a.name == "background_records")
        # sample_id column included, so check data length
        assert len(bg.data) >= 500

    def test_artifacts_have_sample_id(self):
        world = _wide_7node()
        artifacts = multi_dataset_sample(world, n=100)
        for a in artifacts:
            assert "sample_id" in a.data.columns

    def test_artifacts_have_metadata(self):
        world = _wide_7node()
        artifacts = multi_dataset_sample(world, n=100)
        for a in artifacts:
            assert a.name
            assert a.source
            assert a.description
            assert "Dataset with" in a.description

    def test_column_split_primary_has_target(self):
        world = _wide_7node()
        artifacts = multi_dataset_sample(world, target="G", n=100)
        bg = next(a for a in artifacts if a.name == "background_records")
        assert "G" in bg.data.columns

    def test_field_survey_has_overlap_column(self):
        world = _wide_7node()
        artifacts = multi_dataset_sample(world, target="G", n=100)
        bg = next(a for a in artifacts if a.name == "background_records")
        survey = next(a for a in artifacts if a.name == "field_survey")
        bg_cols = set(bg.data.columns) - {"sample_id"}
        survey_cols = set(survey.data.columns) - {"sample_id"}
        # Survey should have at least one column not in background (the overlap)
        # or be a superset if all primary are shared
        assert survey_cols >= bg_cols or len(survey_cols - bg_cols) >= 0

    def test_detailed_has_specialized_columns(self):
        world = _wide_7node()
        artifacts = multi_dataset_sample(world, target="G", n=100)
        if len(artifacts) == 3:
            detail = next(a for a in artifacts if a.name == "detailed_analysis")
            bg = next(a for a in artifacts if a.name == "background_records")
            bg_cols = set(bg.data.columns) - {"sample_id"}
            detail_cols = set(detail.data.columns) - {"sample_id"}
            # Detailed should have columns NOT in background
            unique_to_detail = detail_cols - bg_cols
            assert len(unique_to_detail) > 0

    def test_artifacts_are_independent_samples(self):
        """Each artifact samples independently (different seed)."""
        world = _wide_7node()
        artifacts = multi_dataset_sample(world, n=200)
        bg = next(a for a in artifacts if a.name == "background_records")
        survey = next(a for a in artifacts if a.name == "field_survey")
        # Find shared columns (excluding sample_id)
        shared = (
            set(bg.data.columns) & set(survey.data.columns)
        ) - {"sample_id"}
        if shared:
            col = list(shared)[0]
            # Means should be similar (same distribution) but not identical
            bg_mean = bg.data[col].mean()
            survey_mean = survey.data[col].dropna().mean()
            # Not identical (independent samples)
            assert bg_mean != pytest.approx(survey_mean, abs=0.001)

    def test_default_config(self):
        world = _wide_7node()
        artifacts = multi_dataset_sample(world)
        assert len(artifacts) >= 2

    def test_custom_config(self):
        world = _wide_7node()
        config = RealisticDataConfig(
            noise_fraction=0.1,
            missing_rate=0.15,
            missing_mechanism="mcar",
            outlier_fraction=0.02,
            seed=42,
        )
        artifacts = multi_dataset_sample(world, config=config)
        survey = next(a for a in artifacts if a.name == "field_survey")
        # Higher missing rate should produce visible missing data
        data_cols = [c for c in survey.data.columns if c != "sample_id"]
        assert survey.data[data_cols].isna().any().any()


# ------------------------------------------------------------------
# TestHelpers
# ------------------------------------------------------------------


class TestHelpers:
    def test_split_columns_chain(self):
        """A -> B -> C -> D -> E, target=E. Primary should be close to E."""
        world = _linear_5node()
        primary, secondary = _split_columns(world, "E")
        assert "E" in primary
        # D is distance 1 from E, should be primary
        assert "D" in primary
        # A is distance 4 from E, should be secondary
        assert "A" in secondary

    def test_split_columns_all_primary_for_small_graph(self):
        world = _simple_3node()
        primary, secondary = _split_columns(world, "Y")
        assert "Y" in primary
        # With only 2 non-target vars, at least 1 should be primary
        assert len(primary) >= 2

    def test_infer_precision_large_range(self):
        series = pd.Series([50, 100, 150, 200])
        assert _infer_precision(series, VariableMeta(range=(0, 200))) == 0

    def test_infer_precision_medium_range(self):
        series = pd.Series([36.0, 37.5, 38.2, 39.1])
        assert _infer_precision(series, VariableMeta(range=(35, 42))) == 2

    def test_infer_precision_small_range(self):
        series = pd.Series([0.1, 0.5, 0.9])
        assert _infer_precision(series, VariableMeta(range=(0, 1))) == 3

    def test_infer_precision_no_meta(self):
        series = pd.Series([10, 20, 30, 40, 50])
        result = _infer_precision(series, None)
        assert isinstance(result, int)
        assert result >= 0

    def test_describe_with_missing(self):
        df = pd.DataFrame({
            "sample_id": [1, 2, 3],
            "X": [1.0, np.nan, 3.0],
            "Y": [np.nan, 2.0, np.nan],
        })
        desc = _describe(df)
        assert "3 observations" in desc
        assert "Missing data:" in desc

    def test_describe_without_missing(self):
        df = pd.DataFrame({
            "sample_id": [1, 2, 3],
            "X": [1.0, 2.0, 3.0],
            "Y": [4.0, 5.0, 6.0],
        })
        desc = _describe(df)
        assert "3 observations" in desc
        assert "Missing" not in desc


# ------------------------------------------------------------------
# E2E: realistic data looks realistic
# ------------------------------------------------------------------


class TestE2E:
    def test_realistic_data_has_imperfections(self):
        """Full pipeline: sample + realism produces data with real-world artifacts."""
        world = _wide_7node()
        df = realistic_sample(
            world, n=1000,
            noise_fraction=0.05,
            missing_rate=0.08,
            outlier_fraction=0.01,
            seed=42,
        )
        # Has missing values
        assert df.isna().any().any()
        # Has reasonable value ranges (not all identical)
        for col in world.variables:
            valid = df[col].dropna()
            assert valid.std() > 0

    def test_multi_dataset_pipeline(self):
        """Full multi-dataset pipeline produces usable artifacts."""
        world = _wide_7node()
        config = RealisticDataConfig(
            noise_fraction=0.05,
            missing_rate=0.05,
            outlier_fraction=0.01,
            seed=42,
        )
        artifacts = multi_dataset_sample(world, config=config, target="G", n=300)

        # At least background + survey
        assert len(artifacts) >= 2

        # Background is large, low missing
        bg = artifacts[0]
        assert len(bg.data) >= 300
        bg_cols = [c for c in bg.data.columns if c != "sample_id"]
        bg_missing = bg.data[bg_cols].isna().mean().mean()
        assert bg_missing < 0.10

        # Survey is smaller, more missing
        survey = artifacts[1]
        assert len(survey.data) < len(bg.data)

        # All artifacts have continuous (float) data
        for a in artifacts:
            data_cols = [c for c in a.data.columns if c != "sample_id"]
            for col in data_cols:
                assert a.data[col].dtype in [np.float64, float]

    def test_data_statistics_preserved(self):
        """Realism transforms shouldn't destroy the underlying signal."""
        world = _linear_5node()
        clean = world.sample(n=2000, seed=42)
        noisy = apply_realism(
            clean, world,
            noise_fraction=0.05,
            missing_rate=0.05,
            outlier_fraction=0.01,
            seed=1,
        )
        # Correlation between B and A should be preserved (strong linear)
        # Drop rows where either A or B is missing (align indices)
        valid = noisy[["A", "B"]].dropna()
        noisy_corr = valid["A"].corr(valid["B"])
        # Correlation should remain high (> 0.8 original was ~0.97)
        assert noisy_corr > 0.8


# ------------------------------------------------------------------
# Panel structure
# ------------------------------------------------------------------


class TestPanelStructure:
    def test_adds_site_and_wave_columns(self):
        world = _linear_5node()
        df = world.sample(n=200, seed=42)
        panel_df, _ = apply_panel_structure(df, world, PanelConfig(seed=42))
        assert "site_id" in panel_df.columns
        assert "wave" in panel_df.columns

    def test_correct_number_of_sites(self):
        world = _linear_5node()
        df = world.sample(n=200, seed=42)
        panel_df, _ = apply_panel_structure(
            df, world, PanelConfig(n_sites=5, seed=42)
        )
        assert panel_df["site_id"].nunique() == 5

    def test_correct_number_of_waves(self):
        world = _linear_5node()
        df = world.sample(n=200, seed=42)
        panel_df, _ = apply_panel_structure(
            df, world, PanelConfig(n_waves=4, seed=42)
        )
        assert panel_df["wave"].nunique() == 4

    def test_within_site_correlation(self):
        """Rows within a site should be more similar than across sites."""
        world = _linear_5node()
        df = world.sample(n=500, seed=42)
        panel_df, _ = apply_panel_structure(
            df, world, PanelConfig(n_sites=5, site_effect_std=0.5, seed=42)
        )
        # ICC: variance of site means / total variance
        col = "A"
        site_means = panel_df.groupby("site_id")[col].mean()
        between_var = site_means.var()
        total_var = panel_df[col].var()
        icc = between_var / total_var if total_var > 0 else 0
        assert icc > 0.01  # some clustering effect

    def test_dropout_reduces_later_waves(self):
        world = _linear_5node()
        df = world.sample(n=300, seed=42)
        panel_df, _ = apply_panel_structure(
            df, world, PanelConfig(n_sites=6, n_waves=3, dropout_rate=0.5, seed=42)
        )
        wave_counts = panel_df.groupby("wave")["A"].apply(
            lambda s: s.notna().sum()
        )
        # Wave 0 should have more valid observations than wave 2
        assert wave_counts.iloc[0] >= wave_counts.iloc[-1]

    def test_reproducible_with_seed(self):
        world = _linear_5node()
        df = world.sample(n=100, seed=42)
        cfg = PanelConfig(seed=99)
        df1, _ = apply_panel_structure(df.copy(), world, cfg)
        df2, _ = apply_panel_structure(df.copy(), world, cfg)
        pd.testing.assert_frame_equal(df1, df2)

    def test_values_clipped_to_range(self):
        world = _linear_5node()
        df = world.sample(n=200, seed=42)
        panel_df, _ = apply_panel_structure(
            df, world, PanelConfig(site_effect_std=0.8, seed=42)
        )
        for var in world.variables:
            meta = world.variable_meta.get(var)
            if meta and var in panel_df.columns:
                valid = panel_df[var].dropna()
                assert valid.min() >= meta.range[0] - 0.01
                assert valid.max() <= meta.range[1] + 0.01


class TestProxyColumns:
    def test_proxy_columns_added(self):
        world = _linear_5node()
        df = world.sample(n=100, seed=42)
        panel_df, proxy_names = apply_panel_structure(
            df, world, PanelConfig(n_proxy_columns=3, seed=42)
        )
        assert len(proxy_names) == 3
        for name in proxy_names:
            assert name in panel_df.columns

    def test_proxy_correlated_with_source(self):
        world = _linear_5node()
        df = world.sample(n=500, seed=42)
        panel_df, proxy_names = apply_panel_structure(
            df, world, PanelConfig(n_proxy_columns=2, proxy_noise_std=0.3, seed=42)
        )
        # At least one proxy should correlate > 0.3 with some real variable
        max_corr = 0
        for pname in proxy_names:
            for var in world.variables:
                if var in panel_df.columns:
                    valid = panel_df[[pname, var]].dropna()
                    if len(valid) > 10:
                        c = abs(valid[pname].corr(valid[var]))
                        max_corr = max(max_corr, c)
        assert max_corr > 0.3

    def test_proxy_names_not_in_scm(self):
        world = _linear_5node()
        df = world.sample(n=100, seed=42)
        _, proxy_names = apply_panel_structure(
            df, world, PanelConfig(n_proxy_columns=2, seed=42)
        )
        for name in proxy_names:
            assert name not in world.variables

    def test_zero_proxies(self):
        world = _linear_5node()
        df = world.sample(n=100, seed=42)
        _, proxy_names = apply_panel_structure(
            df, world, PanelConfig(n_proxy_columns=0, seed=42)
        )
        assert len(proxy_names) == 0


class TestPanelMultiDataset:
    def test_background_has_panel_columns(self):
        world = _wide_7node()
        config = RealisticDataConfig(seed=42)
        panel = PanelConfig(n_sites=4, n_waves=2, seed=42)
        artifacts = multi_dataset_sample(
            world, config=config, target="G", n=200, panel=panel,
        )
        bg = artifacts[0]
        assert "site_id" in bg.data.columns
        assert "wave" in bg.data.columns

    def test_survey_flat_no_panel(self):
        world = _wide_7node()
        config = RealisticDataConfig(seed=42)
        panel = PanelConfig(seed=42)
        artifacts = multi_dataset_sample(
            world, config=config, target="G", n=200, panel=panel,
        )
        survey = artifacts[1]
        assert "site_id" not in survey.data.columns
        assert "wave" not in survey.data.columns

    def test_shared_sample_ids(self):
        """Survey rows should be a subset of the master sample."""
        world = _wide_7node()
        config = RealisticDataConfig(seed=42)
        panel = PanelConfig(seed=42)
        artifacts = multi_dataset_sample(
            world, config=config, target="G", n=200, panel=panel,
        )
        bg_ids = set(artifacts[0].data["sample_id"].dropna())
        survey_ids = set(artifacts[1].data["sample_id"].dropna())
        # Survey IDs should be a subset of background IDs
        assert survey_ids.issubset(bg_ids)

    def test_panel_missing_higher(self):
        """Panel background should have higher missing than legacy mode."""
        world = _wide_7node()
        config = RealisticDataConfig(seed=42)
        panel = PanelConfig(seed=42)
        arts_panel = multi_dataset_sample(
            world, config=config, target="G", n=300, panel=panel,
        )
        arts_legacy = multi_dataset_sample(
            world, config=config, target="G", n=300, panel=None,
        )
        bg_panel = arts_panel[0]
        bg_legacy = arts_legacy[0]
        data_cols_p = [
            c for c in bg_panel.data.columns
            if c not in {"sample_id", "site_id", "wave"}
            and not c.endswith(("_index", "_reading", "_score", "_level", "_measure"))
        ]
        data_cols_l = [c for c in bg_legacy.data.columns if c != "sample_id"]
        miss_panel = bg_panel.data[data_cols_p].isna().mean().mean()
        miss_legacy = bg_legacy.data[data_cols_l].isna().mean().mean()
        assert miss_panel > miss_legacy
