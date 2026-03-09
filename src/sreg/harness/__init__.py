"""Harness: dataset generation and evaluation."""

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
from sreg.harness.trajectory import TeacherTrajectory, TrajectoryStep, generate_teacher_trajectory

__all__ = [
    "BatchEvaluator",
    "BatchResult",
    "GeneratorDiversityMetrics",
    "ProblemResult",
    "QualitySuiteReport",
    "TaskQualityMetrics",
    "TeacherTrajectory",
    "TrajectoryStep",
    "WorldQualityMetrics",
    "WorldReport",
    "compute_generator_diversity",
    "compute_task_quality",
    "compute_world_quality",
    "generate_teacher_trajectory",
    "print_quality_report",
    "run_quality_suite",
]
