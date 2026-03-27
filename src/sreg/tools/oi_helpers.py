"""OI Instrumented Helpers: analysis functions that produce trace records.

These helpers are pre-loaded in the solver's python_exec namespace during
OI episodes. They perform standard analyses AND automatically log
AnalysisRecord entries for the warrant system.

Usage in solver code:
    df = load_artifact("dataset_bg")
    oi.corr(df, cols=["A", "Y", "C"])
    oi.regress(df, y="Y", x=["A"], controls=["C"])
    oi.stratify(df, by="Z", value="Y")

The solver CAN also use raw pandas — these helpers are preferred but
not required. Using helpers produces stronger warrant (Level 3).

Design: research/notes/oi_trace_contract.md
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import numpy as np
import pandas as pd

from sreg.models.open_investigation import AnalysisRecord, EpisodeTrace

logger = logging.getLogger(__name__)


class OIHelpers:
    """Instrumented analysis helpers for OI solver.

    Each method performs a standard analysis AND logs an AnalysisRecord
    in the provided EpisodeTrace. The op_type is set automatically
    from the helper method name — no self-reporting by the solver.
    """

    def __init__(self, trace: EpisodeTrace, step_counter: dict[str, int]):
        """Initialize with trace collector and step counter.

        Args:
            trace: The EpisodeTrace to log records into.
            step_counter: Mutable dict with "current" key for step tracking.
                The runner increments this as the episode progresses.
        """
        self._trace = trace
        self._step = step_counter

    def _current_step(self) -> int:
        return self._step.get("current", 0)

    def _log(
        self,
        op_type: str,
        input_artifact_ids: list[str],
        columns_used: list[str],
        output_artifact_id: str | None = None,
    ) -> None:
        """Log an AnalysisRecord to the trace."""
        self._trace.analyses.append(
            AnalysisRecord(
                analysis_id=f"oi_{uuid.uuid4().hex[:8]}",
                input_artifact_ids=input_artifact_ids,
                columns_used=columns_used,
                op_type=op_type,
                step=self._current_step(),
                output_artifact_id=output_artifact_id,
            )
        )

    def _infer_artifact_id(self, df: pd.DataFrame) -> str:
        """Try to get artifact_id from DataFrame metadata."""
        return getattr(df, "_oi_artifact_id", "unknown")

    # -----------------------------------------------------------------
    # Analysis helpers
    # -----------------------------------------------------------------

    def corr(
        self,
        df: pd.DataFrame,
        cols: list[str] | None = None,
    ) -> pd.DataFrame:
        """Compute correlation matrix.

        Args:
            df: DataFrame to analyze.
            cols: Columns to include. If None, uses all numeric columns.
        """
        if cols is None:
            cols = list(df.select_dtypes(include=[np.number]).columns)
        result = df[cols].corr()
        aid = self._infer_artifact_id(df)
        self._log("correlation", [aid], cols)
        return result

    def regress(
        self,
        df: pd.DataFrame,
        y: str,
        x: list[str],
        controls: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run OLS regression.

        Returns dict with coefficients, r_squared, p_values, n_obs.
        """
        from scipy import stats as sp_stats

        all_x = list(x) + (controls or [])
        all_cols = [y] + all_x
        clean = df[all_cols].dropna()

        if len(clean) < len(all_x) + 2:
            return {"error": "insufficient data", "n_obs": len(clean)}

        X = clean[all_x].values
        Y = clean[y].values

        # Add intercept
        X_with_intercept = np.column_stack([np.ones(len(X)), X])

        try:
            # OLS via normal equations
            beta = np.linalg.lstsq(X_with_intercept, Y, rcond=None)[0]
            y_pred = X_with_intercept @ beta
            residuals = Y - y_pred
            ss_res = float(np.sum(residuals**2))
            ss_tot = float(np.sum((Y - np.mean(Y)) ** 2))
            r_squared = 1.0 - ss_res / max(ss_tot, 1e-10)

            # Standard errors + p-values
            n = len(Y)
            k = X_with_intercept.shape[1]
            mse = ss_res / max(n - k, 1)
            try:
                var_beta = mse * np.linalg.inv(
                    X_with_intercept.T @ X_with_intercept
                ).diagonal()
                se = np.sqrt(np.maximum(var_beta, 0))
                t_stats = beta / np.maximum(se, 1e-10)
                p_values = [
                    float(2 * (1 - sp_stats.t.cdf(abs(t), max(n - k, 1))))
                    for t in t_stats
                ]
            except np.linalg.LinAlgError:
                se = [float("nan")] * k
                p_values = [float("nan")] * k

            coefs = {
                "intercept": float(beta[0]),
            }
            for i, name in enumerate(all_x):
                coefs[name] = float(beta[i + 1])

            result = {
                "coefficients": coefs,
                "r_squared": r_squared,
                "p_values": dict(zip(["intercept"] + all_x, p_values)),
                "n_obs": n,
            }
        except Exception as e:
            result = {"error": str(e), "n_obs": len(clean)}

        aid = self._infer_artifact_id(df)
        self._log("regression", [aid], all_cols)
        return result

    def stratify(
        self,
        df: pd.DataFrame,
        by: str,
        value: str,
        n_strata: int = 3,
    ) -> dict[str, Any]:
        """Stratified means of `value` by quantile groups of `by`.

        Returns dict with strata means, counts, and overall mean.
        """
        clean = df[[by, value]].dropna()
        if len(clean) < n_strata:
            return {"error": "insufficient data", "n_obs": len(clean)}

        clean = clean.copy()
        clean["_stratum"] = pd.qcut(
            clean[by], n_strata, labels=False, duplicates="drop"
        )

        strata = {}
        for s in sorted(clean["_stratum"].unique()):
            subset = clean[clean["_stratum"] == s]
            strata[f"q{int(s)}"] = {
                "mean": float(subset[value].mean()),
                "std": float(subset[value].std()),
                "n": int(len(subset)),
                f"{by}_range": [
                    float(subset[by].min()),
                    float(subset[by].max()),
                ],
            }

        result = {
            "strata": strata,
            "overall_mean": float(clean[value].mean()),
            "n_obs": len(clean),
        }

        aid = self._infer_artifact_id(df)
        self._log("stratify", [aid], [by, value])
        return result

    def test_independence(
        self,
        df: pd.DataFrame,
        x: str,
        y: str,
        z: str | None = None,
    ) -> dict[str, Any]:
        """Test statistical independence between x and y, optionally conditioning on z.

        Uses partial correlation test when z is provided.
        """
        from scipy import stats as sp_stats

        cols = [x, y] + ([z] if z else [])
        clean = df[cols].dropna()

        if len(clean) < 5:
            return {"error": "insufficient data", "n_obs": len(clean)}

        if z is None:
            # Simple correlation test
            r, p = sp_stats.pearsonr(clean[x], clean[y])
            result = {
                "test": "pearson_correlation",
                "r": float(r),
                "p_value": float(p),
                "independent": float(p) > 0.05,
                "n_obs": len(clean),
            }
        else:
            # Partial correlation
            r_xy = float(clean[x].corr(clean[y]))
            r_xz = float(clean[x].corr(clean[z]))
            r_yz = float(clean[y].corr(clean[z]))
            denom = np.sqrt(max((1 - r_xz**2) * (1 - r_yz**2), 1e-10))
            r_partial = (r_xy - r_xz * r_yz) / denom

            n = len(clean)
            t_stat = r_partial * np.sqrt(max(n - 3, 1)) / np.sqrt(
                max(1 - r_partial**2, 1e-10)
            )
            p_val = float(
                2 * (1 - sp_stats.t.cdf(abs(t_stat), max(n - 3, 1)))
            )

            result = {
                "test": "partial_correlation",
                "r_partial": float(r_partial),
                "p_value": p_val,
                "independent": p_val > 0.05,
                "conditioning_on": z,
                "n_obs": n,
            }

        aid = self._infer_artifact_id(df)
        self._log("test", [aid], cols)
        return result

    def groupby_mean(
        self,
        df: pd.DataFrame,
        group_col: str,
        value_col: str,
    ) -> pd.DataFrame:
        """Group by a column and compute mean of another."""
        result = df.groupby(group_col)[value_col].agg(["mean", "std", "count"])
        aid = self._infer_artifact_id(df)
        self._log("aggregate", [aid], [group_col, value_col])
        return result


def tag_dataframe(df: pd.DataFrame, artifact_id: str) -> pd.DataFrame:
    """Tag a DataFrame with its artifact_id for trace inference.

    Called by load_artifact() to enable _infer_artifact_id().
    """
    df._oi_artifact_id = artifact_id  # type: ignore[attr-defined]
    return df


__all__ = [
    "OIHelpers",
    "tag_dataframe",
]
