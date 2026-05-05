"""Compila un `WorldSpec` v1.5 (formalism='scm') a un `SCMWorld` v1.

Wrapper fino sobre `SCMWorldGenTool` v1: el adapter
`_world_to_scm_spec` mapea contratos v1.5 → v1, y luego se reusa toda
la lógica probada (compile equations + build graph + validate by
sampling). NO duplicamos el motor.

El `WorldSpec` v1.5 quedó alineado intencionalmente con `SCMSpec` v1
para que este adapter sea trivial (ver `world.py` v1.5 docstring y
`research/notes/v1_5_debates.md` Ronda 14).

Limitaciones explícitas en v1.5:
- `WorldSpec.parameters` no soportado para SCM (rebota con
  `NotImplementedError`). El Architect debe inlinear valores literales
  en las `equation`s.
- `VariableSpec.kind` es metadata-only: el compiler NO valida que los
  samples respeten el `kind` declarado. v1.6+.
- `WorldSpec.metadata.domain` no se mapea a `SCMSpec` (no tiene
  equivalente). Se mantiene en el WorldSpec si el caller lo necesita.
"""

from __future__ import annotations

from sreg.models.scm_spec import SCMSpec, SCMVariableSpec
from sreg.tools.scm_world_gen import SCMWorldGenTool
from sreg.v1_5.contracts.world import WorldSpec
from sreg.world.scm import SCMWorld


def compile_scm(world: WorldSpec, *, seed: int = 42) -> SCMWorld:
    """Compila un `WorldSpec` (formalism='scm') a un `SCMWorld` ejecutable.

    Args:
        world: spec declarativa producida por el Architect.
        seed: seed para la validación interna por sampling
            (`SCMWorldGenTool._validate`).

    Returns:
        `SCMWorld` listo para `sample`/`intervene`/`is_d_separated`/etc.

    Raises:
        ValueError: si `world.formalism != 'scm'`.
        NotImplementedError: si `world.parameters` no está vacío
            (sustitución determinista no soportada en v1.5).
        ExpressionError: si alguna `equation` es inválida o referencia
            variables no padres.
        ValueError (de `SCMWorldGenTool._validate`): si los samples
            tienen NaN/Inf, varianza nula, o valores extremos.
    """
    if world.formalism != "scm":
        raise ValueError(
            f"compile_scm requiere formalism='scm', got '{world.formalism}'. "
            f"Para ODE usar compile_ode (no implementado todavía)."
        )
    if world.parameters:
        raise NotImplementedError(
            f"WorldSpec.parameters no soportado en SCM v1.5: "
            f"{sorted(world.parameters.keys())}. El Architect debe "
            f"inlinear valores literales en las equations. "
            f"Sustitución determinista de parámetros: v1.6+."
        )
    if len(world.variables) < 2:
        # Heritage constraint de SCMSpec v1 (`min_length=2`). Lo enforce
        # acá con mensaje útil antes que un ValidationError críptico.
        raise ValueError(
            f"compile_scm requiere WorldSpec con >= 2 variables (heritage "
            f"constraint de SCMWorldGenTool v1). Got "
            f"{len(world.variables)} variable(s): "
            f"{[v.name for v in world.variables]}."
        )

    spec_v1 = _world_to_scm_spec(world)
    return SCMWorldGenTool().generate(spec_v1, seed=seed)


def _world_to_scm_spec(world: WorldSpec) -> SCMSpec:
    """Adapter de contratos v1.5 → v1.

    Mapeos:
    - `VariableSpec.name` → `SCMVariableSpec.name`
    - `VariableSpec.equation` → `SCMVariableSpec.equation` (garantizado
       no-None por el validador `_check_scm_has_equations` de WorldSpec)
    - `VariableSpec.is_observable=True/False` →
       `SCMVariableSpec.role='observable'/'latent'`
    - `VariableSpec.description` → `SCMVariableSpec.description` (default '')
    - `WorldSpec.edges` → `SCMSpec.edges` (mismo tipo)

    Pérdidas conscientes (no mapean):
    - `VariableSpec.kind` (metadata-only en v1.5)
    - `WorldSpec.metadata` (no hay equivalente en SCMSpec)
    - `WorldSpec.intended_phenomena` (input al Designer, no al compiler)
    - `WorldSpec.observation_noise` (no aplica a SCM)
    """
    scm_variables: list[SCMVariableSpec] = []
    for v in world.variables:
        if v.equation is None:
            # Defensa por si alguien construye con `model_construct` o
            # bypass-ea el validador. NO usamos `assert` (se elimina con -O).
            raise ValueError(
                f"VariableSpec '{v.name}' no tiene `equation`; el "
                f"validador de WorldSpec(formalism='scm') debió haberlo "
                f"rebotado. Probable construcción con `model_construct` "
                f"que salta validación."
            )
        scm_variables.append(
            SCMVariableSpec(
                name=v.name,
                role="observable" if v.is_observable else "latent",
                description=v.description or "",
                equation=v.equation,
            )
        )

    return SCMSpec(
        variables=scm_variables,
        edges=list(world.edges),
    )


__all__ = ["compile_scm"]
