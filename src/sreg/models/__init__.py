"""Data contracts for SREG."""

from sreg.models.agent_tools import AgentTool, AgentToolset
from sreg.models.benchmark import BenchmarkComparison, BenchmarkResult, BenchmarkStatus
from sreg.models.case_plan import CasePlan, EvalQuestionPlan
from sreg.models.code_exec import CodeExecConfig, CodeExecResult, ExecStatus
from sreg.models.dag_spec import DAGNodeSpec, DAGSpec
from sreg.models.env_protocol import EnvAction, EnvObservation, EnvStepResult
from sreg.models.episode import Action, ActionDef, ActionType, Episode, Observation, StepResult
from sreg.models.research_problem import (
    AvailableAction,
    DataAsset,
    ResearchActionType,
    ResearchProblem,
)
from sreg.models.score import Score, StepScore
from sreg.models.task import Task, TaskBundle, TaskSpec, TaskType
from sreg.models.teacher import TeacherOutput
from sreg.models.world import CPD, DifficultyProfile, Edge, Node, NodeType, World

__all__ = [
    "Action",
    "ActionDef",
    "ActionType",
    "AgentTool",
    "AgentToolset",
    "AvailableAction",
    "BenchmarkComparison",
    "BenchmarkResult",
    "BenchmarkStatus",
    "CPD",
    "CasePlan",
    "CodeExecConfig",
    "CodeExecResult",
    "DAGNodeSpec",
    "DAGSpec",
    "DataAsset",
    "DifficultyProfile",
    "Edge",
    "EnvAction",
    "EnvObservation",
    "EnvStepResult",
    "Episode",
    "EvalQuestionPlan",
    "ExecStatus",
    "Node",
    "NodeType",
    "Observation",
    "ResearchActionType",
    "ResearchProblem",
    "Score",
    "StepResult",
    "StepScore",
    "Task",
    "TaskBundle",
    "TaskSpec",
    "TaskType",
    "TeacherOutput",
    "World",
]
