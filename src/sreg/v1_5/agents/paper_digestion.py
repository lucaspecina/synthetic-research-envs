"""Agente Paper Digestion: paper crudo → `PaperInsights`.

Lee un paper / seed y extrae una representación estructurada con dos
artefactos:

1. **Mecanismos / fenómenos** (técnicos) que consume el World Architect.
2. **`narrative_capsule`** saneada (anti-leak) que consumen Question
   Designer y Case Writer.

Implementación: function calling sobre el `ModelClient` v1 con el schema
JSON auto-generado de `PaperInsights`. El prompt del sistema vive en
`prompts/paper_digestion.md` (fácil de iterar sin tocar código).

NO valida que el contenido sea fielmente extraído del paper — eso
queda para revisión humana del primer batch (ver
`scripts/run_paper_digestion.py`).
"""

from __future__ import annotations

import json
from pathlib import Path

from sreg.inference.protocol import (
    FinishReason,
    Message,
    MessageRole,
    ModelClient,
    ToolSpec,
)
from sreg.v1_5.contracts import PaperInsights

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_SYSTEM_PROMPT_FILE = _PROMPTS_DIR / "paper_digestion.md"

_TOOL_NAME = "emit_paper_insights"


class PaperDigestionError(RuntimeError):
    """Algo salió mal en la digestión: el LLM no llamó al tool, o el tool
    devolvió argumentos que no validan contra el schema."""


class PaperDigestionAgent:
    """Agente Paper Digestion.

    Uso típico::

        client = OpenAIClient()
        agent = PaperDigestionAgent(client)
        insights = agent.digest(paper_text="...", paper_id="seed_001")
    """

    def __init__(
        self,
        client: ModelClient,
        *,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature
        self._system_prompt = _SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")

    def digest(self, *, paper_text: str, paper_id: str) -> PaperInsights:
        """Ejecuta la digestión y devuelve un `PaperInsights` validado.

        Args:
            paper_text: contenido del paper / seed (markdown o texto plano).
            paper_id: identificador (ej. nombre del archivo sin extensión).
        """
        if not paper_text.strip():
            raise PaperDigestionError("paper_text vacío")

        messages = [
            Message(role=MessageRole.SYSTEM, content=self._system_prompt),
            Message(
                role=MessageRole.USER,
                content=(
                    f"paper_id: {paper_id}\n\n---\n\n{paper_text.strip()}"
                ),
            ),
        ]

        tool = self._build_tool_spec()
        response = self._client.chat(
            messages=messages,
            tools=[tool],
            model=self._model,
            temperature=self._temperature,
        )

        if response.finish_reason != FinishReason.TOOL_CALLS:
            raise PaperDigestionError(
                f"El LLM no llamó al tool '{_TOOL_NAME}'. finish_reason="
                f"{response.finish_reason}, message="
                f"{(response.message.content or '')[:200]!r}"
            )

        # Buscar la llamada al tool correcto.
        matching = [tc for tc in response.tool_calls if tc.name == _TOOL_NAME]
        if not matching:
            raise PaperDigestionError(
                f"El LLM llamó tools que no coinciden con '{_TOOL_NAME}'. "
                f"Tools llamados: {[tc.name for tc in response.tool_calls]}."
            )
        if len(matching) > 1:
            # Edge case: si llama varias veces, tomamos la primera y avisamos.
            # Mantenerlo estricto por ahora (signal de prompt confuso).
            raise PaperDigestionError(
                f"El LLM llamó '{_TOOL_NAME}' {len(matching)} veces; "
                f"esperábamos una sola."
            )

        args = matching[0].arguments
        # Forzar que `paper_id` venga del caller, no del modelo.
        args = {**args, "paper_id": paper_id}

        try:
            insights = PaperInsights.model_validate(args)
        except Exception as exc:
            raise PaperDigestionError(
                f"Los argumentos del tool no validan contra `PaperInsights`: "
                f"{exc}\nArgumentos crudos: "
                f"{json.dumps(args, indent=2, default=str, ensure_ascii=False)[:1500]}"
            ) from exc

        return insights

    # -- internals ----------------------------------------------------

    @staticmethod
    def _build_tool_spec() -> ToolSpec:
        """Construye el `ToolSpec` desde el schema JSON de `PaperInsights`.

        Usamos `model_json_schema()` para no mantener dos fuentes de verdad.
        Si en el futuro el schema queda muy anidado y los modelos se
        confunden, simplificamos acá (y no en el contrato Pydantic).
        """
        schema = PaperInsights.model_json_schema()
        return ToolSpec(
            name=_TOOL_NAME,
            description=(
                "Emit the structured PaperInsights extracted from the source "
                "paper. Call exactly once. paper_id will be overwritten by "
                "the caller, but include it as a placeholder."
            ),
            parameters=schema,
        )


__all__ = ["PaperDigestionAgent", "PaperDigestionError"]
