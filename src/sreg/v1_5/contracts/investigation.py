"""Contratos del runtime del Investigator.

`InvestigationLog` se registra siempre, pero **no se evalúa en MVP** —
habilita trace scoring como feature futura (issue #53). El campo
`epistemic_tag` es vocabulario Corral (H/T/E/J/U/C) opcional, también
telemetría no-scoring en v1.5.

`InvestigatorAction.kind` en v1.5 NO incluye `observe`, `intervene`,
`simulate` — esas son acciones del Sherlock multi-turno (v2, Epic #64).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Claim(BaseModel):
    """Una afirmación del Investigator en prosa libre.

    Sin formato estructural impuesto — el Investigator escribe como
    quiere. La estructura aparece después en evaluación (rubric + judge).
    """

    model_config = ConfigDict(extra="forbid")

    text: str
    cited_evidence: list[str] = Field(default_factory=list)
    """Identificadores de spans citados (líneas, datasets, queries
    propias) que respaldan la claim. Permite al Evaluator chequear
    si la evidencia citada existe."""


class HypothesisEntry(BaseModel):
    """Una hipótesis formulada por el Investigator durante la investigación."""

    model_config = ConfigDict(extra="forbid")

    step: int
    text: str
    rationale: str | None = None


class InvestigatorAction(BaseModel):
    """Una acción del Investigator.

    `kind` es el TIPO TÉCNICO de la acción (cómo se ejecuta).
    `epistemic_tag` es el TIPO EPISTÉMICO (qué función cumple en el
    razonamiento), inspirado en Corral. El tag es opcional en MVP — solo
    se registra, no se evalúa. Habilita trace scoring y rewards de
    proceso como feature futura (issue #53).
    """

    model_config = ConfigDict(extra="forbid")

    step: int
    timestamp: datetime
    kind: Literal["python_exec", "hypothesis", "pivot", "submit"]
    """Acciones de v1.5 (single-turn, estático). v2 agrega
    `observe`/`intervene`/`simulate`."""
    payload: dict[str, Any]
    rationale: str | None = None
    """Por qué esta acción. Opcional pero recomendado — el prompt del
    Investigator lo solicita."""
    epistemic_tag: Literal["H", "T", "E", "J", "U", "C"] | None = None
    """Vocabulario Corral (Ríos-García/Jablonka 2026):
    H=hypothesis, T=test, E=evidence, J=judgment, U=update, C=commitment.
    Ortogonal a `kind`: una `python_exec` puede ser E (gathering evidence)
    o T (testing prediction) según su rol epistémico. NO se usa en
    scoring de MVP."""


class InvestigationLog(BaseModel):
    """Log estructurado de la investigación. Registrado siempre.

    En MVP solo se persiste, no se evalúa. Habilita trace scoring (#53)
    y rewards de proceso a futuro sin requerir rehacer tools después.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str
    actions: list[InvestigatorAction]
    hypotheses_log: list[HypothesisEntry] = Field(default_factory=list)
    final_claims: list[Claim] = Field(default_factory=list)


__all__ = [
    "Claim",
    "HypothesisEntry",
    "InvestigatorAction",
    "InvestigationLog",
]
