"""Tests for DiagnosticRunner classification and aggregation logic."""

from sreg.harness.diagnostic import (
    DiagnosticReport,
    DiagnosticRunner,
    SRCResult,
    TaskResult,
    TypeMetrics,
    beats_baseline,
    classify_failure_mode,
    classify_task_verdict,
    compute_baseline_score,
    format_diagnostic_report,
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

    def test_nbo_zero_obs_is_not_failure(self):
        """NBO with 0 observations and correct answer is expected behavior."""
        fm = classify_failure_mode(
            TaskType.NEXT_BEST_OBSERVATION, True, 1.0, 0, 0, None
        )
        assert fm is None  # Not a failure — immediate answer is valid for NBO

    def test_should_condition_zero_obs_is_not_failure(self):
        """should_condition with 0 observations and correct answer is expected."""
        fm = classify_failure_mode(
            TaskType.SHOULD_CONDITION, True, 1.0, 0, 0, None
        )
        assert fm is None  # Not a failure — theoretical question

    def test_other_type_zero_obs_still_flagged(self):
        """Other types with 0 observations and correct answer stay ZERO_OBS_CORRECT."""
        fm = classify_failure_mode(
            TaskType.COMPARE_INTERVENTIONS, True, 1.0, 0, 0, None
        )
        assert fm == "ZERO_OBS_CORRECT"


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


class TestAggregation:
    """DiagnosticRunner._aggregate populates type_metrics correctly."""

    def _make_report(self, task_results):
        """Create a report with a single SRC containing the given tasks."""
        src = SRCResult(
            case_id=1,
            orchestrator_completed=True,
            eval_types=[tr.task_type for tr in task_results],
            task_results=task_results,
        )
        report = DiagnosticReport(
            timestamp="test",
            n_srcs=1,
            n_srcs_completed=1,
            n_tasks=len(task_results),
            src_results=[src],
        )
        runner = DiagnosticRunner.__new__(DiagnosticRunner)
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
    """format_diagnostic_report produces readable output."""

    def test_basic_formatting(self):
        report = DiagnosticReport(
            timestamp="2026-03-11T12:00:00",
            n_srcs=1,
            n_srcs_completed=1,
            n_tasks=2,
            types_exercised=["infer_target"],
            types_missing=["causal_effect"],
            overall_submission_rate=1.0,
            is_partial=True,
        )
        text = format_diagnostic_report(report)
        assert "DIAGNOSTIC REPORT (partial)" in text
        assert "infer_target" in text
        assert "PARTIAL: True" in text

    def test_per_type_table(self):
        report = DiagnosticReport(
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
        text = format_diagnostic_report(report)
        assert "infer_target" in text
        assert "EXCELLENT" in text

    def test_baseline_section_shown(self):
        """Report shows baseline comparison when baseline data exists."""
        report = DiagnosticReport(
            timestamp="test",
            n_srcs=1,
            n_srcs_completed=1,
            n_tasks=2,
            type_metrics={
                "compare_interventions": TypeMetrics(
                    count=2, submitted=2, scores=[1.0, 0.0],
                    baseline_scores=[0.5, 0.5],
                    n_baseline_computed=2, n_beats_baseline=1,
                ),
            },
        )
        text = format_diagnostic_report(report)
        assert "BASELINE COMPARISON" in text
        assert "random" in text.lower()


# ---------------------------------------------------------------------------
# compute_baseline_score
# ---------------------------------------------------------------------------


class TestComputeBaseline:
    """Baseline score computation for each task type."""

    def test_distribution_uniform_kl(self):
        """For infer_target: baseline = KL(uniform || correct)."""
        correct = {"low": 0.8, "high": 0.2}
        baseline = compute_baseline_score(TaskType.INFER_TARGET, correct)
        assert baseline is not None
        # Uniform = {low: 0.5, high: 0.5}, correct = {low: 0.8, high: 0.2}
        # KL(uniform || correct) > 0
        assert baseline > 0

    def test_distribution_uniform_vs_uniform(self):
        """If correct IS uniform, baseline KL should be ~0."""
        correct = {"a": 0.5, "b": 0.5}
        baseline = compute_baseline_score(TaskType.INFER_TARGET, correct)
        assert baseline is not None
        assert baseline < 0.01  # Essentially zero

    def test_causal_effect_baseline(self):
        correct = {"low": 0.3, "mid": 0.4, "high": 0.3}
        baseline = compute_baseline_score(TaskType.CAUSAL_EFFECT, correct)
        assert baseline is not None
        assert baseline > 0

    def test_latent_cause_baseline(self):
        correct = {"cause_a": 0.9, "cause_b": 0.1}
        baseline = compute_baseline_score(TaskType.INFER_LATENT_CAUSE, correct)
        assert baseline is not None
        assert baseline > 0

    def test_binary_compare_interventions(self):
        correct = {"A": 0.8, "B": 0.3}
        baseline = compute_baseline_score(TaskType.COMPARE_INTERVENTIONS, correct)
        assert baseline == 0.5

    def test_binary_should_condition(self):
        correct = {"yes": 1.0}
        baseline = compute_baseline_score(TaskType.SHOULD_CONDITION, correct)
        assert baseline == 0.5

    def test_hypothesis_selection_3_options(self):
        correct = {"H1": 0.1, "H2": 0.5, "H3": 0.8}
        baseline = compute_baseline_score(TaskType.HYPOTHESIS_SELECTION, correct)
        assert baseline is not None
        assert abs(baseline - 1 / 3) < 0.001

    def test_hypothesis_selection_2_options(self):
        correct = {"H1": 0.1, "H2": 0.9}
        baseline = compute_baseline_score(TaskType.HYPOTHESIS_SELECTION, correct)
        assert baseline == 0.5

    def test_nbo_baseline(self):
        """NBO: baseline = mean(ig) / max(ig)."""
        correct = {"A": 0.5, "B": 1.0, "C": 0.25}
        baseline = compute_baseline_score(TaskType.NEXT_BEST_OBSERVATION, correct)
        # mean = (0.5+1.0+0.25)/3 = 0.583..., max = 1.0, ratio = 0.583
        assert baseline is not None
        assert abs(baseline - 0.583333) < 0.001

    def test_nbo_all_equal_ig(self):
        """If all nodes have same IG, baseline = 1.0 (any pick equally good)."""
        correct = {"A": 0.5, "B": 0.5, "C": 0.5}
        baseline = compute_baseline_score(TaskType.NEXT_BEST_OBSERVATION, correct)
        assert baseline == 1.0

    def test_best_intervention_baseline(self):
        """best_intervention: baseline = mean(effects) / max(effects)."""
        correct = {"x:high": 0.8, "y:low": 0.2, "z:mid": 0.4}
        baseline = compute_baseline_score(TaskType.BEST_INTERVENTION, correct)
        # mean = (0.8+0.2+0.4)/3 = 0.4667, max = 0.8, ratio = 0.5833
        assert baseline is not None
        assert abs(baseline - 0.583333) < 0.001

    def test_adjustment_set_returns_none(self):
        """adjustment_set: no baseline computable."""
        correct = {"a,b": 1.0}
        assert compute_baseline_score(TaskType.ADJUSTMENT_SET, correct) is None

    def test_empty_answer_returns_none(self):
        assert compute_baseline_score(TaskType.INFER_TARGET, {}) is None
        assert compute_baseline_score(TaskType.INFER_TARGET, None) is None


# ---------------------------------------------------------------------------
# beats_baseline
# ---------------------------------------------------------------------------


class TestBeatsBaseline:
    """Agent vs random baseline comparison."""

    def test_distribution_lower_kl_beats(self):
        """For KL-based types, lower agent score = beats baseline."""
        assert beats_baseline(TaskType.INFER_TARGET, 0.1, 0.5) is True

    def test_distribution_higher_kl_loses(self):
        assert beats_baseline(TaskType.INFER_TARGET, 0.8, 0.5) is False

    def test_accuracy_higher_beats(self):
        """For accuracy types, higher agent score = beats baseline."""
        assert beats_baseline(TaskType.COMPARE_INTERVENTIONS, 1.0, 0.5) is True

    def test_accuracy_lower_loses(self):
        assert beats_baseline(TaskType.HYPOTHESIS_SELECTION, 0.0, 0.333) is False

    def test_none_score(self):
        assert beats_baseline(TaskType.INFER_TARGET, None, 0.5) is None

    def test_none_baseline(self):
        assert beats_baseline(TaskType.ADJUSTMENT_SET, 1.0, None) is None

    def test_equal_does_not_beat_distribution(self):
        """Equal KL does not beat (strictly less is needed)."""
        assert beats_baseline(TaskType.INFER_TARGET, 0.5, 0.5) is False

    def test_equal_does_not_beat_accuracy(self):
        """Equal accuracy does not beat (strictly greater is needed)."""
        assert beats_baseline(TaskType.SHOULD_CONDITION, 0.5, 0.5) is False


# ---------------------------------------------------------------------------
# Aggregation with baselines
# ---------------------------------------------------------------------------


class TestBaselineAggregation:
    """Verify baseline stats are aggregated in type_metrics."""

    def _make_report(self, task_results):
        src = SRCResult(
            case_id=1,
            orchestrator_completed=True,
            eval_types=[tr.task_type for tr in task_results],
            task_results=task_results,
        )
        report = DiagnosticReport(
            timestamp="test",
            n_srcs=1,
            n_srcs_completed=1,
            n_tasks=len(task_results),
            src_results=[src],
        )
        runner = DiagnosticRunner.__new__(DiagnosticRunner)
        runner._aggregate(report)
        return report

    def test_baseline_scores_collected(self):
        tasks = [
            TaskResult(
                task_id="1", task_type="compare_interventions",
                submitted=True, score=1.0,
                baseline_score=0.5, agent_beats_baseline=True,
            ),
            TaskResult(
                task_id="2", task_type="compare_interventions",
                submitted=True, score=0.0,
                baseline_score=0.5, agent_beats_baseline=False,
            ),
        ]
        report = self._make_report(tasks)
        m = report.type_metrics["compare_interventions"]
        assert m.n_baseline_computed == 2
        assert m.baseline_scores == [0.5, 0.5]
        assert m.n_beats_baseline == 1

    def test_no_baseline_when_none(self):
        tasks = [
            TaskResult(
                task_id="1", task_type="adjustment_set",
                submitted=True, score=1.0,
            ),
        ]
        report = self._make_report(tasks)
        m = report.type_metrics["adjustment_set"]
        assert m.n_baseline_computed == 0
        assert m.baseline_scores == []
