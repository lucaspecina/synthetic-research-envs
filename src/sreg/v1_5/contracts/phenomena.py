"""Contratos del output del Explorer.

El Explorer encuentra fenómenos interesantes en el mundo y adjunta
**evidencia ejecutable** (script + resultado numérico) para evitar error
laundering — sin script ejecutable, cualquier alucinación del Explorer
contamina upstream.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ExecutableEvidence(BaseModel):
    """Evidencia ejecutable adjunta a un fenómeno.

    El Explorer corre el `script` contra el Environment y guarda el
    `numerical_result`. NO entrega prosa descriptiva.
    """

    model_config = ConfigDict(extra="forbid")

    script: str
    numerical_result: dict[str, Any]
    notes: str | None = None


class Phenomenon(BaseModel):
    """Un fenómeno del WorldModel detectado por el Explorer."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "counterintuitive",
        "identifiability_gap",
        "bifurcation_proximity",
        "spurious_correlation",
        "heterogeneity",
        "non_linearity",
    ]
    description: str
    evidence: ExecutableEvidence


class PhenomenaManifest(BaseModel):
    """Output del Explorer: catálogo de fenómenos con evidencia ejecutable."""

    model_config = ConfigDict(extra="forbid")

    world_id: str
    phenomena: list[Phenomenon]
    interesting_score: float
    """Agregado: qué tan interesante es el mundo según los fenómenos
    encontrados. Evita gastar al Designer en mundos triviales."""


__all__ = ["ExecutableEvidence", "Phenomenon", "PhenomenaManifest"]
