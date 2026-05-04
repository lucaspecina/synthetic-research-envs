"""Contrato del paquete que recibe el Investigator.

`ResearchCase` es **PÚBLICO** — lo ve el Investigator. NO incluye
`QuestionsBundle`, `Rubric`, `AnswerKey` ni `WorldSpec`. La frontera
público/oculto es invariante operativa (ver `ARCHITECTURE.md` §10).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class Dataset(BaseModel):
    """Un dataset visible para el Investigator."""

    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    columns: list[str]
    n_rows: int
    path: str
    """Path al archivo (típicamente CSV) accesible al runtime del Investigator."""


class ToolSpec(BaseModel):
    """Especificación de una herramienta disponible para el Investigator.

    Ej: `python_exec` para ejecutar análisis sobre los datasets.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    schema_: dict[str, Any]
    """JSON schema de los argumentos. (Nombre `schema_` con guión bajo
    para evitar colisión con `BaseModel.schema()`.)"""


class ResearchCase(BaseModel):
    """El paquete que recibe el Investigator.

    **PÚBLICO**: el Investigator ve todo lo que está acá adentro.

    **NO contiene**: `QuestionsBundle`, `GoldQuestion`, `Rubric`,
    `AnswerKey`, `WorldSpec`, `ValidationReport`. Si querés agregar uno
    de esos campos: PARÁ — eso filtra la respuesta. Esos artefactos
    viven aparte y no se exponen acá.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str
    brief: str
    context: str
    """Narrativa, background del dominio, supuestos, restricciones."""
    datasets: list[Dataset]
    tools: list[ToolSpec]


__all__ = ["Dataset", "ToolSpec", "ResearchCase"]
