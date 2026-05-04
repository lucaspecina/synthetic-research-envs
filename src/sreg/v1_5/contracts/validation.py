"""Contratos del Validator transversal del Designer.

El Validator tiene vista global (lee `WorldSpec`, `PhenomenaManifest`,
`QuestionsBundle`, `ResearchCase`, `Rubric`s) y puede invalidar upstream.
Su rol incluye intentos adversariales: tratar de "hackear" el caso
sin investigar, para detectar GQs triviales.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ValidationArtifact = Literal["world", "phenomena", "questions", "case", "rubric"]


class ValidationIssue(BaseModel):
    """Un problema concreto detectado por el Validator."""

    model_config = ConfigDict(extra="forbid")

    artifact: ValidationArtifact
    severity: Literal["error", "warning"]
    description: str


class AdversarialAttempt(BaseModel):
    """Un intento adversarial del Validator de responder sin investigar.

    Si `succeeded=True`, la GQ probablemente es trivial (responde a priors
    sin necesidad de mirar los datos del caso) y debe descartarse o
    ajustarse.
    """

    model_config = ConfigDict(extra="forbid")

    attack: str
    """Qué intentó. Ej: 'responder GQ1 solo con el brief, sin datasets'."""
    succeeded: bool
    notes: str | None = None


class ValidationReport(BaseModel):
    """Output del Validator transversal."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    invalidated_artifacts: list[ValidationArtifact] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)
    adversarial_attempts: list[AdversarialAttempt] = Field(default_factory=list)


__all__ = [
    "ValidationArtifact",
    "ValidationIssue",
    "AdversarialAttempt",
    "ValidationReport",
]
