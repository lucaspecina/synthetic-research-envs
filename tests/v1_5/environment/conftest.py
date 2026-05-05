"""Fixtures de Environment v1.5.

Mundos SCM hand-authored para tests del Environment. Estos mundos son
DETERMINISTAS dado un seed: los tests pueden assertar exactitudes
numéricas dentro de tolerancias declaradas. También se reusarán para
tests de los agentes del Designer (Explorer/Designer, Selector, etc.).
"""

from __future__ import annotations

import numpy as np
import pytest

from sreg.v1_5.environment import SCMEnvironmentAdapter
from sreg.world.scm import SCMWorld


def _gaussian(mean: float, std: float):
    """Equation factory: X ~ Normal(mean, std), independiente de los padres."""

    def eq(parents: dict[str, float], rng: np.random.Generator) -> float:
        return float(mean + std * rng.standard_normal())

    return eq


def _linear(coefs: dict[str, float], intercept: float = 0.0, std: float = 0.1):
    """Equation factory: X = intercept + sum(coef * parent) + N(0, std)."""

    def eq(parents: dict[str, float], rng: np.random.Generator) -> float:
        val = intercept + sum(coefs.get(p, 0.0) * parents[p] for p in parents)
        return float(val + std * rng.standard_normal())

    return eq


@pytest.fixture
def trivial_scm() -> SCMWorld:
    """Mundo SCM mínimo: X → Y, sin confounders.

    - X ~ N(0, 1)
    - Y = 2 * X + N(0, 0.1)

    ATE(X → Y) ≈ 2 (efecto causal verdadero).
    Asociación cruda(X, Y) ≈ ~0.998 (dominada por el efecto directo).
    Confounding gap ≈ 0 (no hay confounders).
    """
    return SCMWorld(
        graph={"X": [], "Y": ["X"]},
        equations={
            "X": _gaussian(mean=0.0, std=1.0),
            "Y": _linear(coefs={"X": 2.0}, intercept=0.0, std=0.1),
        },
    )


@pytest.fixture
def confounded_scm() -> SCMWorld:
    """Mundo SCM con confounder: U → X, U → Y, X → Y.

    - U ~ N(0, 1)         (confounder)
    - X = U + N(0, 0.1)
    - Y = 2 * X + 3 * U + N(0, 0.1)

    Causal ATE(X → Y) = 2 (post-do).
    Asociación cruda(X, Y) ≈ 2 + 3 = 5 (overstated por el confounder U).
    Confounding gap ≈ 3.
    Adjustment set para identificar X → Y: {U}.
    """
    return SCMWorld(
        graph={"U": [], "X": ["U"], "Y": ["X", "U"]},
        equations={
            "U": _gaussian(mean=0.0, std=1.0),
            "X": _linear(coefs={"U": 1.0}, intercept=0.0, std=0.1),
            "Y": _linear(coefs={"X": 2.0, "U": 3.0}, intercept=0.0, std=0.1),
        },
    )


@pytest.fixture
def trivial_env(trivial_scm: SCMWorld) -> SCMEnvironmentAdapter:
    return SCMEnvironmentAdapter(trivial_scm)


@pytest.fixture
def confounded_env(confounded_scm: SCMWorld) -> SCMEnvironmentAdapter:
    return SCMEnvironmentAdapter(confounded_scm)


@pytest.fixture
def latent_confounder_env() -> SCMEnvironmentAdapter:
    """Mundo con `U` LATENTE (confounder no observado).

    - U ~ N(0, 1)         (latente)
    - X = U + N(0, 0.1)
    - Y = 2*X + 3*U + N(0, 0.1)

    `observable_variables = {X, Y}`. `U` no aparece por default en
    `observe()`/`intervene()`.
    """
    world = SCMWorld(
        graph={"U": [], "X": ["U"], "Y": ["X", "U"]},
        equations={
            "U": _gaussian(mean=0.0, std=1.0),
            "X": _linear(coefs={"U": 1.0}, intercept=0.0, std=0.1),
            "Y": _linear(coefs={"X": 2.0, "U": 3.0}, intercept=0.0, std=0.1),
        },
        latent_variables={"U"},
    )
    return SCMEnvironmentAdapter(world)
