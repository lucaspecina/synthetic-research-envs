"""Contrato del output de Paper Digestion (post Ronda 13).

`PaperInsights` extrae lo necesario para que el World Architect construya
un mundo inspirado en el paper. Además incluye una `narrative_capsule`
saneada (anti-leak) que se pasa al Question Designer y Case Writer SIN el
paper crudo — esto evita que las GoldQuestions hereden frases icónicas
del paper (ej. "the birth weight paradox") que el Investigator podría
memorizar (ver `research/notes/multi_explorer_redesign.md` §3.5).

Inspirar, no replicar (ver `PROJECT.md` invariante 5).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PaperNarrativeCapsule(BaseModel):
    """Cápsula narrativa saneada del paper (anti-leak).

    Contiene contexto necesario para redactar GoldQuestions / brief en
    un dominio realista (dominio, población, unidades, convenciones, estilo
    de pregunta natural) PERO **NO** frases icónicas, nombres canónicos del
    paper, ni conclusiones / interpretaciones del autor.

    Pasada al Question Designer y al Case Writer; el paper crudo NO llega
    a esas etapas.
    """

    model_config = ConfigDict(extra="forbid")

    domain: str
    """Dominio (ej. 'epidemiología perinatal')."""
    population: str
    """Quién/qué es la población observada (ej. 'cohorte de ~1500
    nacimientos')."""
    units: dict[str, str] = Field(default_factory=dict)
    """Unidades por variable (ej. `{'birth_weight': 'gramos'}`)."""
    measurement_conventions: list[str] = Field(default_factory=list)
    """Convenciones de medición del dominio (ej. 'LBW threshold 2500g')."""
    natural_question_style: list[str] = Field(default_factory=list)
    """Estilo de pregunta natural en el dominio. SIN nombres del paper.
    Ej: 'estimaciones de efecto causal con CI', 'análisis estratificados'."""
    forbidden_phrases: list[str] = Field(default_factory=list)
    """Frases del paper original que el Question Designer NO debe usar
    (anti-leak léxico). Ej: 'paradoja del peso al nacer', 'collider'."""


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
    """Cómo se relacionan, alto nivel. NO ecuaciones. Input al World Architect."""
    phenomena: list[str]
    """Fenómenos observados (paradojas, no-linealidades, identifiability gaps)."""
    complications: list[str]
    """Confounders, missing data, sesgos típicos del dominio."""
    counterintuitive_priors: list[str]
    """Priors equivocados que un agente podría tener — el caso debería
    forzar a verificar contra los datos en lugar de adivinar por prior."""
    realism_bounds: list[str]
    """Qué hace al caso realista: rangos de variables, escalas, plausibilidad."""
    narrative_capsule: PaperNarrativeCapsule
    """Cápsula saneada que el Question Designer y el Case Writer reciben
    en lugar del paper crudo (anti-leak). Obligatoria — el flujo
    post-Ronda 13 prohíbe exponer el paper crudo aguas abajo de Paper
    Digestion."""


__all__ = ["PaperInsights", "PaperNarrativeCapsule"]
