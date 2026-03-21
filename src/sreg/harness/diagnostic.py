"""DiagnosticRunner: real E2E environment quality evaluation.

Generates SRCs via the real orchestrator, runs agent on each task,
collects per-eval-type metrics with type-aware failure classification.

This is Level 2 QA (periodic environment diagnostic), NOT Level 1
(pre-commit tests) nor Level 3 (transfer benchmark). It validates
that the generator produces quality environments. It ALWAYS uses
the real system with LLM.

IMPORTANT: This diagnostic is partial and evolving. It does not yet
cover all aspects of environment quality (e.g. rich actions, narrative
quality). Failure classifications are task-type-dependent — the same
behavior (e.g. zero observations + correct answer) means different
things for different eval types.
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from sreg.agent.agent import AgentResult, AgentSolver
from sreg.models.task import Task, TaskType
from sreg.models.world import World
from sreg.orchestrator.orchestrator import Orchestrator
from sreg.tools.verifier import VerifierTool
from sreg.tools.world_check import WorldCheckTool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type-aware classification
# ---------------------------------------------------------------------------

# Distribution types: scored by KL divergence (lower is better)
_DISTRIBUTION_TYPES = {
    TaskType.INFER_TARGET,
    TaskType.CAUSAL_EFFECT,
    TaskType.INFER_LATENT_CAUSE,
}

# Numeric types: scored by relative error (0-1, higher is better)
_NUMERIC_TYPES = {
    TaskType.ATE,
    TaskType.MEDIATION,
}

# Binary/choice types: scored 0 (wrong) or 1 (correct)
_ACCURACY_TYPES = {
    TaskType.HYPOTHESIS_SELECTION,
    TaskType.COMPARE_INTERVENTIONS,
    TaskType.SHOULD_CONDITION,
    TaskType.BEST_INTERVENTION,
    TaskType.NEXT_BEST_OBSERVATION,
    TaskType.ADJUSTMENT_SET,
    TaskType.INTERACTION,
}


def classify_task_verdict(task_type: TaskType, score: float | None) -> str:
    """Assign a verdict label based on task type and score.

    Distribution types use KL thresholds.
    Accuracy types use correct/incorrect.
    """
    if score is None:
        return "NO_SCORE"

    if task_type in _DISTRIBUTION_TYPES:
        if score < 0.1:
            return "EXCELLENT"
        elif score < 0.5:
            return "GOOD"
        elif score < 1.5:
            return "FAIR"
        else:
            return "POOR"
    else:
        # Accuracy-based: 1.0 = correct, 0.0 = wrong, partial in between
        if score >= 0.99:
            return "CORRECT"
        elif score > 0.0:
            return "PARTIAL"
        else:
            return "WRONG"


def classify_failure_mode(
    task_type: TaskType,
    submitted: bool,
    score: float | None,
    budget_used: int,
    format_errors: int,
    error: str | None,
) -> str | None:
    """Classify the failure mode for a single task result.

    Returns None if no notable issue detected.

    Failure modes are task-type-dependent. The same behavior can mean
    different things depending on the eval type.
    """
    if error:
        return "AGENT_CRASH"
    if not submitted:
        return "NO_SUBMIT"

    if score is None:
        return "NO_SCORE"

    # Types where zero observations is expected behavior (not a failure).
    # NBO asks "what would you observe first?" — answering immediately is correct.
    # should_condition asks a theoretical causal question — may not require observations.
    _IMMEDIATE_ANSWER_OK = {
        TaskType.NEXT_BEST_OBSERVATION,
        TaskType.SHOULD_CONDITION,
    }

    # Type-specific classification
    if task_type in _DISTRIBUTION_TYPES:
        if score > 2.0:
            return "HIGH_KL"
        if budget_used == 0 and score < 0.5:
            return "ZERO_OBS_LOW_KL"
    else:
        if score == 0.0:
            return "INCORRECT"
        if budget_used == 0 and score >= 0.99:
            if task_type in _IMMEDIATE_ANSWER_OK:
                return None  # Not a failure — expected for these types
            return "ZERO_OBS_CORRECT"

    if format_errors > 0 and submitted:
        return "FORMAT_RETRY"

    return None


def compute_baseline_score(
    task_type: TaskType, correct_answer: dict[str, float] | None
) -> float | None:
    """Compute expected score of a random baseline for this task type.

    Returns None if baseline cannot be computed for this type.

    For distribution types (lower KL is better): baseline = KL(uniform || correct).
    For accuracy types (higher is better): baseline = expected random score.
    """
    if not correct_answer:
        return None

    if task_type in _DISTRIBUTION_TYPES:
        # KL of uniform vs. correct answer
        n_states = len(correct_answer)
        if n_states <= 1:
            return None
        uniform = {s: 1.0 / n_states for s in correct_answer}
        return round(VerifierTool.kl_divergence(uniform, correct_answer), 6)

    if task_type in (
        TaskType.COMPARE_INTERVENTIONS, TaskType.SHOULD_CONDITION,
        TaskType.INTERACTION,
    ):
        return 0.5  # Random binary choice

    if task_type in _NUMERIC_TYPES:
        return 0.0  # Random guess = no information about the true value

    if task_type == TaskType.HYPOTHESIS_SELECTION:
        n_hyp = len(correct_answer)
        return round(1.0 / n_hyp, 6) if n_hyp > 0 else None

    if task_type == TaskType.NEXT_BEST_OBSERVATION:
        # Expected score = mean(ig) / max(ig)
        values = list(correct_answer.values())
        max_ig = max(values) if values else 0
        if max_ig <= 0:
            return 1.0  # All zero IG, any choice equally good
        return round(sum(values) / (len(values) * max_ig), 6)

    if task_type == TaskType.BEST_INTERVENTION:
        # Expected score = mean(effect) / max(effect)
        values = list(correct_answer.values())
        max_eff = max(values) if values else 0
        if max_eff <= 0:
            return 1.0
        return round(sum(values) / (len(values) * max_eff), 6)

    # adjustment_set: too complex without knowing total possible subsets
    return None


def beats_baseline(
    task_type: TaskType, score: float | None, baseline: float | None
) -> bool | None:
    """Check if the agent's score beats the random baseline.

    For distribution types (KL): lower is better, so agent < baseline = beats.
    For accuracy types: higher is better, so agent > baseline = beats.
    Returns None if either score is unavailable.
    """
    if score is None or baseline is None:
        return None
    if task_type in _DISTRIBUTION_TYPES:
        return score < baseline  # Lower KL = better
    return score > baseline  # Higher accuracy = better


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class TaskResult(BaseModel):
    """Result of running the agent on a single task."""

    task_id: str
    task_type: str
    question: str = ""
    submitted: bool = False
    score: float | None = None
    verdict: str = ""
    failure_mode: str | None = None
    budget_used: int = 0
    num_observations: int = 0
    num_steps: int = 0
    format_errors: int = 0
    time_s: float = 0
    answer: Any = None
    error: str | None = None
    baseline_score: float | None = None
    agent_beats_baseline: bool | None = None


class SRCResult(BaseModel):
    """Result of generating and evaluating a single SRC."""

    case_id: int
    goal: str = ""
    seed: int = 0
    timestamp: str = ""
    orchestrator_completed: bool = False
    orchestrator_error: str | None = None
    orchestrator_time_s: float = 0
    worldcheck_passed: bool | None = None
    num_nodes: int = 0
    num_edges: int = 0
    scenario_title: str = ""
    eval_types: list[str] = Field(default_factory=list)
    task_results: list[TaskResult] = Field(default_factory=list)


class TypeMetrics(BaseModel):
    """Aggregated metrics for a single eval type."""

    count: int = 0
    submitted: int = 0
    scores: list[float] = Field(default_factory=list)
    format_errors: int = 0
    verdicts: dict[str, int] = Field(default_factory=dict)
    failure_modes: dict[str, int] = Field(default_factory=dict)
    baseline_scores: list[float] = Field(default_factory=list)
    n_beats_baseline: int = 0
    n_baseline_computed: int = 0


class DiagnosticReport(BaseModel):
    """Complete diagnostic report."""

    timestamp: str
    n_srcs: int
    n_srcs_completed: int
    n_tasks: int
    goals: list[str] = Field(default_factory=list)
    src_results: list[SRCResult] = Field(default_factory=list)
    type_metrics: dict[str, TypeMetrics] = Field(default_factory=dict)
    types_exercised: list[str] = Field(default_factory=list)
    types_missing: list[str] = Field(default_factory=list)
    overall_submission_rate: float = 0
    overall_format_errors: int = 0
    is_partial: bool = True  # Always true until we have full coverage


# ---------------------------------------------------------------------------
# DiagnosticRunner
# ---------------------------------------------------------------------------


class DiagnosticRunner:
    """Runs the real E2E diagnostic: orchestrator -> agent -> score.

    This diagnostic is PARTIAL and EVOLVING. It uses the real system
    (LLM orchestrator + LLM agent) and measures product quality, not
    just code correctness.
    """

    def __init__(
        self,
        agent: AgentSolver | None = None,
        max_iterations: int = 15,
    ):
        self.agent = agent or AgentSolver(max_iterations=max_iterations)
        self._checker = WorldCheckTool()

    def run(
        self,
        goals: list[str],
        seed: int = 42,
        on_src: callable | None = None,
    ) -> DiagnosticReport:
        """Run the diagnostic on a list of orchestrator goals.

        Args:
            goals: List of goal strings for the orchestrator.
            seed: Base seed (incremented per SRC).
            on_src: Optional callback(case_id, src_result) for progress.
        """
        report = DiagnosticReport(
            timestamp=datetime.now().isoformat(),
            n_srcs=len(goals),
            n_srcs_completed=0,
            n_tasks=0,
            goals=goals,
        )

        for i, goal in enumerate(goals):
            src_result = self._run_src(goal, case_id=i + 1, seed=seed + i)
            report.src_results.append(src_result)

            if src_result.orchestrator_completed:
                report.n_srcs_completed += 1

            report.n_tasks += len(src_result.task_results)

            if on_src:
                on_src(i + 1, src_result)

        # Aggregate metrics
        self._aggregate(report)
        return report

    def _run_src(self, goal: str, case_id: int, seed: int) -> SRCResult:
        """Generate one SRC and run agent on all tasks."""
        src = SRCResult(
            case_id=case_id,
            goal=goal[:200],
            seed=seed,
            timestamp=datetime.now().isoformat(),
        )

        # --- Orchestrator ---
        t0 = time.time()
        try:
            orchestrator = Orchestrator()
            orch_result = orchestrator.run(goal)
        except Exception as e:
            src.orchestrator_error = str(e)[:300]
            logger.error("Orchestrator failed for case %d: %s", case_id, e)
            return src

        src.orchestrator_time_s = round(time.time() - t0, 1)

        if not orch_result.world or not orch_result.problem:
            src.orchestrator_error = "Incomplete result"
            return src

        src.orchestrator_completed = True
        world = orch_result.world
        problem = orch_result.problem
        tasks: list[Task] = orch_result.task or []

        # Structural info
        check = self._checker.check(world)
        src.worldcheck_passed = check.passed
        src.num_nodes = len(world.nodes)
        src.num_edges = len(world.edges)
        src.scenario_title = world.scenario_title or ""
        src.eval_types = list(set(t.type.value for t in tasks))

        # --- Agent on each task ---
        for task in tasks:
            task_result = self._run_task(world, problem, task, seed)
            src.task_results.append(task_result)

        return src

    def _run_task(
        self, world: World, problem, task: Task, seed: int
    ) -> TaskResult:
        """Run agent on a single task and classify the result."""
        tr = TaskResult(
            task_id=task.id,
            task_type=task.type.value,
            question=task.question[:200] if task.question else "",
        )

        try:
            t0 = time.time()
            result: AgentResult = self.agent.solve(
                world, problem, seed=seed, task=task
            )
            tr.time_s = round(time.time() - t0, 1)

            tr.submitted = result.submitted_answer is not None
            tr.budget_used = result.budget_used
            tr.num_observations = len(result.observations)
            tr.score = (
                round(result.score.functional_score, 4)
                if result.score else None
            )
            tr.answer = result.submitted_answer

            # Count format errors and steps from messages
            for msg in result.messages:
                if msg.get("role") == "tool":
                    try:
                        parsed = json.loads(msg.get("content", ""))
                        if "error" in parsed:
                            tr.format_errors += 1
                    except (json.JSONDecodeError, TypeError):
                        pass
                elif msg.get("role") == "assistant":
                    tr.num_steps += len(msg.get("tool_calls", []))

        except Exception as e:
            tr.error = str(e)[:300]
            logger.error("Agent failed on task %s: %s", task.id, e)

        # Type-aware classification
        tr.verdict = classify_task_verdict(task.type, tr.score)
        tr.failure_mode = classify_failure_mode(
            task.type, tr.submitted, tr.score,
            tr.budget_used, tr.format_errors, tr.error,
        )

        # Baseline comparison
        tr.baseline_score = compute_baseline_score(task.type, task.correct_answer)
        tr.agent_beats_baseline = beats_baseline(
            task.type, tr.score, tr.baseline_score
        )

        return tr

    def _aggregate(self, report: DiagnosticReport) -> None:
        """Compute aggregated per-type metrics."""
        type_data: dict[str, TypeMetrics] = defaultdict(TypeMetrics)

        for src in report.src_results:
            for tr in src.task_results:
                m = type_data[tr.task_type]
                m.count += 1
                if tr.submitted:
                    m.submitted += 1
                if tr.score is not None:
                    m.scores.append(tr.score)
                m.format_errors += tr.format_errors
                m.verdicts[tr.verdict] = m.verdicts.get(tr.verdict, 0) + 1
                if tr.failure_mode:
                    m.failure_modes[tr.failure_mode] = (
                        m.failure_modes.get(tr.failure_mode, 0) + 1
                    )
                if tr.baseline_score is not None:
                    m.baseline_scores.append(tr.baseline_score)
                    m.n_baseline_computed += 1
                    if tr.agent_beats_baseline is True:
                        m.n_beats_baseline += 1

        report.type_metrics = dict(type_data)

        # Types coverage
        all_possible = {t.value for t in TaskType}
        exercised = set(report.type_metrics.keys())
        report.types_exercised = sorted(exercised)
        report.types_missing = sorted(all_possible - exercised)

        # Overall stats
        total = report.n_tasks
        if total > 0:
            total_sub = sum(m.submitted for m in report.type_metrics.values())
            report.overall_submission_rate = round(total_sub / total, 4)
        report.overall_format_errors = sum(
            m.format_errors for m in report.type_metrics.values()
        )


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def format_diagnostic_report(report: DiagnosticReport) -> str:
    """Format a DiagnosticReport as human-readable text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("DIAGNOSTIC REPORT (partial)")
    lines.append("=" * 70)
    lines.append(f"  Timestamp: {report.timestamp}")
    lines.append(f"  SRCs: {report.n_srcs_completed}/{report.n_srcs} completed")
    lines.append(f"  Tasks: {report.n_tasks}")
    lines.append(
        f"  Submission rate: {report.overall_submission_rate*100:.0f}%"
    )
    if report.overall_format_errors:
        lines.append(f"  Format errors: {report.overall_format_errors}")

    # Per-type breakdown
    lines.append(f"\n{'='*70}")
    lines.append("PER EVAL TYPE")
    lines.append(f"{'='*70}")
    lines.append(
        f"  {'Type':<25} {'N':>3} {'Sub%':>5} {'Score':>8} "
        f"{'Verdicts':<25} {'Failures'}"
    )
    lines.append("  " + "-" * 80)

    for tt in sorted(report.type_metrics.keys()):
        m = report.type_metrics[tt]
        n = m.count
        sub_pct = f"{m.submitted/n*100:.0f}%" if n > 0 else "-"
        if m.scores:
            mean_s = sum(m.scores) / len(m.scores)
            score_str = f"{mean_s:.4f}"
        else:
            score_str = "N/A"
        verdicts = ", ".join(
            f"{v}:{c}" for v, c in sorted(m.verdicts.items())
        )[:25]
        failures = ", ".join(
            f"{f}:{c}" for f, c in sorted(m.failure_modes.items())
        ) or "-"
        lines.append(
            f"  {tt:<25} {n:>3} {sub_pct:>5} {score_str:>8} "
            f"{verdicts:<25} {failures}"
        )

    # Baseline comparison
    has_baseline = any(
        m.n_baseline_computed > 0 for m in report.type_metrics.values()
    )
    if has_baseline:
        lines.append(f"\n{'='*70}")
        lines.append("BASELINE COMPARISON (random guess)")
        lines.append(f"{'='*70}")
        lines.append(
            f"  {'Type':<25} {'N':>3} {'Agent':>8} {'Random':>8} "
            f"{'Beats%':>7} {'Note'}"
        )
        lines.append("  " + "-" * 70)

        for tt in sorted(report.type_metrics.keys()):
            m = report.type_metrics[tt]
            if m.n_baseline_computed == 0:
                continue
            n = m.n_baseline_computed
            mean_baseline = sum(m.baseline_scores) / n
            # Agent mean (only tasks with baseline)
            scored = [s for s in m.scores if s is not None]
            mean_agent = sum(scored) / len(scored) if scored else float("nan")
            beat_pct = f"{m.n_beats_baseline/n*100:.0f}%"

            tt_enum = TaskType(tt)
            if tt_enum in _DISTRIBUTION_TYPES:
                note = "lower=better"
                agent_str = f"{mean_agent:.4f}"
                base_str = f"{mean_baseline:.4f}"
            else:
                note = "higher=better"
                agent_str = f"{mean_agent:.4f}"
                base_str = f"{mean_baseline:.4f}"

            lines.append(
                f"  {tt:<25} {n:>3} {agent_str:>8} {base_str:>8} "
                f"{beat_pct:>7} {note}"
            )

    # Failure modes (grouped by type)
    all_failures = defaultdict(lambda: defaultdict(int))
    for src in report.src_results:
        for tr in src.task_results:
            if tr.failure_mode:
                all_failures[tr.task_type][tr.failure_mode] += 1

    if any(all_failures.values()):
        lines.append(f"\n{'='*70}")
        lines.append("FAILURE MODES BY TYPE")
        lines.append(f"{'='*70}")
        for tt in sorted(all_failures.keys()):
            modes = all_failures[tt]
            mode_str = ", ".join(
                f"{m}:{c}" for m, c in sorted(modes.items(), key=lambda x: -x[1])
            )
            lines.append(f"  {tt}: {mode_str}")

    # Per-SRC table
    lines.append(f"\n{'='*70}")
    lines.append("PER SRC")
    lines.append(f"{'='*70}")
    lines.append(
        f"  {'ID':>3} {'Orch':>5} {'WC':>4} {'Tasks':>5} "
        f"{'Sub':>4} {'Types':<35} {'Title'}"
    )
    lines.append("  " + "-" * 80)

    for src in report.src_results:
        cid = src.case_id
        orch = "OK" if src.orchestrator_completed else "FAIL"
        wc_val = src.worldcheck_passed
        wc = "PASS" if wc_val else "FAIL" if wc_val is not None else "-"
        n_tasks = len(src.task_results)
        n_sub = sum(1 for tr in src.task_results if tr.submitted)
        types = ", ".join(sorted(src.eval_types))[:35]
        title = src.scenario_title[:25]
        lines.append(
            f"  {cid:>3} {orch:>5} {wc:>4} {n_tasks:>5} "
            f"{n_sub:>4} {types:<35} {title}"
        )

    # Coverage
    lines.append(f"\n{'='*70}")
    lines.append("COVERAGE")
    lines.append(f"{'='*70}")
    lines.append(f"  Types exercised: {report.types_exercised}")
    if report.types_missing:
        lines.append(f"  Types NOT exercised: {report.types_missing}")
    else:
        lines.append("  All 9 eval types exercised")
    lines.append(f"  Benchmark is PARTIAL: {report.is_partial}")

    lines.append("=" * 70)
    return "\n".join(lines)


def save_diagnostic(report: DiagnosticReport, output_dir: Path) -> None:
    """Save a diagnostic report to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Report text
    text = format_diagnostic_report(report)
    (output_dir / "report.txt").write_text(text, encoding="utf-8")

    # Summary JSON (no trajectories)
    summary = report.model_dump(mode="json")
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )

    # Config
    config = {
        "n_srcs": report.n_srcs,
        "goals": report.goals,
        "timestamp": report.timestamp,
        "is_partial": report.is_partial,
    }
    (output_dir / "config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )


__all__ = [
    "DiagnosticReport",
    "DiagnosticRunner",
    "SRCResult",
    "TaskResult",
    "TypeMetrics",
    "beats_baseline",
    "classify_failure_mode",
    "classify_task_verdict",
    "compute_baseline_score",
    "format_diagnostic_report",
    "save_diagnostic",
]
