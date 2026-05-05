"""Contratos del WorldModel (matemática subyacente del caso).

Diseño alineado con `src/sreg/models/scm_spec.py` v1 — patrón probado:

- **Una `equation` por variable** (NO por arista). Multi-parent natural.
- **`edges` como `list[tuple[str, str]]`** (parent, child). Topología del DAG.
- Cada `VariableSpec.equation` es expresión de math/funciones soportadas
  por `ExpressionCompiler` (`src/sreg/world/expression_compiler.py`).

`WorldSpec` discrimina por `formalism`:
- `scm` (causal estático): `equation` evalúa la variable dado parents.
- `ode` (dinámica determinista): `equation` representa `dy/dt = f(...)`.
  Soporta `observation_noise` opcional.

SDE intrínseco se difiere a v1.6 (ver `ARCHITECTURE.md` §9, §11).
"""

from __future__ import annotations

import keyword
from typing import Literal

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Funciones reservadas por `ExpressionCompiler` (no pueden ser nombres de variable).
_RESERVED_NAMES: frozenset[str] = frozenset(
    {
        # math
        "exp", "log", "log2", "log10", "sqrt", "sin", "cos", "tan",
        "abs", "min", "max", "pow", "ceil", "floor", "round",
        # distributions
        "normal", "uniform", "exponential", "lognormal", "beta", "gamma",
        "bernoulli",
        # helpers
        "sigmoid", "I",
    }
)


class VariableSpec(BaseModel):
    """Una variable del WorldModel.

    Para SCM, `equation` es obligatoria y describe cómo se computa la
    variable desde sus padres + ruido (ej. `'2.0 * smoking + normal(0, 0.5)'`).

    Para ODE, `equation` representa la dinámica `dy/dt = f(...)` (ej.
    `'-k * y + u'`). Validado por `WorldSpec` post hoc.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    kind: Literal["continuous", "binary", "categorical", "count"] = "continuous"
    description: str | None = None
    is_observable: bool = True
    """Si False, la variable es latente (ej. confounder no observado).
    El Investigator NO la ve en los datasets."""
    equation: str | None = None
    """Expresión simbólica que computa la variable. Obligatoria para SCM
    (validador a nivel `WorldSpec`); opcional para roots sin ruido. En
    ODE representa `dy/dt = ...`. Sintaxis soportada: ver
    `src/sreg/world/expression_compiler.py`."""

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not v.isidentifier():
            raise ValueError(
                f"VariableSpec.name='{v}' no es identificador Python válido."
            )
        if keyword.iskeyword(v):
            raise ValueError(
                f"VariableSpec.name='{v}' es keyword reservado de Python."
            )
        if v in _RESERVED_NAMES:
            raise ValueError(
                f"VariableSpec.name='{v}' colisiona con función reservada "
                f"del ExpressionCompiler ({sorted(_RESERVED_NAMES)})."
            )
        return v


class WorldMetadata(BaseModel):
    """Metadata del mundo: dominio, paper que inspira, notas."""

    model_config = ConfigDict(extra="forbid")

    domain: str
    """Ej: 'epidemiology', 'pharmacokinetics', 'ecology'."""
    seed_paper_id: str | None = None
    notes: str | None = None


class IntendedPhenomenon(BaseModel):
    """Lo que el `World Architect` quiso poner intencionalmente en el `WorldSpec`.

    Es la guía de "qué fenómenos esperar" para los Validators.
    Vive en nivel **mecanismo / fenómeno**, NO en nivel pregunta concreta
    (esa decisión la toma el Question Designer).

    Ejemplos válidos:
    - `kind="collider"`, `description="LBW collider entre smoking y hidden_u"`
    - `kind="mediation"`, `description="smoking afecta mortality vía birth_weight"`
    - `kind="bifurcation"`, `description="bifurcación de Hopf cerca de R0=1.0"`
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    """String libre. Tags comunes: collider, mediation, confounding, bifurcation,
    non_linearity, heterogeneity, etc."""
    description: str
    relevant_variables: list[str]


Edge = tuple[str, str]
"""Arista del DAG: `(parent, child)`."""


class WorldSpec(BaseModel):
    """Especificación matemática del mundo.

    Patrón (alineado con `SCMSpec` v1):
    - `variables`: lista de `VariableSpec`. Cada una con su `equation` propia.
    - `edges`: lista de `(parent, child)` describiendo el DAG.
    - `parameters`: hiperparámetros nombrados (no son variables del modelo).

    El `formalism` (`scm` / `ode`) determina cómo se compila el Environment.
    `intended_phenomena` declara qué fenómenos el Architect quiso poner;
    los Validators los usan como guía para verificar
    (ver `multi_explorer_redesign.md`).
    """

    model_config = ConfigDict(extra="forbid")

    formalism: Literal["scm", "ode"]
    variables: list[VariableSpec] = Field(min_length=1)
    edges: list[Edge] = Field(default_factory=list)
    """Topología del DAG: pares `(parent, child)`. Para SCM define padres
    de cada variable. Para ODE puede declarar qué variable acopla con qué
    en `dy/dt`."""
    parameters: dict[str, float] = Field(default_factory=dict)
    metadata: WorldMetadata
    observation_noise: float | None = None
    """Desvío estándar gaussiano opcional sobre las trayectorias observadas
    (solo aplica a `formalism='ode'`). Modela ruido de medición sin
    requerir SDE intrínseco."""
    intended_phenomena: list[IntendedPhenomenon] = Field(default_factory=list)
    """Lista corta (típicamente 2-5) de fenómenos que el Architect declaró
    haber puesto. Sirve como guía de focos para los Validators."""

    @model_validator(mode="after")
    def _check_variable_names_unique(self) -> "WorldSpec":
        names = [v.name for v in self.variables]
        dupes = [n for n in set(names) if names.count(n) > 1]
        if dupes:
            raise ValueError(
                f"WorldSpec tiene VariableSpec con nombres duplicados: "
                f"{sorted(dupes)}."
            )
        return self

    @model_validator(mode="after")
    def _check_edges_reference_known_variables(self) -> "WorldSpec":
        names = {v.name for v in self.variables}
        for parent, child in self.edges:
            if parent not in names:
                raise ValueError(
                    f"Edge ({parent!r}, {child!r}): parent no es una "
                    f"variable de WorldSpec."
                )
            if child not in names:
                raise ValueError(
                    f"Edge ({parent!r}, {child!r}): child no es una "
                    f"variable de WorldSpec."
                )
        return self

    @model_validator(mode="after")
    def _check_no_duplicate_edges(self) -> "WorldSpec":
        seen: set[tuple[str, str]] = set()
        for edge in self.edges:
            if edge in seen:
                raise ValueError(f"WorldSpec tiene edge duplicado: {edge!r}.")
            seen.add(edge)
        return self

    @model_validator(mode="after")
    def _check_dag(self) -> "WorldSpec":
        if not self.edges:
            return self
        g = nx.DiGraph()
        g.add_nodes_from(v.name for v in self.variables)
        g.add_edges_from(self.edges)
        if not nx.is_directed_acyclic_graph(g):
            raise ValueError("WorldSpec.edges contiene ciclos. Debe ser DAG.")
        return self

    @model_validator(mode="after")
    def _check_scm_has_equations(self) -> "WorldSpec":
        """Para SCM, todas las variables deben tener `equation`."""
        if self.formalism != "scm":
            return self
        missing = [v.name for v in self.variables if v.equation is None]
        if missing:
            raise ValueError(
                f"WorldSpec(formalism='scm') exige `equation` en cada "
                f"variable. Faltan en: {missing}."
            )
        return self

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
                f"observation_noise debe ser >= 0 (es desvío estándar "
                f"gaussiano), no {self.observation_noise}."
            )
        return self

    # --- Conveniencia ---

    def parents_of(self, variable_name: str) -> list[str]:
        """Devuelve los nombres de los padres de `variable_name` según `edges`."""
        return [parent for parent, child in self.edges if child == variable_name]

    def variable_names(self) -> list[str]:
        return [v.name for v in self.variables]


__all__ = [
    "VariableSpec",
    "WorldMetadata",
    "IntendedPhenomenon",
    "Edge",
    "WorldSpec",
]
