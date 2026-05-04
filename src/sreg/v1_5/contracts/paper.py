"""Contrato del output de Paper Digestion.

`PaperInsights` extrae lo necesario para que el World Architect pueda
construir un mundo nuevo inspirado en el paper. Inspirar, no replicar
(ver `PROJECT.md` invariante 5).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PaperInsights(BaseModel):
    """Output del agente Paper Digestion.

    Captura mecanismos, fenómenos y trampas del paper sin filtrar la
    respuesta — el solver no debe poder responder por memoria del paper.
    """

    model_config = ConfigDict(extra="forbid")

    paper_id: str
    objective: str
    """Qué investiga el paper, en una oración."""
    entities: list[str]
    """Actores principales (variables, sistemas, agentes)."""
    mechanisms: list[str]
    """Cómo se relacionan, alto nivel. NO ecuaciones."""
    phenomena: list[str]
    """Fenómenos observados (paradojas, no-linealidades, identifiability gaps)."""
    complications: list[str]
    """Confounders, missing data, sesgos típicos del dominio."""
    counterintuitive_priors: list[str]
    """Priors equivocados que un agente podría tener — el caso debería
    forzar a verificar contra los datos en lugar de adivinar por prior."""
    realism_bounds: list[str]
    """Qué hace al caso realista: rangos de variables, escalas, plausibilidad."""


__all__ = ["PaperInsights"]
