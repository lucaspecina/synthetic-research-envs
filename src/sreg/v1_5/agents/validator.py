"""Agente Validator: prueba empíricamente un `IntendedPhenomenon` contra el mundo.

Recibe un `IntendedPhenomenon` declarado por el Architect + un
`SCMEnvironment` compilado, y devuelve un `ValidatorVote` con vote /
margin / fragility / evidence ejecutable.

El LLM escribe scripts Python libres contra el Environment (vía
`python_exec`), inspecciona outputs, decide si el fenómeno se
manifiesta, y emite el voto vía la function call `emit_validator_vote`.

Diseño explícito (post Ronda 15 + Codex review):
- Scripts Python libres: NO hay DSL intermedia, NO `tests[]/perturbations[]`.
  El LLM resuelve cada fenómeno con el método que corresponda.
- `margin / fragility` son autoevaluación gruesa del LLM (señales para el
  Architect, no medición determinista). El doc + contratos NO especifican
  semántica determinista, y agregarla requeriría infraestructura nueva.
- `delta_from_previous` se computa determinista en el wrapper, comparando
  los campos canónicos del `ValidatorVote` (margin, fragility, vote). NO
  se lo damos al LLM, NO lo computa el Architect (rompería disciplina de
  votos inmutables).
- Reuso de `ToolEnrichedClient` para el loop multi-turn de python_exec.
- Reuso de `make_python_namespace(extras={"env": env})` para inyectar el
  Environment.

Single retry con error feedback (mismo patrón que `ArchitectAgent`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from sreg.agent.python_exec import make_python_namespace
from sreg.inference.protocol import (
    FinishReason,
    Message,
    MessageRole,
    ModelClient,
    ToolSpec,
)
from sreg.inference.tool_client import ToolEnrichedClient
from sreg.v1_5.contracts import (
    EvidenceArtifact,
    IntendedPhenomenon,
    ValidatorVote,
    WorldSpec,
)
from sreg.v1_5.environment.protocols import SCMEnvironment

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_SYSTEM_PROMPT_FILE = _PROMPTS_DIR / "validator.md"

_TOOL_NAME = "emit_validator_vote"

_DEFAULT_MAX_ITERATIONS = 15


class ValidatorError(RuntimeError):
    """El Validator no logró producir un `ValidatorVote` válido."""


class ValidatorVoteDraft(BaseModel):
    """Schema simplificado emitido por el LLM.

    Solo contiene los campos que el LLM decide. Los campos administrados
    por el sistema (`validator_id`, `target_intended_id`, `iteration`,
    `delta_from_previous`) se agregan en el wrapper antes de validar
    contra `ValidatorVote` real.
    """

    model_config = ConfigDict(extra="forbid")

    vote: Literal["passes", "weak_pass", "fails"]
    margin: float = Field(ge=0.0, le=1.0)
    fragility: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceArtifact] = Field(min_length=1)
    failure_reason: str | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_failure_reason_consistency(self) -> "ValidatorVoteDraft":
        # Reglas alineadas con `ValidatorVote._check_consistency` para
        # rechazar drafts inconsistentes lo antes posible (antes del retry).
        if self.vote != "passes" and self.failure_reason is None:
            raise ValueError(
                f"Draft con vote='{self.vote}' requiere `failure_reason`."
            )
        if self.vote == "passes" and self.failure_reason is not None:
            raise ValueError(
                "Draft con vote='passes' NO debe tener `failure_reason`."
            )
        return self


class ValidatorAgent:
    """Agente Validator para UN `IntendedPhenomenon`.

    Uso típico::

        client = OpenAIClient()
        agent = ValidatorAgent(client)
        vote = agent.validate(
            world=world_spec,
            env=scm_env,
            phenomenon=intended_phenomenon,
        )
    """

    def __init__(
        self,
        client: ModelClient,
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_iterations: int = _DEFAULT_MAX_ITERATIONS,
    ) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature
        self._max_iterations = max_iterations
        self._system_prompt = _SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")

    def validate(
        self,
        *,
        world: WorldSpec,
        env: SCMEnvironment,
        phenomenon: IntendedPhenomenon,
        iteration: int = 0,
        previous_vote: ValidatorVote | None = None,
        validator_id: str | None = None,
    ) -> ValidatorVote:
        """Corre el Validator sobre un fenómeno y devuelve el voto final.

        Estrategia: 1 intento + 1 retry con feedback. Si ambos fallan,
        levanta `ValidatorError`.

        Args:
            world: el `WorldSpec` ya construido por el Architect.
            env: `SCMEnvironment` compilado, expuesto como `env` al LLM.
            phenomenon: el `IntendedPhenomenon` a verificar.
            iteration: número de iteración del Architect (0-indexed).
            previous_vote: voto anterior del mismo fenómeno (si lo hay)
                para computar `delta_from_previous`.
            validator_id: ID descriptivo del validator. Si None, se
                genera como `f"validator_{phenomenon.id}_iter{iteration}"`.
        """
        if validator_id is None:
            validator_id = f"validator_{phenomenon.id}_iter{iteration}"
        if iteration == 0 and previous_vote is not None:
            raise ValidatorError(
                "iteration=0 NO puede tener previous_vote (no hay anterior)."
            )

        user_msg = _build_user_message(world, phenomenon)
        tool = self._build_tool_spec()
        tool_client = ToolEnrichedClient(
            base_client=self._client,
            max_iterations=self._max_iterations,
            namespace_factory=lambda: make_python_namespace(extras={"env": env}),
        )

        messages: list[Message] = [
            Message(role=MessageRole.SYSTEM, content=self._system_prompt),
            Message(role=MessageRole.USER, content=user_msg),
        ]

        delta = _compute_delta(previous_vote=previous_vote)

        # Primer intento.
        try:
            return self._validate_once(
                messages=messages,
                tool=tool,
                tool_client=tool_client,
                validator_id=validator_id,
                target_intended_id=phenomenon.id,
                iteration=iteration,
                delta_from_previous=delta,
            )
        except ValidatorError as first_err:
            retry_msg = (
                "Your previous output failed validation. Read the error "
                "carefully and emit a corrected `emit_validator_vote` "
                "call. Do NOT repeat the same mistake.\n\n"
                f"ERROR:\n{first_err}"
            )
            messages_retry = list(messages) + [
                Message(role=MessageRole.USER, content=retry_msg),
            ]
            try:
                return self._validate_once(
                    messages=messages_retry,
                    tool=tool,
                    tool_client=tool_client,
                    validator_id=validator_id,
                    target_intended_id=phenomenon.id,
                    iteration=iteration,
                    delta_from_previous=delta,
                )
            except ValidatorError as second_err:
                raise ValidatorError(
                    f"Validator failed twice. First attempt: {first_err}. "
                    f"Retry: {second_err}"
                ) from second_err

    # -- internals ----------------------------------------------------

    def _validate_once(
        self,
        *,
        messages: list[Message],
        tool: ToolSpec,
        tool_client: ToolEnrichedClient,
        validator_id: str,
        target_intended_id: str,
        iteration: int,
        delta_from_previous: dict[str, Any] | None,
    ) -> ValidatorVote:
        """Hace una corrida del loop y valida el output deterministamente."""
        response = tool_client.chat(
            messages=messages,
            tools=[tool],
            model=self._model,
            temperature=self._temperature,
        )

        if response.finish_reason != FinishReason.TOOL_CALLS:
            raise ValidatorError(
                f"El LLM no llamó al tool '{_TOOL_NAME}'. finish_reason="
                f"{response.finish_reason}, message="
                f"{(response.message.content or '')[:300]!r}"
            )

        matching = [tc for tc in response.tool_calls if tc.name == _TOOL_NAME]
        if not matching:
            raise ValidatorError(
                f"El LLM llamó tools que no son '{_TOOL_NAME}'. "
                f"Tools llamados: {[tc.name for tc in response.tool_calls]}."
            )
        if len(matching) > 1:
            raise ValidatorError(
                f"El LLM llamó '{_TOOL_NAME}' {len(matching)} veces; "
                f"se esperaba una sola."
            )

        args = matching[0].arguments

        # Validar contra el schema simplificado.
        try:
            draft = ValidatorVoteDraft.model_validate(args)
        except ValidationError as exc:
            raise ValidatorError(
                f"ValidatorVoteDraft no valida contra el schema. {exc}\n"
                f"args (truncado): "
                f"{json.dumps(args, indent=2, default=str, ensure_ascii=False)[:1500]}"
            ) from exc

        # Convertir a ValidatorVote real (agrega los campos administrados).
        try:
            return ValidatorVote(
                validator_id=validator_id,
                target_intended_id=target_intended_id,
                iteration=iteration,
                vote=draft.vote,
                margin=draft.margin,
                fragility=draft.fragility,
                delta_from_previous=delta_from_previous,
                evidence=draft.evidence,
                failure_reason=draft.failure_reason,
                diagnostics=draft.diagnostics,
            )
        except ValidationError as exc:
            raise ValidatorError(
                f"ValidatorVote validation falló al consolidar el draft. {exc}"
            ) from exc

    @staticmethod
    def _build_tool_spec() -> ToolSpec:
        """Tool spec con el JSON schema simplificado del draft."""
        schema = ValidatorVoteDraft.model_json_schema()
        return ToolSpec(
            name=_TOOL_NAME,
            description=(
                "Emit the final ValidatorVote for the intended phenomenon "
                "after investigating with python_exec. Call exactly once. "
                "Required: vote, margin, fragility, evidence (at least 1 "
                "EvidenceArtifact). failure_reason mandatory if vote != "
                "'passes'."
            ),
            parameters=schema,
        )


def _compute_delta(
    *, previous_vote: ValidatorVote | None
) -> dict[str, Any] | None:
    """Computa `delta_from_previous` deterministicamente.

    Compara los campos canónicos del `ValidatorVote` (no keys arbitrarias
    de `numerical_result`). El delta se decide al emitir el voto nuevo, NO
    en el LLM.

    Devuelve None si no hay voto previo (iteration=0).
    """
    if previous_vote is None:
        return None
    return {
        "previous_vote": previous_vote.vote,
        "previous_margin": previous_vote.margin,
        "previous_fragility": previous_vote.fragility,
    }


def _build_user_message(
    world: WorldSpec, phenomenon: IntendedPhenomenon
) -> str:
    """Arma el user message que ve el Validator.

    Incluye:
    - Datos del fenómeno a verificar (kind, description, relevant_variables).
    - Lista de variables del mundo (observables y latentes) para que el
      LLM sepa qué puede pedirle a `env`.
    - Recordatorio operativo de cómo se llama al tool emit_validator_vote.
    """
    observable = [v.name for v in world.variables if v.is_observable]
    latent = [v.name for v in world.variables if not v.is_observable]

    payload = {
        "phenomenon_to_verify": {
            "id": phenomenon.id,
            "kind": phenomenon.kind,
            "description": phenomenon.description,
            "relevant_variables": phenomenon.relevant_variables,
        },
        "world": {
            "formalism": world.formalism,
            "domain": world.metadata.domain,
            "observable_variables": observable,
            "latent_variables": latent,
        },
    }

    return (
        "Validate the intended phenomenon below. Investigate using "
        "python_exec against `env`. When done, emit "
        f"`{_TOOL_NAME}` once with your final vote.\n\n"
        f"{json.dumps(payload, indent=2, ensure_ascii=False)}"
    )


__all__ = [
    "ValidatorAgent",
    "ValidatorError",
    "ValidatorVoteDraft",
]
