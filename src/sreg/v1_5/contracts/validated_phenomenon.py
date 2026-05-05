"""Contratos del flujo Architect ↔ Validators (post Ronda 13).

Cada `IntendedPhenomenon` declarado por el Architect es asignado a un
Validator que escribe scripts Python contra el `Environment` y emite un
`ValidatorVote`. Los `IntendedPhenomenon` cuyo voto es `passes` se
promueven a `ValidatedPhenomenon` (input principal del Question Designer).

Disciplina del flujo (ver `research/notes/multi_explorer_redesign.md` §3.1):

- Votos crudos inmutables: el Architect los lee, no los edita.
- Solo `vote='passes'` graduates a `ValidatedPhenomenon`. `weak_pass` NO
  promueve silenciosamente — fuerza al Architect a iterar.
- Cambios al `IntendedPhenomenon` entre iteraciones quedan versionados.

`ValidatorVote` tiene output enriquecido (margin / fragility /
delta_from_previous / diagnostics) para evitar hill-climbing ciego: el
Architect sabe no solo si pasó, sino qué tan sólido / frágil / cambiante
es el resultado iter-a-iter.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sreg.v1_5.contracts.phenomena import EvidenceArtifact


def _evidence_fingerprint(ev: EvidenceArtifact) -> tuple[str, str]:
    """Fingerprint de un `EvidenceArtifact` para anti-huérfanos.

    Compara `script + numerical_result` (lo que define la provenance real).
    Ignora `tag` y `notes` (metadata descriptiva). Esto detecta casos
    donde el Architect copia el script pero retoca números.
    """
    return (ev.script, json.dumps(ev.numerical_result, sort_keys=True, default=str))


class ValidatorVote(BaseModel):
    """Output crudo de un Validator sobre un `IntendedPhenomenon` específico.

    Inmutable: el Architect lo lee, no lo edita.

    `vote='passes'` graduates el fenómeno a `ValidatedPhenomenon`.
    `vote='weak_pass'` NO graduates — el Architect tiene que iterar.
    `vote='fails'` exige `failure_reason` con explicación concreta.
    """

    model_config = ConfigDict(extra="forbid")

    validator_id: str
    """Identificador del Validator. Ej: 'validator_run_2_collider'."""
    target_intended_id: str
    """`IntendedPhenomenon.id` que este Validator estaba verificando."""
    iteration: int = Field(ge=0)
    """Iteración del Architect que generó el WorldSpec evaluado (0-indexed)."""
    vote: Literal["passes", "weak_pass", "fails"]
    margin: float = Field(ge=0.0, le=1.0)
    """Claridad cuantitativa del resultado en [0, 1]. 1.0 = fenómeno
    cristalino; 0.0 = ruido. Ej: paradoja con `diff=-0.045 ± 0.01` → margin
    alto; `diff=-0.005 ± 0.01` → margin nulo."""
    fragility: float = Field(ge=0.0, le=1.0)
    """Sensibilidad a perturbaciones de coefs en [0, 1]. Alto fragility =
    el Architect tiene que reforzar antes de declararlo robusto."""
    delta_from_previous: dict[str, Any] | None = None
    """Cambios respecto a la iteración anterior. Debe ser None si
    `iteration=0` (no hay previa)."""
    evidence: list[EvidenceArtifact] = Field(min_length=1)
    """Scripts ejecutables que respaldan el voto (mínimo 1)."""
    failure_reason: str | None = None
    """Texto explicando por qué el voto no es `passes`. Obligatorio si
    `vote != 'passes'`."""
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    """Metadata libre: sample_size, ci, varianza muestral, scripts probados,
    etc. Telemetría no normativa para tuning futuro
    (`research/synthesis/world_design_techniques_survey.md` §4.5).

    Convención: **JSON-serializable** (claves str, valores tipos primitivos
    o estructuras anidadas de los mismos). El pipeline NO debe depender
    de claves específicas para lógica core — eso pertenece a campos
    tipados explícitos."""

    @model_validator(mode="after")
    def _check_consistency(self) -> "ValidatorVote":
        if self.vote != "passes" and self.failure_reason is None:
            raise ValueError(
                f"ValidatorVote con vote='{self.vote}' requiere "
                f"`failure_reason` explicando por qué."
            )
        if self.vote == "passes" and self.failure_reason is not None:
            raise ValueError(
                "ValidatorVote con vote='passes' NO debe tener "
                "`failure_reason` (eso es solo para weak_pass / fails)."
            )
        if self.iteration == 0 and self.delta_from_previous is not None:
            raise ValueError(
                "ValidatorVote con iteration=0 NO puede tener "
                "`delta_from_previous` (no hay iteración previa)."
            )
        return self


class ValidatedPhenomenon(BaseModel):
    """`IntendedPhenomenon` cuya materialización en el WorldSpec fue verificada.

    Construido cuando `validator_votes` tiene al menos un voto `passes` y
    NO tiene votos en estado distinto a `passes`. Apunta al
    `IntendedPhenomenon` original vía `source_intended_id` — son objetos
    distintos (intención del Architect vs. evidencia materializada).

    Input principal del Question Designer.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    source_intended_id: str
    """`IntendedPhenomenon.id` del original que generó este fenómeno validado."""
    kind: str
    description: str
    relevant_variables: list[str]
    validator_votes: list[ValidatorVote] = Field(min_length=1)
    """Votes que graduaron este fenómeno. Mínimo 1; todos deben tener
    `vote='passes'`."""
    margin: float = Field(ge=0.0, le=1.0)
    """Margin agregado conservador en [0, 1]. **Debe ser <= min(votes.margin)**:
    no infraestimar el fenómeno débil. El Architect no puede subir el
    margin "promediando" hacia arriba."""
    fragility: float = Field(ge=0.0, le=1.0)
    """Fragility agregada en [0, 1]. **Debe ser >= max(votes.fragility)**:
    no minimizar la fragilidad."""
    evidence: list[EvidenceArtifact] = Field(min_length=1)
    """Scripts re-ejecutables que respaldan el fenómeno. **Cada script
    debe haber estado en evidence de algún `validator_vote`**: no se
    permite evidencia "huérfana" inventada por el Architect."""

    @model_validator(mode="after")
    def _check_consistency(self) -> "ValidatedPhenomenon":
        # 1. Todos los votes deben ser `passes` y apuntar al mismo intended.
        for v in self.validator_votes:
            if v.vote != "passes":
                raise ValueError(
                    f"ValidatedPhenomenon solo se construye con votes "
                    f"`passes`. Voto de {v.validator_id} es '{v.vote}'."
                )
            if v.target_intended_id != self.source_intended_id:
                raise ValueError(
                    f"ValidatorVote.target_intended_id="
                    f"'{v.target_intended_id}' no coincide con "
                    f"ValidatedPhenomenon.source_intended_id="
                    f"'{self.source_intended_id}'."
                )

        # 2. Evidence: cada `(script, numerical_result)` debe estar en algún
        # vote. Anti-huérfanos. Compara fingerprint completo (no solo script)
        # para detectar Architect que copia código pero retoca números.
        vote_fingerprints = {
            _evidence_fingerprint(ev)
            for v in self.validator_votes
            for ev in v.evidence
        }
        own_fingerprints = {_evidence_fingerprint(ev) for ev in self.evidence}
        orphans = own_fingerprints - vote_fingerprints
        if orphans:
            raise ValueError(
                f"ValidatedPhenomenon.evidence contiene "
                f"{len(orphans)} EvidenceArtifact(s) cuyo (script + "
                f"numerical_result) NO aparece en ningún "
                f"validator_vote.evidence. Evidence huérfana no permitida."
            )

        # 3. Margin agregado: debe ser <= min de los votes (conservador).
        min_vote_margin = min(v.margin for v in self.validator_votes)
        if self.margin > min_vote_margin:
            raise ValueError(
                f"ValidatedPhenomenon.margin={self.margin:.4f} excede "
                f"el mínimo de validator_votes={min_vote_margin:.4f}. "
                f"La agregación de margin debe ser conservadora."
            )

        # 4. Fragility agregada: debe ser >= max de los votes (conservador).
        max_vote_fragility = max(v.fragility for v in self.validator_votes)
        if self.fragility < max_vote_fragility:
            raise ValueError(
                f"ValidatedPhenomenon.fragility={self.fragility:.4f} es "
                f"menor que el máximo de validator_votes="
                f"{max_vote_fragility:.4f}. La agregación de fragility "
                f"NO debe minimizar la fragilidad real."
            )
        return self


__all__ = ["ValidatorVote", "ValidatedPhenomenon"]
