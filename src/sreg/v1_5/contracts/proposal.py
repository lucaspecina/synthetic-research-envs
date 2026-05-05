"""Contratos del flujo multi-agente de diseño de preguntas.

Los Explorer/Designers (N en paralelo, multi-turn) producen
`QuestionProposal` cada uno. El Selector (advisory) los lee, elige las
mejores, y produce `SelectionReport` + `QuestionsBundle` final.

Ver `research/notes/multi_explorer_redesign.md` para el flujo completo.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sreg.v1_5.contracts.phenomena import EvidenceArtifact
from sreg.v1_5.contracts.questions import AnswerKey, Rubric


class QuestionProposal(BaseModel):
    """Una pregunta candidata propuesta por un Explorer/Designer.

    Pasa por el Selector (que elige cuáles van al `QuestionsBundle` final).
    El `status` indica el resultado del intento del Explorer:

    - `verified`: el Explorer confirmó el `IntendedPhenomenon` y produjo
      una propuesta completa. **Caso típico.** En este estado todos los
      campos de la propuesta son obligatorios:
      `question_text`, `rubric_draft`, `answer_key`, `answer_key_provenance`.
    - `proposed`: armado pero pendiente de verificación final (uso interno
      transitorio, raro en output).
    - `rejected_unconfirmed`: el Explorer NO pudo confirmar el fenómeno;
      reporta el problema en `failure_reason` y termina sin proponer
      pregunta alternativa creativa (regla "verify first / propose later").
      En este estado los campos de la propuesta son opcionales.
    """

    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    author_run_id: str
    """Identificador del Explorer/Designer que la generó. Ej:
    `explorer_run_2_focus_collider`."""
    focus: str
    """En qué se concentró el explorador para generar esta propuesta.
    Puede ser un `IntendedPhenomenon.id` o `"wildcard"`."""
    status: Literal["proposed", "verified", "rejected_unconfirmed"]
    question_text: str | None = None
    rubric_draft: Rubric | None = None
    answer_key: AnswerKey | None = None
    answer_key_provenance: list[EvidenceArtifact] = Field(default_factory=list)
    """Scripts ejecutables que respaldan el `AnswerKey`. Mínimo 1 cuando
    `status` ∈ {`proposed`, `verified`}; puede estar vacío cuando
    `status="rejected_unconfirmed"`."""
    failure_reason: str | None = None
    """Solo para `status="rejected_unconfirmed"`: por qué el Explorer
    no pudo confirmar el fenómeno (ej. "el collider en LBW no se
    materializa: la asociación cruda y la estratificada coinciden")."""
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_status_consistency(self) -> "QuestionProposal":
        if self.status in ("proposed", "verified"):
            missing = []
            if self.question_text is None:
                missing.append("question_text")
            if self.rubric_draft is None:
                missing.append("rubric_draft")
            if self.answer_key is None:
                missing.append("answer_key")
            if not self.answer_key_provenance:
                missing.append("answer_key_provenance (mínimo 1)")
            if missing:
                raise ValueError(
                    f"QuestionProposal con status='{self.status}' requiere "
                    f"todos los campos de la propuesta: {missing} faltan."
                )
            if self.failure_reason is not None:
                raise ValueError(
                    f"QuestionProposal con status='{self.status}' NO debe "
                    f"tener `failure_reason` (eso es solo para "
                    f"'rejected_unconfirmed')."
                )
        elif self.status == "rejected_unconfirmed":
            if self.failure_reason is None:
                raise ValueError(
                    "QuestionProposal con status='rejected_unconfirmed' "
                    "requiere `failure_reason` explicando por qué."
                )
        return self


class SelectionReport(BaseModel):
    """Output advisory del Selector. NO tiene autoridad de invalidar.

    El `Validator` transversal lee este reporte y decide si el caso pasa
    o se re-itera (ver `ValidationReport.target_to_reiterate`).
    """

    model_config = ConfigDict(extra="forbid")

    selected_proposals: list[str]
    """`proposal_id`s que entraron al `QuestionsBundle` final."""
    rejected_proposals: list[str] = Field(default_factory=list)
    """`proposal_id`s que el Selector descartó."""
    merged_proposals: dict[str, list[str]] = Field(default_factory=dict)
    """Si el Selector fusionó propuestas duplicadas:
    `{final_id: [source_proposal_ids]}`."""
    quality_issues: list[str] = Field(default_factory=list)
    """Problemas detectados en el pool. Ej: 'todas las propuestas son del
    mismo focus', 'evidencia insuficiente en X', 'baja diversidad'."""
    diversity_score: float | None = None
    """Estimación de qué tan diversas son las preguntas finales (0-1).
    None si el Selector no la computa."""


__all__ = ["QuestionProposal", "SelectionReport"]
