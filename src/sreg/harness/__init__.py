"""Harness: dataset generation and evaluation."""

from sreg.harness.agent_trajectory import (
    AgentTrajectory,
    AgentTrajectoryStep,
    export_agent_trajectories,
    extract_agent_trajectory,
)
from sreg.harness.comparison import TrajectoryComparison, compare_trajectories
from sreg.harness.eval import BatchEvaluator, BatchResult, ProblemResult
from sreg.harness.quality import (
    GeneratorDiversityMetrics,
    QualitySuiteReport,
    TaskQualityMetrics,
    WorldQualityMetrics,
    WorldReport,
    compute_generator_diversity,
    compute_task_quality,
    compute_world_quality,
    print_quality_report,
    run_quality_suite,
)
from sreg.harness.benchmark import (
    BenchmarkReport,
    BenchmarkRunner,
    SRCResult,
    TaskResult,
    TypeMetrics,
    classify_failure_mode,
    classify_task_verdict,
    format_benchmark_report,
    save_benchmark,
)
from sreg.harness.trajectory import TeacherTrajectory, TrajectoryStep, generate_teacher_trajectory

__all__ = [
    "AgentTrajectory",
    "AgentTrajectoryStep",
    "BatchEvaluator",
    "BatchResult",
    "BenchmarkReport",
    "BenchmarkRunner",
    "GeneratorDiversityMetrics",
    "ProblemResult",
    "QualitySuiteReport",
    "SRCResult",
    "TaskQualityMetrics",
    "TaskResult",
    "TeacherTrajectory",
    "TrajectoryComparison",
    "TrajectoryStep",
    "TypeMetrics",
    "WorldQualityMetrics",
    "WorldReport",
    "classify_failure_mode",
    "classify_task_verdict",
    "compare_trajectories",
    "compute_generator_diversity",
    "compute_task_quality",
    "compute_world_quality",
    "export_agent_trajectories",
    "extract_agent_trajectory",
    "format_benchmark_report",
    "generate_teacher_trajectory",
    "print_quality_report",
    "run_quality_suite",
    "save_benchmark",
]
