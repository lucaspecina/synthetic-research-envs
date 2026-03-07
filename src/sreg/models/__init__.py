"""Data contracts for SREG."""

from sreg.models.episode import Action, ActionType, Episode, Observation, StepResult
from sreg.models.score import Score, StepScore
from sreg.models.task import Task, TaskSpec, TaskType
from sreg.models.teacher import TeacherOutput
from sreg.models.world import CPD, DifficultyProfile, Edge, Node, NodeType, World

__all__ = [
    "Action",
    "ActionType",
    "CPD",
    "DifficultyProfile",
    "Edge",
    "Episode",
    "Node",
    "NodeType",
    "Observation",
    "Score",
    "StepResult",
    "StepScore",
    "Task",
    "TaskSpec",
    "TaskType",
    "TeacherOutput",
    "World",
]
