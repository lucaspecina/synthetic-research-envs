"""Contratos del output del proceso de diseño de preguntas.

`GoldQuestion` es la pregunta canónica del caso, con `Rubric` y `AnswerKey`
ya computados en design-time. El `AnswerKey` se respalda en una lista de
`EvidenceArtifact` (scripts ejecutables) — no hay catálogo cerrado de
operaciones canónicas (ver `multi_explorer_redesign.md`).

Pesos discretos (`weight ∈ {0.08, 0.12, 0.16, 0.20}` para `GoldQuestion`,
`weight ∈ {1, 2, 3}` para `Criterion`) son anti-ajuste-fino: evitan que
el Designer micro-optimice pesos para inflar score.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sreg.v1_5.contracts.phenomena import EvidenceArtifact

ALLOWED_GQ_WEIGHTS: tuple[float, ...] = (0.08, 0.12, 0.16, 0.20)
ALLOWED_CRITERION_WEIGHTS: tuple[int, ...] = (1, 2, 3)


class AnswerKey(BaseModel):
    """Verdad de referencia de una `GoldQuestion`.

    Computada en design-time por el agente que armó la pregunta, ejecutando
    scripts contra el `Environment` (registrados en `answer_key_provenance`
    del `GoldQuestion`). El Evaluator solo lee — NO recomputa.
    """

    model_config = ConfigDict(extra="forbid")

    summary: str
    """Respuesta esperada en NL (lo que el Investigator debería decir
    en prosa para considerarse correcto)."""
    numeric: dict[str, Any]
    """Campos numéricos clave para anchors. Ej:
    `{'effect_direction': 'positive', 'magnitude_pp': 2.3}`."""


class AnswerKeyAnchor(BaseModel):
    """Referencia tipada a un campo del `AnswerKey`.

    Acredita un `Criterion` cuando el claim del Investigator matchea el
    valor del anchor según `match`.
    """

    model_config = ConfigDict(extra="forbid")

    path: str
    """Path al campo dentro de `AnswerKey.numeric`. Ej: `magnitude_pp`,
    `interpretation.bias_type`."""
    match: Literal["approx", "equals", "enum", "mentioned"]
    tolerance: float | None = None
    """Para `match='approx'`: tolerancia numérica de matcheo."""
    value: Any | None = None
    """Para `match='equals'` o `'enum'`: valor o lista de valores válidos."""

    @model_validator(mode="after")
    def _check_match_consistency(self) -> "AnswerKeyAnchor":
        if self.match == "approx":
            if self.tolerance is None:
                raise ValueError(
                    "AnswerKeyAnchor con match='approx' requiere `tolerance`"
                )
            if self.tolerance < 0:
                raise ValueError(
                    f"AnswerKeyAnchor.tolerance debe ser >= 0, "
                    f"no {self.tolerance}"
                )
            if self.value is not None:
                raise ValueError(
                    "AnswerKeyAnchor con match='approx' no usa `value`"
                )
        elif self.match in ("equals", "enum"):
            if self.value is None:
                raise ValueError(
                    f"AnswerKeyAnchor con match='{self.match}' requiere `value`"
                )
            if self.tolerance is not None:
                raise ValueError(
                    f"AnswerKeyAnchor con match='{self.match}' no usa `tolerance`"
                )
        elif self.match == "mentioned":
            if self.tolerance is not None or self.value is not None:
                raise ValueError(
                    "AnswerKeyAnchor con match='mentioned' no usa "
                    "`tolerance` ni `value`"
                )
        return self


class Criterion(BaseModel):
    """Un criterio de la `Rubric`.

    Pesos discretos (1, 2, 3) y `role` core/bonus. `core` aporta 70-85%
    del score de la GQ; `bonus` aporta 15-30% y NO compensa errores del
    core (ver `ARCHITECTURE.md` §6).
    """

    model_config = ConfigDict(extra="forbid")

    text: str
    """Qué se evalúa, en NL."""
    weight: int
    role: Literal["core", "bonus"]
    anchor: AnswerKeyAnchor
    scoring_hint: str
    """Guía al juez para calibrar el cumplimiento. 2-4 frases concretas."""
    requires_span: bool = True
    """Si True, el judge debe citar span textual del reporte."""

    @field_validator("weight")
    @classmethod
    def _check_weight(cls, v: int) -> int:
        if v not in ALLOWED_CRITERION_WEIGHTS:
            raise ValueError(
                f"Criterion.weight debe ser uno de {ALLOWED_CRITERION_WEIGHTS}, "
                f"no {v}"
            )
        return v


class Rubric(BaseModel):
    """Rubric asociada a una `GoldQuestion`. Lista de `Criterion`.

    Invariantes:
    - Una rubric vacía no puede evaluarse → `min_length=1`.
    - Debe tener al menos un `Criterion` con `role='core'`. El score se
      separa en core (70-85%) y bonus (15-30%); sin ningún core la rubric
      no puede acreditar ni siquiera la respuesta esperada base.
    - `bonus` es opcional: una rubric solo-core es válida.
    """

    model_config = ConfigDict(extra="forbid")

    criteria: list[Criterion] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_at_least_one_core(self) -> "Rubric":
        if not any(c.role == "core" for c in self.criteria):
            raise ValueError(
                "Rubric debe tener al menos un Criterion con role='core'. "
                "Una rubric solo-bonus no es evaluable."
            )
        return self


class GoldQuestion(BaseModel):
    """Pregunta canónica del caso, con `AnswerKey` pre-computado.

    `answer_key_provenance` es la lista de `EvidenceArtifact` (scripts
    ejecutables) que produjeron el `AnswerKey`. Plural porque una pregunta
    rica puede necesitar varios scripts (ej: ATE marginal + ATE estratificado
    + check de identifiability). Reproducible: cualquiera puede re-correr
    los scripts y verificar.

    El Evaluator usa `identification_hint` (paso 1, identificación binaria)
    y la `Rubric` (paso 2, completion graduada).
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    weight: float
    role: Literal["required", "support"]
    answer_key: AnswerKey
    answer_key_provenance: list[EvidenceArtifact] = Field(min_length=1)
    """Scripts ejecutables que respaldan el `AnswerKey`. Mínimo 1."""
    identification_hint: str
    """Guía al juez para decidir si el reporte aborda esta GQ. 2-4 frases
    concretas sobre qué buscar Y qué NO cuenta como identificación."""
    rubric: Rubric

    @field_validator("weight")
    @classmethod
    def _check_weight(cls, v: float) -> float:
        if v not in ALLOWED_GQ_WEIGHTS:
            raise ValueError(
                f"GoldQuestion.weight debe ser uno de {ALLOWED_GQ_WEIGHTS}, "
                f"no {v}"
            )
        return v


class QuestionsBundle(BaseModel):
    """Output final del Selector: catálogo de `GoldQuestion`s del caso.

    Un bundle vacío no es evaluable: `min_length=1`. La spec recomienda
    3-5 GoldQuestions por caso; esa restricción fuerte la chequea el
    `Validator` transversal, no este schema.
    """

    model_config = ConfigDict(extra="forbid")

    questions: list[GoldQuestion] = Field(min_length=1)


__all__ = [
    "ALLOWED_GQ_WEIGHTS",
    "ALLOWED_CRITERION_WEIGHTS",
    "AnswerKey",
    "AnswerKeyAnchor",
    "Criterion",
    "Rubric",
    "GoldQuestion",
    "QuestionsBundle",
]
