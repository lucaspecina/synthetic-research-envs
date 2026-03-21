"""SCMSpec: declarative contract for specifying SCM worlds.

The LLM produces an SCMSpec via function calling. The SCMWorldGenTool
compiles it into an SCMWorld with safe equation evaluation.
"""

from __future__ import annotations

import keyword
from typing import Literal

import networkx as nx
from pydantic import BaseModel, Field, field_validator, model_validator

# Names reserved by the expression compiler (math functions + distributions)
_RESERVED_NAMES: frozenset[str] = frozenset(
    {
        "exp", "log", "log2", "log10", "sqrt", "sin", "cos", "tan",
        "abs", "min", "max", "pow", "ceil", "floor", "round",
        "normal", "uniform", "exponential", "lognormal", "beta", "gamma",
    }
)


class SCMVariableSpec(BaseModel):
    """Specification for a variable in the SCM."""

    name: str = Field(description="Variable name, e.g. 'temperature'")
    role: Literal["observable", "latent", "target"] = Field(
        default="observable",
        description=(
            "observable = agent can see, latent = hidden, target = what to predict"
        ),
    )
    unit: str = Field(default="", description="Physical unit, e.g. 'celsius', 'mg/kg'")
    range: tuple[float, float] | None = Field(
        default=None,
        description="Expected value range [min, max]. None = unbounded.",
    )
    description: str = Field(default="", description="Human-readable description")
    equation: str = Field(
        description=(
            "Structural equation as math expression, "
            "e.g. '0.5 * parent_a + normal(0, 2)'"
        ),
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.isidentifier():
            raise ValueError(
                f"Variable name '{v}' is not a valid Python identifier"
            )
        if keyword.iskeyword(v):
            raise ValueError(
                f"Variable name '{v}' is a Python keyword"
            )
        if v in _RESERVED_NAMES:
            raise ValueError(
                f"Variable name '{v}' conflicts with a built-in function "
                f"(reserved: {sorted(_RESERVED_NAMES)})"
            )
        return v


class SCMSpec(BaseModel):
    """Declarative specification for an SCM world.

    The LLM produces this via function calling. It describes the full
    causal structure: variables, edges, and equations as expression strings.
    The SCMWorldGenTool compiles it into a working SCMWorld.
    """

    variables: list[SCMVariableSpec] = Field(min_length=2)
    edges: list[tuple[str, str]] = Field(
        default_factory=list,
        description="Directed edges as (parent, child) pairs",
    )

    @model_validator(mode="after")
    def validate_no_duplicate_names(self) -> SCMSpec:
        names = [v.name for v in self.variables]
        dupes = [name for name in names if names.count(name) > 1]
        if dupes:
            raise ValueError(f"Duplicate variable names: {set(dupes)}")
        return self

    @model_validator(mode="after")
    def validate_edge_references(self) -> SCMSpec:
        names = {v.name for v in self.variables}
        for src, dst in self.edges:
            if src not in names:
                raise ValueError(f"Edge references unknown variable '{src}'")
            if dst not in names:
                raise ValueError(f"Edge references unknown variable '{dst}'")
        return self

    @model_validator(mode="after")
    def validate_is_dag(self) -> SCMSpec:
        if not self.edges:
            return self  # No edges = trivially acyclic (all roots)
        g = nx.DiGraph()
        g.add_nodes_from(v.name for v in self.variables)
        g.add_edges_from(self.edges)
        if not nx.is_directed_acyclic_graph(g):
            raise ValueError("Graph contains cycles")
        return self

    @model_validator(mode="after")
    def validate_has_target(self) -> SCMSpec:
        if not any(v.role == "target" for v in self.variables):
            raise ValueError("SCMSpec must have at least one target variable")
        return self

    @model_validator(mode="after")
    def validate_no_duplicate_edges(self) -> SCMSpec:
        seen: set[tuple[str, str]] = set()
        for edge in self.edges:
            t = tuple(edge)
            if t in seen:
                raise ValueError(f"Duplicate edge: {t}")
            seen.add(t)
        return self

    @model_validator(mode="after")
    def validate_has_observable(self) -> SCMSpec:
        if not any(v.role == "observable" for v in self.variables):
            raise ValueError("SCMSpec must have at least one observable variable")
        return self

    # --- Convenience ---

    def variable_names(self) -> list[str]:
        """All variable names in order."""
        return [v.name for v in self.variables]

    def get_variable(self, name: str) -> SCMVariableSpec:
        """Get variable spec by name."""
        for v in self.variables:
            if v.name == name:
                return v
        raise KeyError(f"Variable '{name}' not found")

    def parents_of(self, name: str) -> list[str]:
        """Get parent variable names for a given variable."""
        return [src for src, dst in self.edges if dst == name]


__all__ = ["SCMSpec", "SCMVariableSpec"]
