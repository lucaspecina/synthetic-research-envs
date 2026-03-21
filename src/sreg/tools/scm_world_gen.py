"""SCMWorldGenTool: builds SCMWorld from a declarative SCMSpec.

Takes an SCMSpec (what the LLM produces via function calling),
compiles expression strings into safe equations, validates the
resulting world by sampling, and returns a ready-to-use SCMWorld.
"""

from __future__ import annotations

import logging
import uuid

import numpy as np

from sreg.models.scm_spec import SCMSpec
from sreg.world.expression_compiler import ExpressionCompiler, ExpressionError
from sreg.world.scm import EquationFn, SCMWorld, VariableMeta

logger = logging.getLogger(__name__)

# Validation thresholds
_VALIDATION_SAMPLES = 1000
_MIN_VARIANCE = 1e-10
_MAX_ABS_VALUE = 1e12


class SCMWorldGenTool:
    """Build and validate SCMWorld instances from declarative specs."""

    def __init__(self) -> None:
        self._compiler = ExpressionCompiler()

    def generate(self, spec: SCMSpec, seed: int = 42) -> SCMWorld:
        """Compile an SCMSpec into a validated SCMWorld.

        Args:
            spec: Declarative specification with variables, edges, and equations.
            seed: Random seed for validation sampling.

        Returns:
            A validated SCMWorld ready for sampling, solving, and task generation.

        Raises:
            ExpressionError: If an equation is invalid or unsafe.
            ValueError: If the world fails validation (NaN, zero variance, etc.).
        """
        # 1. Compile expression strings -> EquationFn callables
        equations = self._compile_equations(spec)

        # 2. Build the SCMWorld
        world = self._build_world(spec, equations)

        # 3. Validate by sampling
        self._validate(world, seed)

        return world

    def _compile_equations(
        self, spec: SCMSpec
    ) -> dict[str, EquationFn]:
        """Compile all equation strings in the spec."""
        equations: dict[str, EquationFn] = {}
        for var in spec.variables:
            parent_names = spec.parents_of(var.name)
            try:
                eq_fn = self._compiler.compile_equation(var.equation, parent_names)
            except ExpressionError as e:
                raise ExpressionError(
                    f"Error in equation for '{var.name}': {e}"
                ) from e
            equations[var.name] = eq_fn
        return equations

    def _build_world(
        self,
        spec: SCMSpec,
        equations: dict[str, EquationFn],
    ) -> SCMWorld:
        """Construct an SCMWorld from the spec and compiled equations."""
        # Build adjacency list: {child: [parent1, parent2, ...]}
        graph: dict[str, list[str]] = {v.name: [] for v in spec.variables}
        for src, dst in spec.edges:
            graph[dst].append(src)

        # Build variable metadata
        variable_meta: dict[str, VariableMeta] = {}
        for v in spec.variables:
            variable_meta[v.name] = VariableMeta(
                unit=v.unit,
                range=v.range if v.range is not None else (0.0, 1.0),
                description=v.description,
            )

        # Identify latent variables
        latent = {v.name for v in spec.variables if v.role == "latent"}

        return SCMWorld(
            graph=graph,
            equations=equations,
            variable_meta=variable_meta,
            id=f"scm-{uuid.uuid4().hex[:8]}",
            latent_variables=latent,
        )

    def _validate(self, world: SCMWorld, seed: int) -> None:
        """Validate world by sampling and checking for degeneracies."""
        try:
            df = world.sample(n=_VALIDATION_SAMPLES, seed=seed)
        except Exception as e:
            raise ValueError(f"World sampling failed: {e}") from e

        issues: list[str] = []

        for col in df.columns:
            values = df[col].values

            # Check NaN
            nan_count = int(np.isnan(values).sum())
            if nan_count > 0:
                issues.append(
                    f"'{col}': {nan_count}/{_VALIDATION_SAMPLES} NaN values"
                )

            # Check Inf
            inf_count = int(np.isinf(values).sum())
            if inf_count > 0:
                issues.append(
                    f"'{col}': {inf_count}/{_VALIDATION_SAMPLES} Inf values"
                )

            # Check variance
            if np.nanvar(values) < _MIN_VARIANCE:
                issues.append(f"'{col}': near-zero variance (constant)")

            # Check extreme values
            max_abs = float(np.nanmax(np.abs(values)))
            if max_abs > _MAX_ABS_VALUE:
                issues.append(
                    f"'{col}': extreme values (max |value| = {max_abs:.2e})"
                )

        if issues:
            raise ValueError(
                "World validation failed:\n"
                + "\n".join(f"  - {i}" for i in issues)
            )

        logger.info(
            "World validated: %d variables, %d samples, all clean.",
            len(world.variables),
            _VALIDATION_SAMPLES,
        )


__all__ = ["SCMWorldGenTool"]
