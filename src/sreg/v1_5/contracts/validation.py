"""Contratos del Validator transversal del Designer.

El Validator es el ÚNICO ÁRBITRO con autoridad de invalidar upstream y
mandar a re-iterar. Tiene vista global (lee `WorldSpec`,
`intended_phenomena`, `QuestionProposals`, `SelectionReport`,
`ResearchCase`). Su rol incluye intentos adversariales: tratar de
"hackear" el caso sin investigar, para detectar GQs triviales.

Si invalida, debe declarar `target_to_reiterate` para que el sistema
sepa qué etapa rehacer (ver `multi_explorer_redesign.md`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ValidationArtifact = Literal["world", "phenomena", "questions", "case", "rubric"]
ReiterationTarget = Literal["world", "explorers", "case"]
"""Etapa a la que el Validator manda a re-iterar:
- `"world"`: rehacer World Architect (WorldSpec + intended_phenomena).
- `"explorers"`: re-correr Explorer/Designers + Selector sobre el mismo
  WorldSpec.
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
    def _check_target_consistency(self) -> "ValidationReport":
        if self.passed and self.target_to_reiterate is not None:
            raise ValueError(
                "ValidationReport con passed=True NO puede tener "
                "target_to_reiterate. Debe ser None."
            )
        if not self.passed and self.target_to_reiterate is None:
            raise ValueError(
                "ValidationReport con passed=False DEBE declarar "
                "target_to_reiterate ('world', 'explorers' o 'case')."
            )
        return self


__all__ = [
    "ValidationArtifact",
    "ReiterationTarget",
    "ValidationIssue",
    "AdversarialAttempt",
    "ValidationReport",
]
