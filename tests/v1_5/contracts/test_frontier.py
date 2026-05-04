"""CP0a + CP0b — frontera público/oculto del ResearchCase.

`ResearchCase` es lo único que ve el Investigator. NO puede contener
`GoldQuestion`, `Rubric`, `AnswerKey`, `WorldSpec`, `ValidationReport`,
ni ningún otro campo del lado oculto.

- **CP0a**: `model_dump()` y `model_dump_json()` NO exponen campos restringidos.
- **CP0b**: `extra="forbid"` rebota cualquier intento de inyección.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from sreg.v1_5.contracts import ResearchCase

# Campos del lado OCULTO que NUNCA deben aparecer en ResearchCase.
FORBIDDEN_FIELDS = [
    "questions",
    "questions_bundle",
    "gold_questions",
    "gold_question",
    "rubric",
    "rubrics",
    "answer_key",
    "answer_keys",
    "world_spec",
    "world_model",
    "world",
    "validation_report",
    "validation",
    "phenomena",
    "phenomena_manifest",
]


# ---------------------------------------------------------------------------
# CP0a — model_dump no expone campos restringidos
# ---------------------------------------------------------------------------


def test_cp0a_model_dump_does_not_leak(research_case: ResearchCase) -> None:
    dumped = research_case.model_dump()
    leaked = set(FORBIDDEN_FIELDS) & set(dumped.keys())
    assert not leaked, (
        f"ResearchCase.model_dump() filtra campos restringidos: {leaked}. "
        "Frontera público/oculto rota."
    )


def test_cp0a_model_dump_json_does_not_leak(research_case: ResearchCase) -> None:
    parsed = json.loads(research_case.model_dump_json())
    leaked = set(FORBIDDEN_FIELDS) & set(parsed.keys())
    assert not leaked, (
        f"ResearchCase.model_dump_json() filtra campos restringidos: {leaked}. "
        "Frontera público/oculto rota."
    )


def test_cp0a_dump_contains_only_public_fields(research_case: ResearchCase) -> None:
    """Verificación inversa: el dump SOLO contiene los 5 campos públicos esperados."""
    expected_public = {"case_id", "brief", "context", "datasets", "tools"}
    dumped = research_case.model_dump()
    assert set(dumped.keys()) == expected_public, (
        f"Campos en ResearchCase.model_dump() difieren de los esperados. "
        f"Esperado: {expected_public}. Got: {set(dumped.keys())}."
    )


# ---------------------------------------------------------------------------
# CP0b — extra="forbid" rebota inyección de campos restringidos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("forbidden_field", FORBIDDEN_FIELDS)
def test_cp0b_research_case_rejects_forbidden_field(
    forbidden_field: str, research_case: ResearchCase
) -> None:
    base = research_case.model_dump()
    base[forbidden_field] = "intento de inyección"
    with pytest.raises(ValidationError) as exc_info:
        ResearchCase(**base)
    # El error debe mencionar el campo (extra forbidden).
    assert "Extra inputs are not permitted" in str(
        exc_info.value
    ) or forbidden_field in str(exc_info.value), (
        f"ResearchCase no rechazó el campo prohibido '{forbidden_field}' "
        f"de la forma esperada. Error: {exc_info.value}"
    )


def test_cp0b_unknown_extra_field_is_rejected(research_case: ResearchCase) -> None:
    """Cualquier campo desconocido (no solo los listados) debe rebotar."""
    base = research_case.model_dump()
    base["totally_made_up_field"] = 42
    with pytest.raises(ValidationError):
        ResearchCase(**base)


# ---------------------------------------------------------------------------
# Bonus: leak transitivo — walk recursivo sobre el dump completo.
# Ningún forbidden key debe aparecer en ningún nivel del JSON resultante.
# ---------------------------------------------------------------------------


def test_no_forbidden_keys_anywhere_in_dump(research_case: ResearchCase) -> None:
    """Walk recursivo: ningún forbidden key como CLAVE en ningún nivel.

    Esto cubre leak transitivo: por ejemplo, si en el futuro alguien
    agrega un sub-modelo a `Dataset` o `ToolSpec` que accidentalmente
    expone campos del lado oculto, este test lo detecta.
    """
    dumped = research_case.model_dump()
    forbidden_lower = {f.lower() for f in FORBIDDEN_FIELDS}

    def walk(obj, path: str = "$") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                key_path = f"{path}.{k}"
                assert k.lower() not in forbidden_lower, (
                    f"Forbidden key '{k}' apareció en path '{key_path}'. "
                    "Leak transitivo de la frontera público/oculto."
                )
                walk(v, key_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                walk(item, f"{path}[{i}]")

    walk(dumped)
