"""Protocols de Environment v1.5.

Usamos `typing.Protocol` (duck typing) en lugar de clases base con
herencia. Cualquier objeto con la firma correcta es válido como
Environment, lo que permite reutilizar `SCMWorld` v1 sin tocar su
jerarquía.

Tres protocols:

- `BaseEnvironment`: lo común a cualquier Environment (formalism + lista
  de variables + variables observables).
- `SCMEnvironment`: agrega `observe`, `intervene` y queries del DAG
  (`is_d_separated`, `get_backdoor_adjustment_sets`).
- `ODEEnvironment`: agrega `simulate` para trayectorias temporales.

Los `Sequence`/`Mapping` son las versiones permisivas: cualquier list,
dict u otra colección compatible es válida. Devolvemos `pd.DataFrame`
porque es el lenguaje natural para datos tabulares.
"""

from __future__ import annotations

from typing import Literal, Mapping, Protocol, Sequence, runtime_checkable

import pandas as pd


@runtime_checkable
class BaseEnvironment(Protocol):
    """Common surface of any Environment (SCM or ODE).

    Atributos (no métodos): el `formalism` y las listas de variables.
    """

    formalism: Literal["scm", "ode"]
    variables: list[str]
    """Todas las variables del WorldModel, en orden topológico para SCM."""
    observable_variables: list[str]
    """Subconjunto de `variables` que NO es latente (visible en datasets)."""


@runtime_checkable
class SCMEnvironment(BaseEnvironment, Protocol):
    """Environment de mundo causal estático (SCM).

    Soporta `observe` y `intervene` (do-operator). Además expone queries
    sobre el DAG para identifiability checks: `is_d_separated` y
    `get_backdoor_adjustment_sets`.
    """

    formalism: Literal["scm"]

    def observe(
        self,
        *,
        n: int,
        columns: Sequence[str] | None = None,
        seed: int | None = None,
    ) -> pd.DataFrame:
        """Samplear `n` filas observacionales del WorldModel.

        Args:
            n: número de filas a samplear.
            columns: subconjunto de variables a devolver (default: todas
                las variables observables).
            seed: para reproducibilidad.

        Returns:
            DataFrame con `n` filas y las columnas pedidas.
        """
        ...

    def intervene(
        self,
        *,
        do: Mapping[str, float],
        n: int,
        columns: Sequence[str] | None = None,
        seed: int | None = None,
    ) -> pd.DataFrame:
        """Samplear `n` filas bajo do-operator de Pearl.

        Las variables en `do` quedan fijas a su valor; sus padres dejan
        de afectarlas. El resto del SCM se samplea normalmente.
        """
        ...

    def is_d_separated(
        self,
        x: str | set[str],
        y: str | set[str],
        z: set[str] | None = None,
    ) -> bool:
        """¿X y Y son d-separadas dado Z en el DAG?"""
        ...

    def get_backdoor_adjustment_sets(
        self, treatment: str, outcome: str
    ) -> list[frozenset[str]]:
        """Todos los conjuntos válidos de back-door adjustment para
        identificar el efecto causal `treatment → outcome`.

        Vacío si el efecto no es identificable bajo el DAG actual.
        """
        ...


@runtime_checkable
class ODEEnvironment(BaseEnvironment, Protocol):
    """Environment de mundo dinámico determinista (ODE).

    Soporta `simulate` para producir trayectorias temporales. Acepta
    `do` opcional para forzar variables a valores fijos durante toda
    la simulación (intervención dinámica simple).
    """

    formalism: Literal["ode"]

    def simulate(
        self,
        *,
        initial: Mapping[str, float],
        t_eval: Sequence[float],
        do: Mapping[str, float] | None = None,
        n_paths: int = 1,
        seed: int | None = None,
        parameters: Mapping[str, float] | None = None,
    ) -> pd.DataFrame:
        """Simular trayectorias del sistema.

        Args:
            initial: condiciones iniciales (valor de cada variable en t=0).
            t_eval: puntos temporales a evaluar.
            do: variables a forzar a valor fijo durante toda la simulación.
            n_paths: cuántas trayectorias generar (>1 solo tiene sentido si
                el ODE incluye observation_noise; con noise=0 todas serían
                idénticas).
            seed: para reproducibilidad del noise.
            parameters: override de los parámetros default del WorldModel.

        Returns:
            DataFrame en formato tidy con columnas:
            `["trajectory_id", "time", *variables]`.
        """
        ...


__all__ = ["BaseEnvironment", "SCMEnvironment", "ODEEnvironment"]
