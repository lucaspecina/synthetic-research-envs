"""Contratos del output del Explorer.

El Explorer encuentra fenómenos interesantes en el mundo y adjunta
**evidencia ejecutable** (`EvidenceArtifact`: script + resultado numérico)
para evitar error laundering — sin script ejecutable, cualquier alucinación
del Explorer contamina upstream.

`Phenomenon.kind` es **string libre con tags opcionales**, NO un enum
cerrado. Cualquier descripción tipo "collider", "bifurcation_proximity",
"oscillation_sensitivity" o algo nuevo emergente es válido. La taxonomía
es descriptiva, no normativa (ver `multi_explorer_redesign.md`).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceArtifact(BaseModel):
    """Evidencia ejecutable que respalda un fenómeno o un AnswerKey.

    Patrón: el agente (Explorer / Question Designer) escribe un script
    Python que recibe el `Environment`, lo ejecuta, y captura el
    resultado numérico. NO se entrega prosa descriptiva como evidencia.

    `tag` es opcional y descriptivo (ej. "ate_computation", "collider_check");
    permite analytics agregados pero NO restringe qué scripts son válidos.
    """

    model_config = ConfigDict(extra="forbid")

    script: str
    numerical_result: dict[str, Any]
    notes: str | None = None
    tag: str | None = None


class Phenomenon(BaseModel):
    """Un fenómeno del WorldModel detectado por el Explorer.

    `kind` es string libre. Ejemplos comunes (NO obligatorios):
    `counterintuitive`, `collider`, `mediation`, `identifiability_gap`,
    `bifurcation_proximity`, `spurious_correlation`, `heterogeneity`,
    `non_linearity`, `regime_switch`, etc. El Explorer puede inventar
    nombres nuevos para fenómenos emergentes.
    """

    model_config = ConfigDict(extra="forbid")

    kind: str
    description: str
    evidence: EvidenceArtifact
    tags: list[str] = Field(default_factory=list)
    """Tags opcionales para análisis agregado. NO normativos."""


class PhenomenaManifest(BaseModel):
    """Output del Explorer: catálogo de fenómenos con evidencia ejecutable."""

    model_config = ConfigDict(extra="forbid")

    world_id: str
    phenomena: list[Phenomenon]
    interesting_score: float
    """Agregado: qué tan interesante es el mundo según los fenómenos
    encontrados. Evita gastar al Designer en mundos triviales."""


__all__ = ["EvidenceArtifact", "Phenomenon", "PhenomenaManifest"]
