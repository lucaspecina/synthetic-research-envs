"""Tests for OI Instrumented Helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sreg.models.open_investigation import EpisodeTrace
from sreg.tools.oi_helpers import OIHelpers, tag_dataframe

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_df(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """Create a sample DataFrame with known relationships."""
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 1, n)
    z = rng.normal(0, 1, n)
    y = 0.5 * x + 0.3 * z + rng.normal(0, 0.5, n)
    df = pd.DataFrame({"X": x, "Z": z, "Y": y})
    return tag_dataframe(df, "dataset_test")


def _make_helpers() -> tuple[OIHelpers, EpisodeTrace]:
    """Create helpers with fresh trace."""
    trace = EpisodeTrace()
    step = {"current": 5}
    helpers = OIHelpers(trace, step)
    return helpers, trace


# ---------------------------------------------------------------------------
# Tag test
# ---------------------------------------------------------------------------


class TestTagDataFrame:
    def test_tags_artifact_id(self):
        df = pd.DataFrame({"A": [1, 2, 3]})
        tagged = tag_dataframe(df, "my_artifact")
        assert tagged._oi_artifact_id == "my_artifact"

    def test_returns_same_df(self):
        df = pd.DataFrame({"A": [1, 2, 3]})
        tagged = tag_dataframe(df, "my_artifact")
        assert tagged is df


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------


class TestCorr:
    def test_correlation_matrix(self):
        helpers, trace = _make_helpers()
        df = _sample_df()
        result = helpers.corr(df, cols=["X", "Y", "Z"])

        assert isinstance(result, pd.DataFrame)
        assert result.shape == (3, 3)
        assert result.loc["X", "Y"] > 0.3  # X->Y positive

    def test_logs_analysis_record(self):
        helpers, trace = _make_helpers()
        df = _sample_df()
        helpers.corr(df, cols=["X", "Y"])

        assert len(trace.analyses) == 1
        rec = trace.analyses[0]
        assert rec.op_type == "correlation"
        assert set(rec.columns_used) == {"X", "Y"}
        assert rec.input_artifact_ids == ["dataset_test"]
        assert rec.step == 5

    def test_default_all_numeric(self):
        helpers, trace = _make_helpers()
        df = _sample_df()
        result = helpers.corr(df)
        assert result.shape == (3, 3)


# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------


class TestRegress:
    def test_ols_coefficients(self):
        helpers, trace = _make_helpers()
        df = _sample_df(n=500)
        result = helpers.regress(df, y="Y", x=["X"])

        assert "coefficients" in result
        assert result["coefficients"]["X"] > 0.3  # true effect ~0.5
        assert result["r_squared"] > 0.2
        assert result["n_obs"] == 500

    def test_with_controls(self):
        helpers, trace = _make_helpers()
        df = _sample_df(n=500)
        result = helpers.regress(df, y="Y", x=["X"], controls=["Z"])

        assert "Z" in result["coefficients"]
        assert result["coefficients"]["Z"] > 0.1

    def test_logs_analysis_record(self):
        helpers, trace = _make_helpers()
        df = _sample_df()
        helpers.regress(df, y="Y", x=["X"], controls=["Z"])

        assert len(trace.analyses) == 1
        rec = trace.analyses[0]
        assert rec.op_type == "regression"
        assert set(rec.columns_used) == {"X", "Y", "Z"}

    def test_insufficient_data(self):
        helpers, trace = _make_helpers()
        df = _sample_df(n=2)
        result = helpers.regress(df, y="Y", x=["X", "Z"])
        assert "error" in result


# ---------------------------------------------------------------------------
# Stratify
# ---------------------------------------------------------------------------


class TestStratify:
    def test_stratified_means(self):
        helpers, trace = _make_helpers()
        df = _sample_df(n=300)
        result = helpers.stratify(df, by="X", value="Y", n_strata=3)

        assert "strata" in result
        assert len(result["strata"]) == 3
        # Higher X strata should have higher Y mean (positive effect)
        means = [s["mean"] for s in result["strata"].values()]
        assert means[-1] > means[0]  # highest > lowest

    def test_logs_analysis_record(self):
        helpers, trace = _make_helpers()
        df = _sample_df()
        helpers.stratify(df, by="X", value="Y")

        assert len(trace.analyses) == 1
        assert trace.analyses[0].op_type == "stratify"
        assert set(trace.analyses[0].columns_used) == {"X", "Y"}


# ---------------------------------------------------------------------------
# Independence test
# ---------------------------------------------------------------------------


class TestIndependence:
    def test_detects_dependence(self):
        helpers, trace = _make_helpers()
        df = _sample_df(n=500)
        result = helpers.test_independence(df, x="X", y="Y")

        assert result["test"] == "pearson_correlation"
        assert not result["independent"]  # X and Y are dependent
        assert result["p_value"] < 0.05

    def test_partial_correlation(self):
        helpers, trace = _make_helpers()
        df = _sample_df(n=500)
        result = helpers.test_independence(df, x="X", y="Y", z="Z")

        assert result["test"] == "partial_correlation"
        assert "r_partial" in result
        assert result["conditioning_on"] == "Z"

    def test_logs_analysis_record(self):
        helpers, trace = _make_helpers()
        df = _sample_df()
        helpers.test_independence(df, x="X", y="Y", z="Z")

        assert len(trace.analyses) == 1
        assert trace.analyses[0].op_type == "test"
        assert set(trace.analyses[0].columns_used) == {"X", "Y", "Z"}


# ---------------------------------------------------------------------------
# Groupby mean
# ---------------------------------------------------------------------------


class TestGroupbyMean:
    def test_groups(self):
        helpers, trace = _make_helpers()
        df = pd.DataFrame({
            "group": ["A", "A", "B", "B", "C", "C"],
            "value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        })
        df = tag_dataframe(df, "test_groups")
        result = helpers.groupby_mean(df, "group", "value")

        assert len(result) == 3
        assert result.loc["A", "mean"] == pytest.approx(1.5)
        assert result.loc["C", "mean"] == pytest.approx(5.5)

    def test_logs_analysis_record(self):
        helpers, trace = _make_helpers()
        df = pd.DataFrame({"g": ["a", "b"], "v": [1.0, 2.0]})
        df = tag_dataframe(df, "test")
        helpers.groupby_mean(df, "g", "v")

        assert len(trace.analyses) == 1
        assert trace.analyses[0].op_type == "aggregate"


# ---------------------------------------------------------------------------
# Multiple analyses accumulate
# ---------------------------------------------------------------------------


class TestTraceAccumulation:
    def test_multiple_helpers_accumulate(self):
        helpers, trace = _make_helpers()
        df = _sample_df()
        helpers.corr(df, cols=["X", "Y"])
        helpers.regress(df, y="Y", x=["X"])
        helpers.stratify(df, by="X", value="Y")

        assert len(trace.analyses) == 3
        ops = [a.op_type for a in trace.analyses]
        assert ops == ["correlation", "regression", "stratify"]
