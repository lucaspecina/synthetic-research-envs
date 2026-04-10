"""Data contracts for SREG."""

from sreg.models.benchmark import BenchmarkComparison, BenchmarkResult, BenchmarkStatus
from sreg.models.case_plan import CasePlan, EvalQuestionPlan
from sreg.models.episode import Action, ActionDef, ActionType, Episode, Observation, StepResult
from sreg.models.open_investigation import (
    Assertion,
    AssertionKind,
    AtomicSpec,
    AtomVerdict,
    ClaimCard,
    ClaimSubmission,
    ClaimVerdict,
    Comparison,
    ComparisonKind,
    EpisodeScore,
    EvidenceRef,
    FamilyAtom,
    FamilyKey,
    Measurement,
    MeasurementKind,
    QueryArm,
    QueryKind,
    SalienceFamily,
    SalienceMap,
)
from sreg.models.research_problem import (
    AvailableAction,
    DataAsset,
    ResearchActionType,
    ResearchProblem,
)
from sreg.models.scm_spec import SCMSpec, SCMVariableSpec
from sreg.models.score import Score, StepScore
from sreg.models.task import Task, TaskBundle, TaskSpec, TaskType
from sreg.models.teacher import TeacherOutput

__all__ = [
    "Action",
    "ActionDef",
    "ActionType",
    "Assertion",
    "AssertionKind",
    "AtomicSpec",
    "AtomVerdict",
    "AvailableAction",
    "BenchmarkComparison",
    "BenchmarkResult",
    "BenchmarkStatus",
    "CasePlan",
    "ClaimCard",
    "ClaimSubmission",
    "ClaimVerdict",
    "Comparison",
    "ComparisonKind",
    "DataAsset",
    "Episode",
    "EpisodeScore",
    "EvalQuestionPlan",
    "EvidenceRef",
    "FamilyAtom",
    "FamilyKey",
    "Measurement",
    "MeasurementKind",
    "Observation",
    "QueryArm",
    "QueryKind",
    "ResearchActionType",
    "ResearchProblem",
    "SCMSpec",
    "SCMVariableSpec",
    "SalienceFamily",
    "SalienceMap",
    "Score",
    "StepResult",
    "StepScore",
    "Task",
    "TaskBundle",
    "TaskSpec",
    "TaskType",
    "TeacherOutput",
]
