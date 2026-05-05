"""Adapter de `SCMWorld` v1 al protocol `SCMEnvironment` v1.5.

`SCMWorld` (en `sreg.world.scm`) ya hace todo el trabajo pesado: sampling,
do-calculus, d-separation, backdoor adjustment sets. Este adapter es
delgado — solo expone una superficie consistente con el protocol.

NO copiamos el código v1; lo wrappamos. v1.5 importa de v1 (la
dependencia es unidireccional: v1 NO importa de v1.5).
"""

from __future__ import annotations

from typing import Mapping, Sequence

import pandas as pd

from sreg.world.scm import SCMWorld


class SCMEnvironmentAdapter:
    """Adapter delgado: `SCMWorld` v1 → `SCMEnvironment` protocol v1.5.

    Uso típico:
        >>> world = SCMWorld(...)        # construido por el caller
        >>> env = SCMEnvironmentAdapter(world)
        >>> df = env.observe(n=1000, seed=42)
    """

    formalism: str = "scm"

    def __init__(self, world: SCMWorld) -> None:
        self._world = world

    # -- BaseEnvironment surface --------------------------------------

    @property
    def variables(self) -> list[str]:
        return list(self._world.variables)

    @property
    def observable_variables(self) -> list[str]:
        return list(self._world.observable_variables)

    # -- SCMEnvironment surface ---------------------------------------

    def observe(
        self,
        *,
        n: int,
        columns: Sequence[str] | None = None,
        seed: int | None = None,
    ) -> pd.DataFrame:
        df = self._world.sample(n=n, seed=seed)
        # `columns=None` significa "todas las observables" según el
        # protocol (`protocols.py`). Las latentes NUNCA se exponen por
        # default — para acceder a ellas hay que pedirlas explícitamente
        # vía `columns=env.variables`. Esa explicitud refuerza la
        # frontera público/oculto.
        if columns is None:
            columns = self.observable_variables
        return self._project_columns(df, columns)

    def intervene(
        self,
        *,
        do: Mapping[str, float],
        n: int,
        columns: Sequence[str] | None = None,
        seed: int | None = None,
    ) -> pd.DataFrame:
        df = self._world.sample(n=n, seed=seed, do=dict(do))
        if columns is None:
            columns = self.observable_variables
        return self._project_columns(df, columns)

    def is_d_separated(
        self,
        x: str | set[str],
        y: str | set[str],
        z: set[str] | None = None,
    ) -> bool:
        return self._world.is_d_separated(x, y, z)

    def get_backdoor_adjustment_sets(
        self, treatment: str, outcome: str
    ) -> list[frozenset[str]]:
        return self._world.get_all_backdoor_adjustment_sets(treatment, outcome)

    # -- internals ----------------------------------------------------

    @staticmethod
    def _project_columns(
        df: pd.DataFrame, columns: Sequence[str] | None
    ) -> pd.DataFrame:
        if columns is None:
            return df
        cols = list(columns)
        missing = set(cols) - set(df.columns)
        if missing:
            raise ValueError(
                f"Columns not in SCM output: {sorted(missing)}. "
                f"Available: {sorted(df.columns)}"
            )
        return df[cols]


__all__ = ["SCMEnvironmentAdapter"]
