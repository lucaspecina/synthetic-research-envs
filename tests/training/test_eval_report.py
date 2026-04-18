"""Tests for sreg.training.eval_report helpers.

These are the pure aggregation helpers driving the eval script's
reporting layer. Bugs here silently corrupt diagnostics (e.g. a
per-case breakdown that loses rollouts, or a percentile summary that
includes non-finite values).
"""

from __future__ import annotations

import json

import pytest

from sreg.training.eval_report import (
    per_case_breakdown,
    run_metadata,
    summarize_values,
    variance_report,
    variance_verdict,
    write_trajectories_jsonl,
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


class TestWriteTrajectoriesJsonl:
    def test_writes_one_line_per_rollout(self, tmp_path):
        outputs = [
            {"problem_id": "a", "reward": 0.5, "trajectory": [{"step": 1}]},
            {"problem_id": "b", "reward": 0.3, "trajectory": [{"step": 1}, {"step": 2}]},
        ]
        path = tmp_path / "trajectories.jsonl"
        n = write_trajectories_jsonl(outputs, path)
        assert n == 2
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        # Each line is a complete JSON object, not just a fragment.
        recs = [json.loads(line) for line in lines]
        assert recs[0]["problem_id"] == "a"
        assert recs[0]["reward"] == 0.5
        assert recs[1]["problem_id"] == "b"

    def test_creates_parent_dir(self, tmp_path):
        """Auto-creates the parent dir — matches --output behavior."""
        path = tmp_path / "nested" / "subdir" / "t.jsonl"
        n = write_trajectories_jsonl([{"problem_id": "x"}], path)
        assert n == 1
        assert path.exists()

    def test_empty_outputs_writes_empty_file(self, tmp_path):
        path = tmp_path / "empty.jsonl"
        n = write_trajectories_jsonl([], path)
        assert n == 0
        assert path.read_text(encoding="utf-8") == ""

    def test_extra_output_fields_dropped(self, tmp_path):
        """Only the whitelisted fields get written — extras don't bloat the file.

        RolloutOutput has many fields we don't need in the trajectory
        dump (e.g. prompt duplication). Whitelist via _TRAJECTORY_FIELDS
        keeps each line focused.
        """
        outputs = [
            {
                "problem_id": "a",
                "reward": 0.5,
                "trajectory": [],
                "completion": [],
                "random_extra_field": "bloat",
                "another_one": [1, 2, 3],
            }
        ]
        path = tmp_path / "t.jsonl"
        write_trajectories_jsonl(outputs, path)
        rec = json.loads(path.read_text(encoding="utf-8").strip())
        assert "random_extra_field" not in rec
        assert "another_one" not in rec
        assert rec["problem_id"] == "a"

    def test_missing_fields_serialized_as_null(self, tmp_path):
        """Rollouts missing a whitelist field get JSON null — not a KeyError."""
        outputs = [{"problem_id": "a"}]  # no reward, no trajectory, etc.
        path = tmp_path / "t.jsonl"
        write_trajectories_jsonl(outputs, path)
        rec = json.loads(path.read_text(encoding="utf-8").strip())
        assert rec["problem_id"] == "a"
        assert rec["reward"] is None
        assert rec["trajectory"] is None

    def test_custom_fields_override(self, tmp_path):
        """fields= param lets callers pick what to dump."""
        outputs = [{"problem_id": "a", "reward": 0.5, "trajectory": [{"x": 1}]}]
        path = tmp_path / "t.jsonl"
        write_trajectories_jsonl(outputs, path, fields=["problem_id", "reward"])
        rec = json.loads(path.read_text(encoding="utf-8").strip())
        assert set(rec.keys()) == {"problem_id", "reward"}

    def test_non_json_serializable_values_use_str_fallback(self, tmp_path):
        """default=str on json.dumps — exotic objects get stringified
        instead of crashing the dump mid-file."""
        from pathlib import PurePosixPath

        outputs = [{"problem_id": "a", "trajectory": [PurePosixPath("/tmp/foo")]}]
        path = tmp_path / "t.jsonl"
        # Should not raise.
        write_trajectories_jsonl(outputs, path)
        rec = json.loads(path.read_text(encoding="utf-8").strip())
        # PurePosixPath serializes to its str form via default=str.
        assert rec["trajectory"][0].endswith("foo")


def _make_output(pid: str, reward: float, *, submitted: bool = True,
                 step_count: int = 5, stop: str = "submitted") -> dict:
    """Helper: build a minimal output dict for variance_report tests."""
    return {
        "problem_id": pid,
        "reward": reward,
        "stop_condition": stop,
        "metrics": {"submitted": 1.0 if submitted else 0.0,
                    "step_count": step_count},
    }


class TestVarianceReport:
    def test_empty_outputs_returns_nan_sentinels(self):
        """No rollouts -> NaN aggregates, empty per_group. Must not crash:
        a failed audit run should produce a readable report, not an
        exception."""
        r = variance_report([])
        assert r["n_rollouts"] == 0
        assert r["n_groups"] == 0
        assert r["per_group"] == {}
        # NaN aggregates (signal "no data", not "signal=0")
        import math
        assert math.isnan(r["mean_intra_group_std"])
        assert math.isnan(r["submitted_only_mean_std"])

    def test_single_group_identical_rewards_zero_variance(self):
        """4 identical rewards in a group -> std=0, counts as "collapsed"."""
        outs = [_make_output("A", 0.3) for _ in range(4)]
        r = variance_report(outs)
        assert r["n_groups"] == 1
        assert r["mean_intra_group_std"] == 0.0
        assert r["pct_zero_variance_groups"] == 100.0
        assert r["pct_single_reward_groups"] == 100.0
        assert r["per_group"]["A"]["n_unique_rewards"] == 1

    def test_mixed_variance_groups(self):
        """2 groups: one collapsed, one with spread. Mean std averages across."""
        outs = [
            _make_output("A", 0.2),
            _make_output("A", 0.2),
            _make_output("B", 0.5),
            _make_output("B", 0.1),
        ]
        r = variance_report(outs)
        assert r["n_groups"] == 2
        # A std=0, B std=0.2 -> mean=0.1
        assert r["mean_intra_group_std"] == pytest.approx(0.1)
        assert r["pct_zero_variance_groups"] == 50.0

    def test_submitted_only_excludes_no_submit_mixture(self):
        """Codex failure mode: 2 submits at +0.3, 2 no-submits at -0.05
        -> raw std ~0.17 looks promising, but submitted_only has only 2
        values at +0.3 -> std=0 reveals no real research-quality signal."""
        outs = [
            _make_output("A", 0.3, submitted=True),
            _make_output("A", 0.3, submitted=True),
            _make_output("A", -0.05, submitted=False),
            _make_output("A", -0.05, submitted=False),
        ]
        r = variance_report(outs)
        # Raw intra-group std is non-trivial...
        assert r["mean_intra_group_std"] > 0.1
        # ...but submitted_only exposes the collapse
        assert r["submitted_only_mean_std"] == 0.0

    def test_submitted_only_nan_when_no_group_has_two_submits(self):
        """If no group has >=2 submitted rollouts, submitted_only is NaN
        (not 0.0) — 0.0 would falsely imply "we measured collapse"."""
        import math
        outs = [
            _make_output("A", -0.05, submitted=False),
            _make_output("A", -0.10, submitted=False),
        ]
        r = variance_report(outs)
        assert math.isnan(r["submitted_only_mean_std"])
        assert r["submitted_only_n_groups"] == 0

    def test_submit_rate_and_stop_conditions(self):
        outs = [
            _make_output("A", 0.3, submitted=True, stop="submitted"),
            _make_output("A", -0.05, submitted=False, stop="turn_limit"),
            _make_output("B", 0.5, submitted=True, stop="submitted"),
        ]
        r = variance_report(outs)
        assert r["submit_rate"] == pytest.approx(2 / 3)
        assert r["stop_condition_distribution"] == {
            "submitted": 2, "turn_limit": 1,
        }

    def test_top1_top2_gap(self):
        """mean_top1_top2_gap: contrastive signal proxy. For group [0.5,
        0.3] gap=0.2; for [0.6, 0.6] gap=0; mean=0.1."""
        outs = [
            _make_output("A", 0.5),
            _make_output("A", 0.3),
            _make_output("B", 0.6),
            _make_output("B", 0.6),
        ]
        r = variance_report(outs)
        assert r["mean_top1_top2_gap"] == pytest.approx(0.1)

    def test_step_count_reward_correlation(self):
        """Negative correlation = more effort -> lower reward (penalty bug signal)."""
        outs = [
            _make_output("A", 0.5, step_count=2),
            _make_output("A", 0.3, step_count=5),
            _make_output("A", 0.1, step_count=10),
        ]
        r = variance_report(outs)
        # step_count up, reward down -> strongly negative correlation
        assert r["step_count_reward_correlation"] < -0.9

    def test_bootstrap_ci_is_reasonable_interval(self):
        """CI should contain the point estimate and be wider than a single
        value. Not asserting exact numbers — bootstrap is stochastic but
        seeded."""
        outs = []
        for pid, rewards in (
            ("A", [0.2, 0.3, 0.4, 0.5]),
            ("B", [0.1, 0.1, 0.2, 0.2]),
            ("C", [0.5, 0.5, 0.5, 0.5]),
        ):
            outs.extend(_make_output(pid, r) for r in rewards)
        r = variance_report(outs)
        lo, hi = r["bootstrap_ci_95"]
        assert lo <= r["mean_intra_group_std"] <= hi

    def test_missing_problem_id_goes_to_unknown(self):
        """state_columns hookup failure manifests as missing problem_id;
        must land under _unknown rather than be silently dropped."""
        outs = [
            {"reward": 0.3, "metrics": {"submitted": 1.0, "step_count": 5}},
            {"reward": 0.5, "metrics": {"submitted": 1.0, "step_count": 5}},
        ]
        r = variance_report(outs)
        assert "_unknown" in r["per_group"]
        assert r["per_group"]["_unknown"]["n_rollouts"] == 2


class TestVarianceVerdict:
    def _report(self, *, all_std: float, sub_std: float, zero_pct: float) -> dict:
        """Minimal variance_report-shaped dict for verdict tests."""
        return {
            "mean_intra_group_std": all_std,
            "submitted_only_mean_std": sub_std,
            "pct_zero_variance_groups": zero_pct,
        }

    def test_all_gates_pass_returns_pass(self):
        v = self._report(all_std=0.10, sub_std=0.05, zero_pct=20.0)
        r = variance_verdict(v)
        assert r["verdict"] == "PASS"
        assert all(r["gates"].values())

    def test_all_gates_fail_returns_fail(self):
        v = self._report(all_std=0.01, sub_std=0.01, zero_pct=90.0)
        r = variance_verdict(v)
        assert r["verdict"] == "FAIL"
        assert not any(r["gates"].values())

    def test_two_gates_pass_returns_borderline(self):
        """Exactly 2/3 gates pass -> BORDERLINE. Operator should consider
        a second audit at higher temperature."""
        v = self._report(all_std=0.10, sub_std=0.05, zero_pct=60.0)
        r = variance_verdict(v)
        assert r["verdict"] == "BORDERLINE"
        assert sum(r["gates"].values()) == 2

    def test_one_gate_passes_returns_fail(self):
        """Single gate pass is not "borderline" — too risky for H100 spend."""
        v = self._report(all_std=0.10, sub_std=0.01, zero_pct=90.0)
        r = variance_verdict(v)
        assert r["verdict"] == "FAIL"

    def test_nan_submitted_std_treated_as_gate_fail(self):
        """If no groups have >=2 submits, submitted_only is NaN — the gate
        must fail closed, not pass (NaN >= 0.03 is False anyway, but make
        it explicit so refactors don't regress)."""
        v = self._report(all_std=0.10, sub_std=float("nan"), zero_pct=20.0)
        r = variance_verdict(v)
        assert r["gates"]["submitted_std_ok"] is False
        assert r["verdict"] == "BORDERLINE"  # 2/3 gates pass
