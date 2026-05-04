"""SREG v1.5 — rediseño que reemplaza el compiler NL↔IR de v1 por
rubric + LLM judge + answer key grounded en Environment.

Subpackage paralelo a `sreg.*` v1 mientras v1.5 está en construcción.
v1 NO debe importar de `sreg.v1_5`. Cuando v1.5 cierre, v1 se elimina y
este subpackage sube al root.

Ver `ARCHITECTURE.md` (raíz del repo) para la spec.
"""

__all__: list[str] = []
