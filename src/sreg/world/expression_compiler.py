"""Safe expression compiler for SCM equations.

Compiles math expression strings (e.g. "0.5 * X + normal(0, 2)") into
EquationFn callables that SCMWorld accepts. Uses ast.parse() with a
whitelist visitor -- NO eval() of raw strings.

Security model:
- Only arithmetic, comparisons, ternary, and whitelisted function calls allowed
- No attribute access, imports, subscripts, or string constants
- Namespace restricted to parent variables + math + distributions
"""

from __future__ import annotations

import ast
from typing import Any

import numpy as np

from sreg.world.scm import EquationFn

# AST node types allowed in equations
_ALLOWED_NODE_TYPES: set[type] = {
    ast.Expression,
    # Binary operations
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.FloorDiv,
    # Unary operations
    ast.UnaryOp,
    ast.USub,
    ast.UAdd,
    ast.Not,
    # Comparisons (for piecewise expressions)
    ast.Compare,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Eq,
    ast.NotEq,
    # Boolean operations (compound conditions)
    ast.BoolOp,
    ast.And,
    ast.Or,
    # Ternary: value_if_true if condition else value_if_false
    ast.IfExp,
    # Function calls (only whitelisted names)
    ast.Call,
    # Names and constants
    ast.Name,
    ast.Constant,
    # Keyword arguments in function calls
    ast.keyword,
}

# Functions allowed in equations
_ALLOWED_FUNCTIONS: frozenset[str] = frozenset(
    {
        # Math
        "exp",
        "log",
        "log2",
        "log10",
        "sqrt",
        "sin",
        "cos",
        "tan",
        "abs",
        "min",
        "max",
        "pow",
        "ceil",
        "floor",
        "round",
        # Distributions (bound to rng at eval time)
        "normal",
        "uniform",
        "exponential",
        "lognormal",
        "beta",
        "gamma",
        "bernoulli",
        # Helpers (deterministic)
        "sigmoid",
        "I",
    }
)


class ExpressionError(ValueError):
    """Raised when an expression string is invalid or unsafe."""


class _WhitelistVisitor(ast.NodeVisitor):
    """AST visitor that rejects any construct not in the whitelist."""

    def __init__(self, parent_names: set[str]) -> None:
        self.parent_names = parent_names

    def generic_visit(self, node: ast.AST) -> None:
        if type(node) not in _ALLOWED_NODE_TYPES:
            raise ExpressionError(f"Disallowed construct: {type(node).__name__}")
        super().generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        all_names = self.parent_names | _ALLOWED_FUNCTIONS
        if node.id not in all_names:
            raise ExpressionError(
                f"Unknown name '{node.id}'. "
                f"Available variables: {sorted(self.parent_names)}"
            )

    def visit_Call(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Name):
            raise ExpressionError(
                "Only simple function calls allowed (no methods or attribute access)"
            )
        if node.func.id not in _ALLOWED_FUNCTIONS:
            raise ExpressionError(
                f"Unknown function '{node.func.id}'. "
                f"Available: {sorted(_ALLOWED_FUNCTIONS)}"
            )
        # Visit arguments (skip func -- already validated above)
        for arg in node.args:
            self.visit(arg)
        for kw in node.keywords:
            self.visit(kw.value)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ExpressionError(
                f"Only numeric constants allowed, got {type(node.value).__name__}"
            )


class ExpressionCompiler:
    """Compiles math expression strings into safe EquationFn callables.

    The compiled functions match the EquationFn signature:
        (parents_dict: dict[str, float], rng: np.random.Generator) -> float

    Usage::

        compiler = ExpressionCompiler()
        eq = compiler.compile_equation("0.5 * X + normal(0, 2)", ["X"])
        rng = np.random.default_rng(42)
        value = eq({"X": 10.0}, rng)  # -> ~7.0
    """

    def compile_equation(
        self,
        expr: str,
        parent_names: list[str],
    ) -> EquationFn:
        """Compile an expression string into an EquationFn.

        Args:
            expr: Math expression, e.g. ``"0.5 * X + normal(0, 2)"``.
            parent_names: Names of parent variables available in the expression.

        Returns:
            Callable matching EquationFn signature.

        Raises:
            ExpressionError: If the expression is invalid or contains unsafe constructs.
        """
        expr = expr.strip()
        if not expr:
            raise ExpressionError("Empty expression")

        # 1. Parse
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as e:
            raise ExpressionError(f"Syntax error in '{expr}': {e}") from e

        # 2. Validate AST against whitelist
        visitor = _WhitelistVisitor(set(parent_names))
        visitor.visit(tree)

        # 3. Compile to bytecode
        code = compile(tree, f"<equation: {expr}>", "eval")

        # 4. Return closure
        def equation(parents: dict[str, float], rng: np.random.Generator) -> float:
            namespace = _build_namespace(parents, rng)
            return float(eval(code, {"__builtins__": {}}, namespace))  # noqa: S307

        # Store source for debugging / repr
        equation.__doc__ = expr
        equation.__qualname__ = f"equation<{expr}>"

        return equation


def _build_namespace(
    parents: dict[str, float],
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Build the restricted evaluation namespace for an equation."""
    ns: dict[str, Any] = {}

    # Parent variable values
    ns.update(parents)

    # Math functions (numpy for robustness: returns inf/nan instead of raising)
    ns.update(
        {
            "exp": np.exp,
            "log": np.log,
            "log2": np.log2,
            "log10": np.log10,
            "sqrt": np.sqrt,
            "sin": np.sin,
            "cos": np.cos,
            "tan": np.tan,
            "abs": abs,
            "min": min,
            "max": max,
            "pow": pow,
            "ceil": np.ceil,
            "floor": np.floor,
            "round": round,
        }
    )

    # Distribution functions (bound to rng for reproducibility)
    ns.update(
        {
            "normal": lambda mu, sigma: float(rng.normal(mu, sigma)),
            "uniform": lambda lo, hi: float(rng.uniform(lo, hi)),
            "exponential": lambda scale: float(rng.exponential(scale)),
            "lognormal": lambda mu, sigma: float(rng.lognormal(mu, sigma)),
            "beta": lambda a, b: float(rng.beta(a, b)),
            "gamma": lambda shape, scale=1.0: float(rng.gamma(shape, scale)),
            "bernoulli": lambda p: float(rng.binomial(1, p)),
        }
    )

    # Deterministic helpers (no rng)
    ns.update(
        {
            # sigmoid(x) = 1 / (1 + exp(-x)), numerically stable.
            "sigmoid": lambda x: float(1.0 / (1.0 + np.exp(-x))),
            # I(condition) -> 1.0 if condition else 0.0 — indicator function.
            "I": lambda cond: 1.0 if bool(cond) else 0.0,
        }
    )

    return ns


__all__ = ["ExpressionCompiler", "ExpressionError"]
