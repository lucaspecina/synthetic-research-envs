"""Tests para los lints deterministas sobre WorldSpec.

Cada lint cierra un hueco encontrado en pilots reales (Architect 2026-05-06):
- repeated stochastic in branch (smoking_birthweight bug)
- methodology in intended_phenomena (confounding_by_indication bug)
"""

from __future__ import annotations

import pytest

from sreg.v1_5.contracts.world import (
    IntendedPhenomenon,
    VariableSpec,
    WorldMetadata,
    WorldSpec,
)
from sreg.v1_5.world.world_lints import (
    lint_intended_phenomena_no_methodology,
    lint_no_repeated_stochastic_in_branch,
)


def _make_world(
    *,
    variables: list[VariableSpec],
    edges: list[tuple[str, str]] | None = None,
    intended_phenomena: list[IntendedPhenomenon] | None = None,
) -> WorldSpec:
    return WorldSpec(
        formalism="scm",
        variables=variables,
        edges=edges or [],
        metadata=WorldMetadata(domain="generic"),
        intended_phenomena=intended_phenomena or [],
    )


# ---------------------------------------------------------------------------
# lint_no_repeated_stochastic_in_branch
# ---------------------------------------------------------------------------


def test_stochastic_lint_passes_single_call_per_branch() -> None:
    """1 distro fuera del ternario y 1 distro dentro: OK."""
    w = _make_world(
        variables=[
            VariableSpec(name="A", equation="normal(0, 1)"),
            VariableSpec(
                name="B",
                kind="binary",
                equation="1 if normal(0, 1) > 0 else 0",
            ),
        ],
        edges=[],
    )
    # No raise.
    lint_no_repeated_stochastic_in_branch(w)


def test_stochastic_lint_rejects_repeated_normal_in_ternary() -> None:
    """Caso real (smoking_birthweight): normal(0, 0.8) en branches distintos."""
    eq = (
        "0 if (-0.6 + normal(0, 0.8)) < -0.5 "
        "else (1 if (-0.6 + normal(0, 0.8)) < 0.5 else 2)"
    )
    w = _make_world(
        variables=[
            VariableSpec(name="A", equation="normal(0, 1)"),
            VariableSpec(name="B", kind="categorical", equation=eq),
        ],
        edges=[],
    )
    with pytest.raises(ValueError, match="ternario con"):
        lint_no_repeated_stochastic_in_branch(w)


def test_stochastic_lint_rejects_two_different_distros_in_ternary() -> None:
    """Más estricto: distros distintas dentro del mismo ternario también."""
    eq = "1 if uniform(0, 1) > 0.5 else normal(0, 1)"
    w = _make_world(
        variables=[
            VariableSpec(name="A", equation="normal(0, 1)"),
            VariableSpec(name="B", equation=eq),
        ],
        edges=[],
    )
    with pytest.raises(ValueError, match="estoc"):
        lint_no_repeated_stochastic_in_branch(w)


def test_stochastic_lint_allows_helpers_in_ternary() -> None:
    """sigmoid, I, math: deterministas, OK múltiples veces."""
    eq = "I(sigmoid(A) > 0.5) + I(sigmoid(A) < 0.2)"
    w = _make_world(
        variables=[
            VariableSpec(name="A", equation="normal(0, 1)"),
            VariableSpec(name="B", equation=eq),
        ],
        edges=[("A", "B")],
    )
    # No raise.
    lint_no_repeated_stochastic_in_branch(w)


def test_stochastic_lint_ignores_invalid_syntax() -> None:
    """Sintaxis inválida la reporta ExpressionCompiler, no este lint."""
    # Construimos saltando el validator de sintaxis (model_construct).
    var = VariableSpec.model_construct(
        name="A",
        kind="continuous",
        is_observable=True,
        equation="this is not python(",
    )
    w = WorldSpec.model_construct(
        formalism="scm",
        variables=[var, VariableSpec(name="B", equation="normal(0, 1)")],
        edges=[],
        metadata=WorldMetadata(domain="generic"),
        intended_phenomena=[],
        parameters={},
    )
    # No raise por syntax — pasa silencioso, otro layer lo atrapa.
    lint_no_repeated_stochastic_in_branch(w)


# ---------------------------------------------------------------------------
# lint_intended_phenomena_no_methodology
# ---------------------------------------------------------------------------


def _vars_minimal() -> list[VariableSpec]:
    return [
        VariableSpec(name="A", equation="normal(0, 1)"),
        VariableSpec(name="B", equation="A + normal(0, 0.1)"),
    ]


def _edges_minimal() -> list[tuple[str, str]]:
    return [("A", "B")]


def test_methodology_lint_passes_clean_description() -> None:
    """Descripción puramente del mundo: OK."""
    w = _make_world(
        variables=_vars_minimal(),
        edges=_edges_minimal(),
        intended_phenomena=[
            IntendedPhenomenon(
                id="ip1",
                kind="confounding",
                description="A is a common cause of B and C in this system.",
                relevant_variables=["A", "B"],
            ),
        ],
    )
    lint_intended_phenomena_no_methodology(w)


@pytest.mark.parametrize(
    "bad_desc",
    [
        "After adjusting for severity, the effect inverts.",
        "Once we account for the confounder, the bias goes away.",
        "Conditioning on M induces association between X and Y.",
        "After adjustment, treatment effect is positive.",
        "Hospital type is a backdoor path.",
        "The minimum adjustment set blocks the spurious path.",
        "Adjusting for X recovers the causal effect.",
        "Controlling for severity removes the confounding.",
    ],
)
def test_methodology_lint_rejects_methodological_phrases(bad_desc: str) -> None:
    """Frases típicas de consejo analítico → fail."""
    w = _make_world(
        variables=_vars_minimal(),
        edges=_edges_minimal(),
        intended_phenomena=[
            IntendedPhenomenon(
                id="ip1",
                kind="confounding",
                description=bad_desc,
                relevant_variables=["A"],
            ),
        ],
    )
    with pytest.raises(ValueError, match="methodol"):
        lint_intended_phenomena_no_methodology(w)


def test_methodology_lint_rejects_real_world_case_from_pilot() -> None:
    """Reproducción del bug real de confounding_by_indication 2026-05-06."""
    w = _make_world(
        variables=_vars_minimal(),
        edges=_edges_minimal(),
        intended_phenomena=[
            IntendedPhenomenon(
                id="treatment_predictor_not_confounder",
                kind="non_identifiability",
                description=(
                    "Hospital type does not directly affect outcome once "
                    "patient case mix is accounted for; conditioning on it "
                    "would not change the estimate."
                ),
                relevant_variables=["hospital_type"],
            ),
        ],
    )
    with pytest.raises(ValueError):
        lint_intended_phenomena_no_methodology(w)
