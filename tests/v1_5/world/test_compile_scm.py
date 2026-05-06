"""Tests unitarios del compiler `compile_scm`.

Foco: la mecánica del compiler en aislamiento. Para validar la pipeline
completa con un caso real (Birth Weight Paradox), ver
`tests/v1_5/integration/test_birth_weight_paradox.py`.
"""

from __future__ import annotations

import pytest

from sreg.v1_5.contracts.world import (
    IntendedPhenomenon,
    VariableSpec,
    WorldMetadata,
    WorldSpec,
)
from sreg.v1_5.world import compile_scm
from sreg.world.expression_compiler import ExpressionError
from sreg.world.scm import SCMWorld


def _world(
    *,
    formalism: str = "scm",
    variables: list[VariableSpec] | None = None,
    edges: list[tuple[str, str]] | None = None,
    parameters: dict[str, float] | None = None,
) -> WorldSpec:
    if variables is None:
        # Default: 2 variables (constraint heritage de SCMSpec v1).
        variables = [
            VariableSpec(name="X", kind="continuous", equation="normal(0, 1)"),
            VariableSpec(name="Y", kind="continuous", equation="2*X + normal(0, 0.1)"),
        ]
    if edges is None:
        edges = [("X", "Y")] if len(variables) == 2 and variables[0].name == "X" else []
    return WorldSpec(
        formalism=formalism,  # type: ignore[arg-type]
        variables=variables,
        edges=edges,
        parameters=parameters or {},
        metadata=WorldMetadata(domain="generic"),
    )


# ---------------------------------------------------------------------------
# Casos básicos
# ---------------------------------------------------------------------------


def test_compile_minimal_two_variables() -> None:
    """Mínimo soportado: 2 variables (constraint heritage de SCMSpec v1)."""
    world = _world(
        variables=[
            VariableSpec(name="X", equation="normal(0, 1)"),
            VariableSpec(name="Y", equation="X + normal(0, 0.1)"),
        ],
        edges=[("X", "Y")],
    )
    scm = compile_scm(world)
    assert isinstance(scm, SCMWorld)
    assert set(scm.variables) == {"X", "Y"}


def test_compile_rejects_single_variable_explicit_message() -> None:
    """1 variable rebota con mensaje útil (no `ValidationError` críptico)."""
    world = _world(
        variables=[VariableSpec(name="X", equation="normal(0, 1)")],
        edges=[],
    )
    with pytest.raises(ValueError, match=">= 2 variables"):
        compile_scm(world)


def test_compile_multi_parent() -> None:
    """Y depende de A y B (multi-parent). Debe compilar y samplear."""
    world = _world(
        variables=[
            VariableSpec(name="A", equation="normal(0, 1)"),
            VariableSpec(name="B", equation="normal(0, 1)"),
            VariableSpec(name="Y", equation="A + 2*B + normal(0, 0.1)"),
        ],
        edges=[("A", "Y"), ("B", "Y")],
    )
    scm = compile_scm(world)
    df = scm.sample(n=500, seed=42)
    assert set(df.columns) == {"A", "B", "Y"}
    assert df.shape == (500, 3)


def test_compile_chain() -> None:
    """A → B → C cadena causal."""
    world = _world(
        variables=[
            VariableSpec(name="A", equation="normal(0, 1)"),
            VariableSpec(name="B", equation="2*A + normal(0, 0.1)"),
            VariableSpec(name="C", equation="3*B + normal(0, 0.1)"),
        ],
        edges=[("A", "B"), ("B", "C")],
    )
    scm = compile_scm(world)
    df = scm.sample(n=1000, seed=42)
    # C depende de B depende de A: corr(A, C) > 0.9
    assert df[["A", "C"]].corr().iloc[0, 1] > 0.9


# ---------------------------------------------------------------------------
# Latentes
# ---------------------------------------------------------------------------


def test_latent_variable_marked_in_scm() -> None:
    """`is_observable=False` debe llegar a `SCMWorld.latent_variables`."""
    world = _world(
        variables=[
            VariableSpec(name="U", equation="normal(0, 1)", is_observable=False),
            VariableSpec(name="X", equation="U + normal(0, 0.1)"),
        ],
        edges=[("U", "X")],
    )
    scm = compile_scm(world)
    assert scm.latent_variables == {"U"}
    assert "X" not in scm.latent_variables


def test_observable_variable_not_in_latent() -> None:
    world = _world(
        variables=[
            VariableSpec(name="X", equation="normal(0, 1)"),
            VariableSpec(name="Y", equation="X + normal(0, 0.1)"),
        ],
        edges=[("X", "Y")],
    )
    scm = compile_scm(world)
    assert scm.latent_variables == set()


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------


def test_compile_rejects_ode_formalism() -> None:
    """Para ODE no hay compile_scm; usar compile_ode (futuro)."""
    world = _world(formalism="ode")
    with pytest.raises(ValueError, match="formalism='scm'"):
        compile_scm(world)


def test_compile_rejects_non_empty_parameters() -> None:
    """parameters no soportado en v1.5: el Architect debe inlinear."""
    world = _world(parameters={"coef": 0.5})
    with pytest.raises(NotImplementedError, match="parameters no soportado"):
        compile_scm(world)


def test_compile_propagates_expression_error() -> None:
    """Si una equation referencia una variable que NO es padre, el
    ExpressionCompiler rebota."""
    world = _world(
        variables=[
            VariableSpec(name="A", equation="normal(0, 1)"),
            VariableSpec(name="B", equation="A + ZZZ"),  # ZZZ no existe
        ],
        edges=[("A", "B")],
    )
    with pytest.raises(ExpressionError):
        compile_scm(world)


def test_compile_propagates_runtime_error() -> None:
    """Si una equation explota en runtime (ej. división por cero), el
    error se propaga al caller. Usamos 2 variables (constraint
    `>= 2 variables`) y forzamos el error en una de ellas."""
    world = _world(
        variables=[
            VariableSpec(name="A", equation="normal(0, 1)"),
            VariableSpec(name="B", equation="1 / 0"),  # explota al samplear
        ],
        edges=[],
    )
    with pytest.raises((ValueError, ZeroDivisionError)):
        compile_scm(world)


# ---------------------------------------------------------------------------
# edges ↔ equations coherence (cierra hueco detectado por Codex 2026-05-05)
# ---------------------------------------------------------------------------


def test_compile_rejects_decorative_edge() -> None:
    """Edge declarado pero no usado en la equation: estructura causal mentirosa."""
    world = _world(
        variables=[
            VariableSpec(name="A", equation="normal(0, 1)"),
            VariableSpec(name="B", equation="normal(0, 1)"),  # NO usa A
        ],
        edges=[("A", "B")],
    )
    with pytest.raises(ValueError, match="declarados como parents"):
        compile_scm(world)


def test_compile_rejects_implicit_dependency() -> None:
    """Equation usa variable sin edge declarado: dependencia oculta."""
    world = _world(
        variables=[
            VariableSpec(name="A", equation="normal(0, 1)"),
            VariableSpec(name="B", equation="A + normal(0, 0.1)"),  # usa A
        ],
        edges=[],  # pero NO hay edge declarado
    )
    with pytest.raises(ValueError, match="no hay edges entrantes"):
        compile_scm(world)


def test_compile_accepts_consistent_dag() -> None:
    """Equation y edges coinciden: pasa."""
    world = _world(
        variables=[
            VariableSpec(name="A", equation="normal(0, 1)"),
            VariableSpec(name="B", equation="normal(0, 1)"),
            VariableSpec(name="Y", equation="A + 2*B + normal(0, 0.1)"),
        ],
        edges=[("A", "Y"), ("B", "Y")],
    )
    scm = compile_scm(world)
    # Sanity: el SCM compila y samplea.
    df = scm.sample(n=10, seed=0)
    assert set(df.columns) >= {"A", "B", "Y"}


def test_compile_error_message_lists_missing_edges() -> None:
    """Mensaje de error es accionable: dice qué edges agregar."""
    world = _world(
        variables=[
            VariableSpec(name="A", equation="normal(0, 1)"),
            VariableSpec(name="B", equation="normal(0, 1)"),
            VariableSpec(name="Y", equation="A + B + normal(0, 0.1)"),
        ],
        edges=[("A", "Y")],  # falta el edge (B, Y)
    )
    with pytest.raises(ValueError) as exc_info:
        compile_scm(world)
    msg = str(exc_info.value)
    assert "B" in msg  # menciona el parent faltante
    assert "Y" in msg  # menciona el child


# ---------------------------------------------------------------------------
# Cobertura del adapter
# ---------------------------------------------------------------------------


def test_compile_preserves_intended_phenomena_in_worldspec() -> None:
    """`intended_phenomena` no se mapea al SCMWorld (es input downstream
    al Designer); pero NO debe romper el compile."""
    world = _world(
        variables=[
            VariableSpec(name="X", equation="normal(0, 1)"),
            VariableSpec(name="Y", equation="X + normal(0, 0.1)"),
        ],
        edges=[("X", "Y")],
    )
    world = WorldSpec(
        **{
            **world.model_dump(),
            "intended_phenomena": [
                IntendedPhenomenon(
                    id="ip1",
                    kind="chain",
                    description="X causa Y",
                    relevant_variables=["X", "Y"],
                ).model_dump()
            ],
        }
    )
    scm = compile_scm(world)
    # SCMWorld no tiene intended_phenomena: ese conocimiento queda en WorldSpec.
    assert isinstance(scm, SCMWorld)


def test_compile_idempotent_per_seed() -> None:
    """Compilar el mismo WorldSpec dos veces produce SCMWorlds que samplean
    igual con la misma seed (ignoramos diferencias en `id` UUID)."""
    world = _world(
        variables=[
            VariableSpec(name="A", equation="normal(0, 1)"),
            VariableSpec(name="B", equation="A + normal(0, 0.1)"),
        ],
        edges=[("A", "B")],
    )
    scm1 = compile_scm(world)
    scm2 = compile_scm(world)
    df1 = scm1.sample(n=100, seed=123)
    df2 = scm2.sample(n=100, seed=123)
    # Misma seed → misma muestra
    assert (df1.values == df2.values).all()
