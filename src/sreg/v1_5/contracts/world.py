"""Contratos del WorldModel (matemática subyacente del caso).

`WorldSpec` discrimina por `formalism`: `scm` (causal estático) u `ode`
(dinámica determinista, con observation noise opcional). SDE intrínseco
se difiere a v1.6 (ver `ARCHITECTURE.md` §9, §11).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VariableSpec(BaseModel):
    """Una variable del WorldModel."""

    model_config = ConfigDict(extra="forbid")

    name: str
    kind: Literal["continuous", "binary", "categorical", "count"] = "continuous"
    description: str | None = None
    is_observable: bool = True
    """Si False, la variable es latente (ej. confounder no observado).
    El Investigator NO la ve en los datasets."""


class RelationshipSpec(BaseModel):
    """Una relación estructural entre variables."""

    model_config = ConfigDict(extra="forbid")

    parent: str
    child: str
    expression: str
    """Expresión simbólica de la relación. Ej: `0.5 * smoking + N(0, 1)`
    para SCM, o `dy/dt = -k * y + u(t)` para ODE."""
    description: str | None = None


class WorldMetadata(BaseModel):
    """Metadata del mundo: dominio, paper que inspira, notas."""

    model_config = ConfigDict(extra="forbid")

    domain: str
    """Ej: 'epidemiology', 'pharmacokinetics', 'ecology'."""
    seed_paper_id: str | None = None
    notes: str | None = None


class WorldSpec(BaseModel):
    """Especificación matemática del mundo.

    El formalismo (`scm` / `ode`) determina cómo se compila el Environment
    y qué `query_kinds` aplican (ver `ARCHITECTURE.md` §9).
    """

    model_config = ConfigDict(extra="forbid")

    formalism: Literal["scm", "ode"]
    variables: list[VariableSpec]
    relationships: list[RelationshipSpec]
    parameters: dict[str, float] = Field(default_factory=dict)
    metadata: WorldMetadata
    observation_noise: float | None = None
    """Desvío estándar gaussiano opcional sobre las trayectorias observadas
    (solo aplica a `formalism='ode'`). Modela ruido de medición sin
    requerir SDE intrínseco."""

    @model_validator(mode="after")
    def _check_observation_noise(self) -> "WorldSpec":
        if self.observation_noise is None:
            return self
        if self.formalism != "ode":
            raise ValueError(
                f"observation_noise solo aplica a formalism='ode' "
                f"(no a '{self.formalism}'). Setear observation_noise=None "
                f"o cambiar formalism a 'ode'."
            )
        if self.observation_noise < 0:
            raise ValueError(
                f"observation_noise debe ser >= 0 (es desvío estándar gaussiano), "
                f"no {self.observation_noise}"
            )
        return self


__all__ = ["VariableSpec", "RelationshipSpec", "WorldMetadata", "WorldSpec"]
