"""Tests for BenchmarkRunner classification and aggregation logic."""

from sreg.harness.benchmark import (
    BenchmarkReport,
    BenchmarkRunner,
    SRCResult,
    TaskResult,
    TypeMetrics,
    classify_failure_mode,
    classify_task_verdict,
    format_benchmark_report,
)
from sreg.models.task import TaskType

# ---------------------------------------------------------------------------
# classify_task_verdict
# ---------------------------------------------------------------------------


class TestClassifyVerdict:
    """Type-aware verdict classification."""

    def test_distribution_excellent(self):
        assert classify_task_verdict(TaskType.INFER_TARGET, 0.05) == "EXCELLENT"

    def test_distribution_good(self):
        assert classify_task_verdict(TaskType.CAUSAL_EFFECT, 0.3) == "GOOD"

    def test_distribution_fair(self):
        assert classify_task_verdict(TaskType.INFER_LATENT_CAUSE, 1.0) == "FAIR"

    def test_distribution_poor(self):
        assert classify_task_verdict(TaskType.INFER_TARGET, 2.5) == "POOR"

    def test_choice_correct(self):
        assert classify_task_verdict(TaskType.HYPOTHESIS_SELECTION, 1.0) == "CORRECT"

    def test_choice_wrong(self):
        assert classify_task_verdict(TaskType.COMPARE_INTERVENTIONS, 0.0) == "WRONG"

    def test_choice_partial(self):
        """NBO score_nbo can return partial values."""
        assert classify_task_verdict(TaskType.NEXT_BEST_OBSERVATION, 0.5) == "PARTIAL"

    def test_intervention_correct(self):
        assert classify_task_verdict(TaskType.BEST_INTERVENTION, 1.0) == "CORRECT"

    def test_adjustment_wrong(self):
        assert classify_task_verdict(TaskType.ADJUSTMENT_SET, 0.0) == "WRONG"

    def test_should_condition_correct(self):
        assert classify_task_verdict(TaskType.SHOULD_CONDITION, 1.0) == "CORRECT"

    def test_no_score(self):
        assert classify_task_verdict(TaskType.INFER_TARGET, None) == "NO_SCORE"


# ---------------------------------------------------------------------------
# classify_failure_mode
# ---------------------------------------------------------------------------


class TestClassifyFailure:
    """Type-aware failure classification — no global TRIVIAL label."""

    def test_agent_crash(self):
        fm = classify_failure_mode(
            TaskType.INFER_TARGET, False, None, 0, 0, "RuntimeError"
        )
        assert fm == "AGENT_CRASH"

    def test_no_submit(self):
        fm = classify_failure_mode(
            TaskType.INFER_TARGET, False, None, 3, 0, None
        )
        assert fm == "NO_SUBMIT"

    def test_no_score(self):
        fm = classify_failure_mode(
            TaskType.INFER_TARGET, True, None, 2, 0, None
        )
        assert fm == "NO_SCORE"

    # Distribution types
    def test_distribution_high_kl(self):
        fm = classify_failure_mode(
            TaskType.CAUSAL_EFFECT, True, 3.5, 2, 0, None
        )
        assert fm == "HIGH_KL"

    def test_distribution_zero_obs_low_kl(self):
        """Zero observations + low KL — might be trivial case or lucky guess."""
        fm = classify_failure_mode(
            TaskType.INFER_TARGET, True, 0.1, 0, 0, None
        )
        assert fm == "ZERO_OBS_LOW_KL"

    def test_distribution_normal(self):
        """Normal case: submitted, reasonable KL, used budget."""
        fm = classify_failure_mode(
            TaskType.INFER_TARGET, True, 0.3, 3, 0, None
        )
        assert fm is None

    # Choice types
    def test_choice_incorrect(self):
        fm = classify_failure_mode(
            TaskType.HYPOTHESIS_SELECTION, True, 0.0, 2, 0, None
        )
        assert fm == "INCORRECT"

    def test_choice_zero_obs_correct(self):
        """Correct without observing — guessing or reasoned from data."""
        fm = classify_failure_mode(
            TaskType.COMPARE_INTERVENTIONS, True, 1.0, 0, 0, None
        )
        assert fm == "ZERO_OBS_CORRECT"

    def test_choice_normal_correct(self):
        """Correct answer with observations — no failure."""
        fm = classify_failure_mode(
            TaskType.SHOULD_CONDITION, True, 1.0, 2, 0, None
        )
        assert fm is None

    def test_adjustment_incorrect(self):
        fm = classify_failure_mode(
            TaskType.ADJUSTMENT_SET, True, 0.0, 1, 0, None
        )
        assert fm == "INCORRECT"

    def test_format_retry(self):
        """Had format errors but still submitted."""
        fm = classify_failure_mode(
            TaskType.INFER_TARGET, True, 0.5, 3, 2, None
        )
        assert fm == "FORMAT_RETRY"

    def test_nbo_zero_obs_correct(self):
        fm = classify_failure_mode(
            TaskType.NEXT_BEST_OBSERVATION, True, 1.0, 0, 0, None
        )
        assert fm == "ZERO_OBS_CORRECT"


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


class TestAggregation:
    """BenchmarkRunner._aggregate populates type_metrics correctly."""

    def _make_report(self, task_results):
        """Create a report with a single SRC containing the given tasks."""
        src = SRCResult(
            case_id=1,
            orchestrator_completed=True,
            eval_types=[tr.task_type for tr in task_results],
            task_results=task_results,
        )
        report = BenchmarkReport(
            timestamp="test",
            n_srcs=1,
            n_srcs_completed=1,
            n_tasks=len(task_results),
            src_results=[src],
        )
        runner = BenchmarkRunner.__new__(BenchmarkRunner)
        runner._aggregate(report)
        return report

    def test_types_exercised(self):
        tasks = [
            TaskResult(task_id="1", task_type="infer_target", submitted=True, score=0.1),
            TaskResult(task_id="2", task_type="causal_effect", submitted=True, score=0.5),
        ]
        report = self._make_report(tasks)
        assert set(report.types_exercised) == {"infer_target", "causal_effect"}
        assert "hypothesis_selection" in report.types_missing

    def test_submission_rate(self):
        tasks = [
            TaskResult(task_id="1", task_type="infer_target", submitted=True, score=0.1),
            TaskResult(task_id="2", task_type="infer_target", submitted=False),
        ]
        report = self._make_report(tasks)
        assert report.overall_submission_rate == 0.5

    def test_type_metrics_scores(self):
        tasks = [
            TaskResult(task_id="1", task_type="infer_target", submitted=True, score=0.1),
            TaskResult(task_id="2", task_type="infer_target", submitted=True, score=0.3),
        ]
        report = self._make_report(tasks)
        m = report.type_metrics["infer_target"]
        assert m.count == 2
        assert m.submitted == 2
        assert m.scores == [0.1, 0.3]

    def test_failure_modes_counted(self):
        tasks = [
            TaskResult(
                task_id="1", task_type="hypothesis_selection",
                submitted=True, score=0.0, verdict="WRONG",
                failure_mode="INCORRECT",
            ),
            TaskResult(
                task_id="2", task_type="hypothesis_selection",
                submitted=True, score=1.0, verdict="CORRECT",
            ),
        ]
        report = self._make_report(tasks)
        m = report.type_metrics["hypothesis_selection"]
        assert m.failure_modes == {"INCORRECT": 1}

    def test_is_partial_always_true(self):
        report = self._make_report([])
        assert report.is_partial is True


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


class TestFormatReport:
    """format_benchmark_report produces readable output."""

    def test_basic_formatting(self):
        report = BenchmarkReport(
            timestamp="2026-03-11T12:00:00",
            n_srcs=1,
            n_srcs_completed=1,
            n_tasks=2,
            types_exercised=["infer_target"],
            types_missing=["causal_effect"],
            overall_submission_rate=1.0,
            is_partial=True,
        )
        text = format_benchmark_report(report)
        assert "BENCHMARK REPORT (partial)" in text
        assert "infer_target" in text
        assert "PARTIAL: True" in text

    def test_per_type_table(self):
        report = BenchmarkReport(
            timestamp="test",
            n_srcs=1,
            n_srcs_completed=1,
            n_tasks=1,
            type_metrics={
                "infer_target": TypeMetrics(
                    count=1, submitted=1, scores=[0.1],
                    verdicts={"EXCELLENT": 1},
                ),
            },
        )
        text = format_benchmark_report(report)
        assert "infer_target" in text
        assert "EXCELLENT" in text
