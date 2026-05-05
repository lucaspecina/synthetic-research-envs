"""Contratos del Validator transversal del Designer (post Ronda 13).

El Validator transversal es el ÚNICO ÁRBITRO con autoridad de invalidar
upstream y mandar a re-iterar. Tiene vista global (lee `WorldSpec`,
`intended_phenomena`, `ValidatedPhenomena`, `QuestionsBundle`,
`ResearchCase`). Su rol incluye intentos adversariales: tratar de
"hackear" el caso sin investigar, para detectar GQs triviales.

Si invalida, debe declarar `target_to_reiterate` para que el sistema
sepa qué etapa rehacer (ver `research/notes/multi_explorer_redesign.md`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ValidationArtifact = Literal["world", "phenomena", "questions", "case", "rubric"]
ReiterationTarget = Literal["world", "designer", "case"]
"""Etapa a la que el Validator manda a re-iterar:
- `"world"`: rehacer World Architect (WorldSpec + intended_phenomena +
  loop con Validators).
- `"designer"`: re-correr Question Designer sobre los mismos
  `ValidatedPhenomena` (e.g., reformular GoldQuestions, ajustar Rubrics).
- `"case"`: rehacer solo Case Writer (brief, datasets, tools).
"""


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
    """Output del Validator transversal.

    Si `passed=False`, debe declarar `target_to_reiterate` para que el
    sistema sepa qué etapa rehacer. Si `passed=True`, el target debe
    quedar en `None`.
    """

    model_config = ConfigDict(extra="forbid")

    passed: bool
    invalidated_artifacts: list[ValidationArtifact] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)
    adversarial_attempts: list[AdversarialAttempt] = Field(default_factory=list)
    target_to_reiterate: ReiterationTarget | None = None
    """Etapa que el Validator quiere rehacer cuando `passed=False`.
    Si `passed=True`, debe ser `None`."""

    @model_validator(mode="after")
    def _check_consistency(self) -> "ValidationReport":
        if self.passed and self.target_to_reiterate is not None:
            raise ValueError(
                "ValidationReport con passed=True NO puede tener "
                "target_to_reiterate. Debe ser None."
            )
        if not self.passed:
            if self.target_to_reiterate is None:
                raise ValueError(
                    "ValidationReport con passed=False DEBE declarar "
                    "target_to_reiterate ('world', 'designer' o 'case')."
                )
            if not self.issues and not self.invalidated_artifacts:
                raise ValueError(
                    "ValidationReport con passed=False DEBE tener al menos "
                    "un `issue` o un `invalidated_artifact` para que el "
                    "routing sea accionable."
                )
        return self


__all__ = [
    "ValidationArtifact",
    "ReiterationTarget",
    "ValidationIssue",
    "AdversarialAttempt",
    "ValidationReport",
]
