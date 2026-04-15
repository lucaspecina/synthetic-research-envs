"""Tests for sreg.training.eval_report helpers.

These are the pure aggregation helpers driving the eval script's
reporting layer. Bugs here silently corrupt diagnostics (e.g. a
per-case breakdown that loses rollouts, or a percentile summary that
includes non-finite values).
"""

from __future__ import annotations

import pytest

from sreg.training.eval_report import (
    per_case_breakdown,
    run_metadata,
    summarize_values,
)


class TestSummarizeValues:
    def test_empty_list_returns_empty_dict(self):
        assert summarize_values([]) == {}

    def test_single_value_all_percentiles_equal(self):
        s = summarize_values([3.0])
        assert s["n"] == 1
        assert s["mean"] == 3.0
        assert s["min"] == 3.0
        assert s["max"] == 3.0
        assert s["p50"] == 3.0
        assert s["p90"] == 3.0
        assert s["p95"] == 3.0
        assert "p99" not in s  # N<50 -> no p99

    def test_small_batch_no_p99(self):
        """N<50 samples -> p99 omitted (single-datapoint quantile is misleading)."""
        s = summarize_values([float(i) for i in range(10)])
        assert "p99" not in s
        assert s["n"] == 10
        assert s["mean"] == 4.5
        assert s["min"] == 0.0
        assert s["max"] == 9.0

    def test_large_batch_includes_p99(self):
        """N>=50 -> p99 reported."""
        vals = [float(i) for i in range(100)]
        s = summarize_values(vals)
        assert "p99" in s
        assert s["n"] == 100
        # p99 of 0..99 = ~98.01 (numpy linear interpolation)
        assert s["p99"] == pytest.approx(98.01, abs=0.1)

    def test_threshold_exactly_50(self):
        """N=50 is the boundary where p99 turns on."""
        s = summarize_values([float(i) for i in range(50)])
        assert "p99" in s

    def test_threshold_49_no_p99(self):
        """N=49 is just under the threshold."""
        s = summarize_values([float(i) for i in range(49)])
        assert "p99" not in s

    def test_percentile_ordering(self):
        """p50 <= p90 <= p95 <= max always."""
        vals = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        s = summarize_values(vals)
        assert s["min"] <= s["p50"] <= s["p90"] <= s["p95"] <= s["max"]


class TestPerCaseBreakdown:
    def test_empty_outputs_returns_empty_dict(self):
        assert per_case_breakdown([]) == {}

    def test_single_rollout_one_case(self):
        outputs = [
            {"problem_id": "case_a", "reward": 0.5, "metrics": {"submitted_metric": 1.0}},
        ]
        b = per_case_breakdown(outputs)
        assert set(b.keys()) == {"case_a"}
        assert b["case_a"]["n_rollouts"] == 1
        assert b["case_a"]["reward_mean"] == 0.5
        assert b["case_a"]["reward_max"] == 0.5
        assert b["case_a"]["metrics_mean"]["submitted_metric"] == 1.0

    def test_multiple_rollouts_same_case_aggregated(self):
        outputs = [
            {"problem_id": "case_a", "reward": 0.2, "metrics": {"m": 1.0}},
            {"problem_id": "case_a", "reward": 0.8, "metrics": {"m": 0.0}},
        ]
        b = per_case_breakdown(outputs)
        assert b["case_a"]["n_rollouts"] == 2
        assert b["case_a"]["reward_mean"] == pytest.approx(0.5)
        assert b["case_a"]["reward_max"] == 0.8
        assert b["case_a"]["metrics_mean"]["m"] == 0.5

    def test_two_cases_keep_separate(self):
        outputs = [
            {"problem_id": "case_a", "reward": 0.2, "metrics": {}},
            {"problem_id": "case_b", "reward": 0.9, "metrics": {}},
            {"problem_id": "case_a", "reward": 0.1, "metrics": {}},
        ]
        b = per_case_breakdown(outputs)
        assert set(b.keys()) == {"case_a", "case_b"}
        assert b["case_a"]["n_rollouts"] == 2
        assert b["case_b"]["n_rollouts"] == 1
        assert b["case_b"]["reward_mean"] == 0.9

    def test_missing_problem_id_grouped_under_unknown(self):
        """Rollouts without problem_id surface as _unknown — not silently lost.

        A silent drop would mask a real bug: state_columns=["problem_id"]
        failed and the column didn't come through.
        """
        outputs = [
            {"problem_id": None, "reward": 0.3, "metrics": {}},
            {"reward": 0.7, "metrics": {}},  # no problem_id key
        ]
        b = per_case_breakdown(outputs)
        assert "_unknown" in b
        assert b["_unknown"]["n_rollouts"] == 2

    def test_metrics_with_missing_keys_averaged_over_present_only(self):
        """If a metric appears in some rollouts but not others, average
        only over rollouts where it's present."""
        outputs = [
            {"problem_id": "a", "reward": 0.0, "metrics": {"m1": 1.0, "m2": 5.0}},
            {"problem_id": "a", "reward": 0.0, "metrics": {"m1": 3.0}},
        ]
        b = per_case_breakdown(outputs)
        # m1 present in both: mean = 2.0
        assert b["a"]["metrics_mean"]["m1"] == 2.0
        # m2 only in first: mean = 5.0 (not 2.5)
        assert b["a"]["metrics_mean"]["m2"] == 5.0


class TestRunMetadata:
    def test_has_required_keys(self):
        meta = run_metadata()
        required = {
            "timestamp_utc",
            "python_version",
            "platform",
            "verifiers_version",
            "git_sha",
            "git_dirty",
        }
        assert required.issubset(set(meta.keys())), (
            f"Missing keys: {required - set(meta.keys())}"
        )

    def test_git_sha_is_real_or_unknown(self):
        """If run inside a git repo, SHA is 40 hex chars; otherwise 'unknown'."""
        meta = run_metadata()
        sha = meta["git_sha"]
        assert sha == "unknown" or (len(sha) == 40 and all(c in "0123456789abcdef" for c in sha))

    def test_bogus_repo_root_returns_unknown_sha(self, tmp_path):
        """A non-git directory yields git_sha='unknown' instead of crashing."""
        meta = run_metadata(repo_root=tmp_path)
        assert meta["git_sha"] == "unknown"

    def test_verifiers_version_is_string(self):
        """verifiers_version is always a string (version or 'unknown')."""
        meta = run_metadata()
        assert isinstance(meta["verifiers_version"], str)
