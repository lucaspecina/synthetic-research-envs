"""Agente World Architect: `PaperInsights` → `WorldSpec` ejecutable.

El Architect lee la digestión estructurada de un paper (mecanismos,
phenomena, complications, plus contexto de dominio) y produce un SCM
que **materializa** esos mecanismos en un mundo ejecutable.

Implementación:
- function calling sobre `ModelClient` v1.
- Schema **simplificado** (`ArchitectWorldDraft`) en la frontera con el
  LLM (Codex 2026-05-05: el JSON schema de `WorldSpec` directo es
  frágil por `edges: list[tuple]`). Conversor determinista en
  `architect_draft.to_world_spec`.
- **Single retry** tras error determinista (Pydantic / `compile_scm` /
  sampling). Sin retries por intuición.

El Architect NO recibe:
- El paper crudo (ya digerido).
- `narrative_capsule.forbidden_phrases` (anti-leak es para downstream).

El Architect SÍ recibe:
- `PaperInsights.mechanisms / phenomena / complications /
  counterintuitive_priors / realism_bounds`.
- Subset del `narrative_capsule`: `domain`, `population`, `units`,
  `measurement_conventions`. Útiles para nombres realistas y rangos.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from sreg.inference.protocol import (
    FinishReason,
    Message,
    MessageRole,
    ModelClient,
    ToolSpec,
)
from sreg.v1_5.agents.architect_draft import (
    ArchitectWorldDraft,
    to_world_spec,
)
from sreg.v1_5.contracts import PaperInsights, WorldSpec
from sreg.v1_5.environment import SCMEnvironmentAdapter
from sreg.v1_5.world import compile_scm

# Lint de soporte plausible: tolerancia max de samples fuera de rango.
_PLAUSIBLE_TOLERANCE = 0.01  # 1%
_PLAUSIBLE_LINT_N = 500
_PLAUSIBLE_LINT_SEED = 7

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_SYSTEM_PROMPT_FILE = _PROMPTS_DIR / "architect.md"

_TOOL_NAME = "emit_world_draft"


class ArchitectError(RuntimeError):
    """El Architect no logró producir un `WorldSpec` ejecutable."""


class ArchitectAgent:
    """Agente World Architect.

    Uso típico::

        client = OpenAIClient()
        agent = ArchitectAgent(client)
        world = agent.design(insights=paper_insights)
    """

    def __init__(
        self,
        client: ModelClient,
        *,
        model: str | None = None,
        temperature: float = 0.3,
    ) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature
        self._system_prompt = _SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")

    def design(self, *, insights: PaperInsights) -> WorldSpec:
        """Genera un `WorldSpec` SCM ejecutable a partir de los insights.

        Estrategia: 1 intento + 1 retry con feedback. Si ambos fallan,
        levanta `ArchitectError` con detalles.
        """
        user_msg = _build_user_message(insights)
        tool = self._build_tool_spec()
        messages = [
            Message(role=MessageRole.SYSTEM, content=self._system_prompt),
            Message(role=MessageRole.USER, content=user_msg),
        ]

        # Primer intento.
        try:
            return self._design_once(messages, tool)
        except ArchitectError as first_err:
            # Single retry con el error como feedback (sin loop infinito).
            retry_msg = (
                "Your previous output failed validation. Read the error "
                "carefully, identify which discipline rule it violated, "
                "and emit a corrected `emit_world_draft` call. Do NOT "
                "repeat the same mistake.\n\n"
                f"ERROR:\n{first_err}"
            )
            messages_retry = list(messages) + [
                Message(role=MessageRole.USER, content=retry_msg),
            ]
            try:
                return self._design_once(messages_retry, tool)
            except ArchitectError as second_err:
                raise ArchitectError(
                    f"Architect failed twice. First attempt: {first_err}. "
                    f"Retry: {second_err}"
                ) from second_err

    # -- internals ----------------------------------------------------

    def _design_once(
        self, messages: list[Message], tool: ToolSpec
    ) -> WorldSpec:
        """Hace una llamada al LLM y valida el output deterministamente.

        Errores deterministas que rebotan a `ArchitectError`:
        - LLM no llamó al tool / tool incorrecto / múltiples llamadas.
        - args no validan contra `ArchitectWorldDraft` (Pydantic).
        - conversor `to_world_spec` falla (Pydantic en `WorldSpec`).
        - `compile_scm` falla (DAG, edges↔equations, sampling).
        """
        response = self._client.chat(
            messages=messages,
            tools=[tool],
            model=self._model,
            temperature=self._temperature,
        )

        if response.finish_reason != FinishReason.TOOL_CALLS:
            raise ArchitectError(
                f"El LLM no llamó al tool '{_TOOL_NAME}'. finish_reason="
                f"{response.finish_reason}, message="
                f"{(response.message.content or '')[:300]!r}"
            )

        matching = [tc for tc in response.tool_calls if tc.name == _TOOL_NAME]
        if not matching:
            raise ArchitectError(
                f"El LLM llamó tools que no son '{_TOOL_NAME}'. "
                f"Tools llamados: {[tc.name for tc in response.tool_calls]}."
            )
        if len(matching) > 1:
            raise ArchitectError(
                f"El LLM llamó '{_TOOL_NAME}' {len(matching)} veces; "
                f"se esperaba una sola."
            )

        args = matching[0].arguments

        # Paso 1: validar el draft contra el schema simplificado.
        try:
            draft = ArchitectWorldDraft.model_validate(args)
        except ValidationError as exc:
            raise ArchitectError(
                f"ArchitectWorldDraft no valida contra el schema. {exc}\n"
                f"args crudo (truncado): "
                f"{json.dumps(args, indent=2, default=str, ensure_ascii=False)[:1500]}"
            ) from exc

        # Paso 2: convertir a WorldSpec real (puede fallar en validators de WorldSpec).
        try:
            world = to_world_spec(draft)
        except ValidationError as exc:
            raise ArchitectError(
                f"to_world_spec falló: el draft cumple el schema "
                f"simplificado pero rompe validators de WorldSpec. {exc}"
            ) from exc

        # Paso 3: compilar (DAG, edges↔equations, lints, sampling de validación).
        try:
            scm = compile_scm(world)
        except Exception as exc:
            raise ArchitectError(
                f"compile_scm falló sobre el WorldSpec emitido: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        # Paso 4: lint de soporte plausible (si el LLM declaró rangos).
        _check_plausible_supports(draft, scm)

        return world

    @staticmethod
    def _build_tool_spec() -> ToolSpec:
        """Tool spec con el JSON schema simplificado del draft."""
        schema = ArchitectWorldDraft.model_json_schema()
        return ToolSpec(
            name=_TOOL_NAME,
            description=(
                "Emit the SCM world draft (variables, edges, intended "
                "phenomena) that materializes the mechanisms from "
                "PaperInsights. Call exactly once."
            ),
            parameters=schema,
        )


def _check_plausible_supports(draft: ArchitectWorldDraft, scm) -> None:
    """Lint determinista: el sample debe respetar los `plausible_min/max`
    que declaró el Architect.

    Recibe el `scm` ya compilado y samplea N=500 filas con seed fijo.
    Para cada variable con `plausible_min` o `plausible_max` declarado,
    chequea que >= 99% de los samples caigan dentro del rango.

    Variables sin rangos declarados: ignoradas (el Architect declara
    rangos solo para variables continuas / count típicamente).

    Raises:
        ArchitectError con la lista de violaciones si las hay.
    """
    vars_with_ranges = [
        v for v in draft.variables
        if v.plausible_min is not None or v.plausible_max is not None
    ]
    if not vars_with_ranges:
        return

    env = SCMEnvironmentAdapter(scm)
    df = env.observe(
        n=_PLAUSIBLE_LINT_N,
        columns=env.variables,  # incluye latentes para validar
        seed=_PLAUSIBLE_LINT_SEED,
    )

    violations: list[str] = []
    for v in vars_with_ranges:
        if v.name not in df.columns:
            continue
        col = df[v.name]
        out_of_range = 0
        if v.plausible_min is not None:
            out_of_range += int((col < v.plausible_min).sum())
        if v.plausible_max is not None:
            out_of_range += int((col > v.plausible_max).sum())
        frac = out_of_range / _PLAUSIBLE_LINT_N
        if frac > _PLAUSIBLE_TOLERANCE:
            violations.append(
                f"  - '{v.name}': {out_of_range}/{_PLAUSIBLE_LINT_N} "
                f"({frac:.1%}) samples out of "
                f"[{v.plausible_min}, {v.plausible_max}]. "
                f"observed range=[{col.min():.3f}, {col.max():.3f}]"
            )

    if violations:
        raise ArchitectError(
            "Plausible support lint failed (>1% of samples outside "
            "declared plausible range):\n" + "\n".join(violations) +
            "\n\nFix: tighten the equation parameters (smaller noise, "
            "different intercept), use clipping (e.g. "
            "`max(0, min(120, ...))`), or relax `plausible_min/max` if "
            "the wider range is actually realistic."
        )


def _build_user_message(insights: PaperInsights) -> str:
    """Arma el user message que ve el Architect.

    Incluye:
    - paper_id (referencia, no leak).
    - mechanisms / phenomena / complications / counterintuitive_priors /
      realism_bounds.
    - Subset SEGURO del narrative_capsule: domain / population / units /
      measurement_conventions. NO forbidden_phrases (Codex: anti-leak es
      para downstream, no para Architect).
    """
    capsule = insights.narrative_capsule
    safe_capsule = {
        "domain": capsule.domain,
        "population": capsule.population,
        "units": capsule.units,
        "measurement_conventions": capsule.measurement_conventions,
    }

    payload = {
        "paper_id": insights.paper_id,
        "objective": insights.objective,
        "entities": insights.entities,
        "mechanisms": insights.mechanisms,
        "phenomena": insights.phenomena,
        "complications": insights.complications,
        "counterintuitive_priors": insights.counterintuitive_priors,
        "realism_bounds": insights.realism_bounds,
        "domain_context": safe_capsule,
    }
    return (
        "Build the SCM. Paper digest:\n"
        f"{json.dumps(payload, indent=2, ensure_ascii=False)}"
    )


__all__ = ["ArchitectAgent", "ArchitectError"]
