"""Tests del SCMEnvironmentAdapter.

Verifica que:
- El adapter satisface el `SCMEnvironment` Protocol (runtime checkable).
- `observe` y `intervene` devuelven DataFrames con shape correcto.
- Los métodos de DAG (`is_d_separated`, backdoor sets) funcionan.
- Reproducibilidad con seed.
"""

from __future__ import annotations

import pandas as pd
import pytest

from sreg.v1_5.environment import SCMEnvironment, SCMEnvironmentAdapter

# -- Protocol satisfaction -------------------------------------------------


def test_adapter_satisfies_protocol(trivial_env: SCMEnvironmentAdapter) -> None:
    """`isinstance(env, SCMEnvironment)` con `runtime_checkable` Protocol."""
    assert isinstance(trivial_env, SCMEnvironment)


def test_adapter_exposes_formalism(trivial_env: SCMEnvironmentAdapter) -> None:
    assert trivial_env.formalism == "scm"


def test_adapter_exposes_variables(trivial_env: SCMEnvironmentAdapter) -> None:
    assert set(trivial_env.variables) == {"X", "Y"}


def test_adapter_exposes_observable_variables(
    trivial_env: SCMEnvironmentAdapter,
) -> None:
    assert set(trivial_env.observable_variables) == {"X", "Y"}


# -- observe ---------------------------------------------------------------


def test_observe_returns_dataframe(trivial_env: SCMEnvironmentAdapter) -> None:
    df = trivial_env.observe(n=100, seed=42)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 100
    assert set(df.columns) == {"X", "Y"}


def test_observe_with_columns_filter(trivial_env: SCMEnvironmentAdapter) -> None:
    df = trivial_env.observe(n=50, columns=["X"], seed=42)
    assert list(df.columns) == ["X"]
    assert len(df) == 50


def test_observe_unknown_column_raises(
    trivial_env: SCMEnvironmentAdapter,
) -> None:
    with pytest.raises(ValueError):
        trivial_env.observe(n=10, columns=["nonexistent"], seed=42)


def test_observe_reproducible_with_seed(
    trivial_env: SCMEnvironmentAdapter,
) -> None:
    df1 = trivial_env.observe(n=100, seed=42)
    df2 = trivial_env.observe(n=100, seed=42)
    pd.testing.assert_frame_equal(df1, df2)


def test_observe_different_seeds_differ(
    trivial_env: SCMEnvironmentAdapter,
) -> None:
    df1 = trivial_env.observe(n=100, seed=1)
    df2 = trivial_env.observe(n=100, seed=2)
    assert not df1.equals(df2)


# -- intervene -------------------------------------------------------------


def test_intervene_fixes_variable(trivial_env: SCMEnvironmentAdapter) -> None:
    df = trivial_env.intervene(do={"X": 5.0}, n=200, seed=42)
    # Bajo do(X=5), X debe ser exactamente 5.0 en todas las filas.
    assert (df["X"] == 5.0).all()


def test_intervene_propagates_through_graph(
    trivial_env: SCMEnvironmentAdapter,
) -> None:
    """Y = 2X + ε. Bajo do(X=5), E[Y] ≈ 10."""
    df = trivial_env.intervene(do={"X": 5.0}, n=2000, seed=42)
    assert abs(df["Y"].mean() - 10.0) < 0.1  # tolerancia generosa


def test_intervene_blocks_confounder(
    confounded_env: SCMEnvironmentAdapter,
) -> None:
    """Confounded SCM: bajo do(X=5), Y = 2X + 3U + ε.
    E[Y | do(X=5)] = 10 + 3*E[U] = 10 (porque E[U]=0).
    Sin do, Cor(X, Y) sería más alta porque U sube ambos.
    """
    df_intervened = confounded_env.intervene(do={"X": 5.0}, n=2000, seed=42)
    assert abs(df_intervened["Y"].mean() - 10.0) < 0.3  # tolerancia mayor por U noise


# -- DAG queries ----------------------------------------------------------


def test_is_d_separated_no_confounder(
    trivial_env: SCMEnvironmentAdapter,
) -> None:
    """X y Y NO son d-separadas (X causa Y directamente)."""
    assert trivial_env.is_d_separated("X", "Y") is False


def test_backdoor_sets_no_confounder(
    trivial_env: SCMEnvironmentAdapter,
) -> None:
    """Sin confounders: el set vacío es válido para identificar X → Y."""
    sets = trivial_env.get_backdoor_adjustment_sets("X", "Y")
    assert frozenset() in sets


def test_backdoor_sets_with_confounder(
    confounded_env: SCMEnvironmentAdapter,
) -> None:
    """Con confounder U: {U} debe ser un set válido."""
    sets = confounded_env.get_backdoor_adjustment_sets("X", "Y")
    assert frozenset({"U"}) in sets
    # Y el set vacío NO debe ser válido (porque U deja un back-door abierto).
    assert frozenset() not in sets
