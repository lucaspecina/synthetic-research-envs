"""Lints deterministas sobre `WorldSpec` post-Architect.

Detectan errores que Pydantic+DAG no atrapan pero que sí corrompen la
semántica del mundo. Vienen de problemas reales encontrados en pilots:

1. **`lint_no_repeated_stochastic_in_branch`**: rechaza equations donde
   una expresión condicional (ternario `a if cond else b`) llama a
   distribuciones estocásticas múltiples veces. Caso real
   (smoking_birthweight, 2026-05-06): `prenatal_care_level` usaba
   `normal(0, 0.8)` dos veces dentro del ternario, así que los
   thresholds se aplicaban sobre dos draws distintos en lugar de un
   score latente único.

2. **`lint_intended_phenomena_no_methodology`**: regex sobre
   `IntendedPhenomenon.description`. Rechaza frases tipo "adjusting
   for X", "conditioning on Y", "once accounted for Z", que mezclan
   consejo de análisis con mecanismo del mundo. Caso real
   (confounding_by_indication, 2026-05-06).

Ambos son llamados desde `compile_scm` antes de pasar a
`SCMWorldGenTool`.
"""

from __future__ import annotations

import ast
import re

from sreg.v1_5.contracts.world import WorldSpec
from sreg.world.expression_compiler import _ALLOWED_FUNCTIONS

# Subset estocástico de las funciones del compiler (las que usan el RNG).
_STOCHASTIC_FUNCTIONS: frozenset[str] = frozenset(
    {
        "normal",
        "uniform",
        "exponential",
        "lognormal",
        "beta",
        "gamma",
        "bernoulli",
    }
)
assert _STOCHASTIC_FUNCTIONS <= _ALLOWED_FUNCTIONS, (
    "_STOCHASTIC_FUNCTIONS deben ser subset de _ALLOWED_FUNCTIONS"
)


# Patrones de texto methodológico que NO deberían aparecer en
# `IntendedPhenomenon.description`. Cada uno es un fragmento sospechoso
# de "consejo de análisis" en lugar de "mecanismo del mundo".
_METHODOLOGY_PATTERNS: tuple[str, ...] = (
    r"\badjusting for\b",
    r"\badjust for\b",
    r"\bcontrolling for\b",
    r"\bcontrol for\b",
    r"\bconditioning on\b",
    r"\bonce accounted for\b",
    r"\bonce we account for\b",
    r"\bonce .* is accounted for\b",
    r"\bonce .* are accounted for\b",
    r"\bafter adjustment\b",
    r"\bafter controlling\b",
    r"\bbackdoor path\b",
    r"\bminimum adjustment set\b",
    r"\bproperly adjusted\b",
    r"\bwould bias\b",
    r"\bwould distort\b",
)
_METHODOLOGY_RE = re.compile(
    "|".join(_METHODOLOGY_PATTERNS), flags=re.IGNORECASE
)


def lint_no_repeated_stochastic_in_branch(world: WorldSpec) -> None:
    """Rechaza equations donde un ternario contiene >=2 calls estocásticas.

    Detecta el patrón "construir un categórico con thresholds sobre
    `normal(...)` llamado múltiples veces" que produce dos draws
    distintos por evaluación.

    Permitido:
        - Una sola call estocástica por ternario.
        - Calls estocásticas fuera de IfExp (ej. `a + normal(0, 1)`).

    Raises:
        ValueError con mensaje accionable si una equation viola la regla.
    """
    for var in world.variables:
        if var.equation is None:
            continue
        try:
            tree = ast.parse(var.equation, mode="eval")
        except SyntaxError:
            # ExpressionCompiler reporta esto en compile-time.
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.IfExp):
                continue
            stochastic_calls = _count_stochastic_calls(node)
            if stochastic_calls >= 2:
                raise ValueError(
                    f"Variable '{var.name}': la equation contiene un "
                    f"ternario con {stochastic_calls} calls estocásticas "
                    f"(normal/bernoulli/uniform/etc). Cada call genera "
                    f"un draw distinto, así que los branches del ternario "
                    f"se evalúan sobre números aleatorios DIFERENTES, no "
                    f"sobre un mismo score latente.\n\nEquation:\n  "
                    f"{var.equation}\n\nFix: extraer el draw a una "
                    f"variable intermedia (otro nodo del SCM) o reescribir "
                    f"sin ternario."
                )


def lint_intended_phenomena_no_methodology(world: WorldSpec) -> None:
    """Rechaza `IntendedPhenomenon.description` con frases methodológicas.

    Cada `intended_phenomenon` debe describir un MECANISMO del mundo.
    Frases como "adjusting for X", "conditioning on Y" son CONSEJO de
    análisis y pertenecen a `complications` (que el Architect no toca),
    no a `intended_phenomena`.

    Raises:
        ValueError con la frase ofensiva citada y una guía de fix.
    """
    for ip in world.intended_phenomena:
        match = _METHODOLOGY_RE.search(ip.description)
        if match:
            raise ValueError(
                f"IntendedPhenomenon '{ip.id}' (kind='{ip.kind}') tiene "
                f"frase methodológica en su description: '{match.group(0)}'.\n\n"
                f"Description completa:\n  {ip.description}\n\n"
                f"Las intended_phenomena describen MECANISMOS del mundo, "
                f"no consejo de análisis. Reescribí en términos del "
                f"mundo (ej. en lugar de 'adjusting for severity recovers "
                f"the effect', escribí 'severity is a common cause of "
                f"treatment and outcome')."
            )


# -- internals -------------------------------------------------------------


def _count_stochastic_calls(node: ast.AST) -> int:
    """Cuenta llamadas a funciones estocásticas en un sub-árbol AST."""
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            if child.func.id in _STOCHASTIC_FUNCTIONS:
                count += 1
    return count


__all__ = [
    "lint_no_repeated_stochastic_in_branch",
    "lint_intended_phenomena_no_methodology",
]
