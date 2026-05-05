"""World v1.5 — compilación de WorldSpec a SCMWorld ejecutable.

`WorldSpec` es la spec declarativa que produce el Architect. Para tener
un mundo **ejecutable** (samplear, intervenir, validar), hay que compilar
ese spec a un `SCMWorld` (la implementación matemática, heritage v1).

`compile_scm` es la función pública. Wrapper fino sobre `SCMWorldGenTool`
v1 — no duplicamos lógica.

Para dinámica (ODE) se agregará `compile_ode` posteriormente (Fase ODE
de v1.5).
"""

from sreg.v1_5.world.compile_scm import compile_scm

__all__ = ["compile_scm"]
