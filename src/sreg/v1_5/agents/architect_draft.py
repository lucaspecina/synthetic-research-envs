"""Schema simplificado para function calling del Architect.

`WorldSpec` v1.5 usa `edges: list[tuple[str, str]]` y otros shapes que
generan JSON schemas con `prefixItems` que los LLMs manejan mal. Este
módulo expone un `ArchitectWorldDraft` con representaciones más
LLM-friendly (edges como objetos `{parent, child}`) y un conversor
determinista a `WorldSpec` real.

**Mantiene LIMPIO el contrato runtime**: `WorldSpec` sigue siendo la
fuente de verdad downstream. `ArchitectWorldDraft` solo existe en la
frontera con el LLM.

Detectado por Codex (2026-05-05): "para `PaperInsights` funcionó usar
`model_json_schema()` directo; para `WorldSpec` ya estás en terreno
más frágil."
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from sreg.v1_5.contracts.world import (
    IntendedPhenomenon,
    VariableSpec,
    WorldMetadata,
    WorldSpec,
)


class VariableDraft(BaseModel):
    """Variable del WorldSpec, en formato LLM-friendly."""

    model_config = ConfigDict(extra="forbid")

    name: str
    kind: Literal["continuous", "binary", "categorical", "count"] = "continuous"
    description: str = ""
    is_observable: bool = True
    equation: str
    """Expresión simbólica obligatoria. Para roots sin parents puede ser
    una distribución pura (ej. ``"normal(0, 1)"``); para nodos
    deterministas, una expresión determinista (ej. ``"I(X < 2500)"``)."""
    plausible_min: float | None = None
    """Cota inferior plausible declarada por el Architect (opcional). Usada
    en el lint de soporte post-sampling: si >1% del sample cae fuera de
    `[plausible_min, plausible_max]`, se rechaza el WorldSpec.

    Recomendado para variables continuas (ej. age en humanos: 0-100). Para
    binary/categorical/count puede dejarse None — el rango está
    determinado por el kind."""
    plausible_max: float | None = None
    """Cota superior plausible. Ver `plausible_min`."""


class EdgeDraft(BaseModel):
    """Arista del DAG en formato objeto (no tuple)."""

    model_config = ConfigDict(extra="forbid")

    parent: str
    child: str


class IntendedPhenomenonDraft(BaseModel):
    """Fenómeno declarado por el Architect, formato LLM-friendly."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    """Tag — preferentemente uno del vocabulario canónico (ver prompt
    del Architect): confounding, selection_bias, collider, mediation,
    effect_heterogeneity, measurement_error, proxy_bias,
    non_identifiability, threshold_effect, non_linearity. Inventar
    uno nuevo solo si ninguno de estos encaja."""
    description: str
    relevant_variables: list[str]


class ArchitectWorldDraft(BaseModel):
    """Output del Architect: WorldSpec en formato LLM-friendly.

    El conversor `to_world_spec(draft)` lo lleva a `WorldSpec` real.
    """

    model_config = ConfigDict(extra="forbid")

    domain: str
    """Dominio del mundo (ej. ``"epidemiología perinatal"``). Mapea a
    ``WorldSpec.metadata.domain``."""
    seed_paper_id: str | None = None
    """Identificador del paper que inspiró este mundo (puede ser None)."""
    notes: str | None = None
    """Notas del Architect: decisiones de diseño, simplificaciones, etc."""
    variables: list[VariableDraft] = Field(min_length=2)
    """Variables del mundo (mínimo 2 — heritage constraint de SCMSpec v1)."""
    edges: list[EdgeDraft] = Field(default_factory=list)
    """Aristas del DAG. Coherencia edges↔equations es validada en
    `compile_scm`: todo edge declarado debe usarse en la equation
    correspondiente, y toda variable usada en una equation debe tener
    edge entrante."""
    intended_phenomena: list[IntendedPhenomenonDraft] = Field(default_factory=list)
    """Fenómenos que el Architect afirma haber materializado en el mundo.
    2-5 entries. Los Validators downstream verifican (no validamos acá)."""


def to_world_spec(draft: ArchitectWorldDraft) -> WorldSpec:
    """Convierte un `ArchitectWorldDraft` a `WorldSpec` v1.5 real.

    El conversor es determinista y NO inyecta valores nuevos: solo
    re-mapea shapes (`EdgeDraft` → tuple, `VariableDraft` →
    `VariableSpec`, etc.).

    Raises:
        pydantic.ValidationError: si el draft no satisface los
            validators de `WorldSpec` (DAG, equation obligatoria en
            SCM, etc.). El caller (Architect agent) debe interpretar
            esos errores y, si corresponde, reintentar.
    """
    return WorldSpec(
        formalism="scm",  # Fijo en v1.5 — ODE viene después.
        variables=[
            VariableSpec(
                name=v.name,
                kind=v.kind,
                description=v.description or None,
                is_observable=v.is_observable,
                equation=v.equation,
            )
            for v in draft.variables
        ],
        edges=[(e.parent, e.child) for e in draft.edges],
        metadata=WorldMetadata(
            domain=draft.domain,
            seed_paper_id=draft.seed_paper_id,
            notes=draft.notes,
        ),
        intended_phenomena=[
            IntendedPhenomenon(
                id=ip.id,
                kind=ip.kind,
                description=ip.description,
                relevant_variables=ip.relevant_variables,
            )
            for ip in draft.intended_phenomena
        ],
    )


__all__ = [
    "VariableDraft",
    "EdgeDraft",
    "IntendedPhenomenonDraft",
    "ArchitectWorldDraft",
    "to_world_spec",
]
