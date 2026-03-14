"""Validation logic for submit payloads by eval type."""

from __future__ import annotations

from sreg.training.types import (
    CHOICE_EVAL_TYPES,
    DISTRIBUTION_EVAL_TYPES,
    SET_EVAL_TYPES,
    SubmitPayload,
)


def validate_submit_payload(payload: SubmitPayload, eval_type: str) -> None:
    """Validate that the submit payload matches the expected format for the eval type.

    Raises ValueError with a descriptive message if validation fails.
    """
    populated = sum(
        v is not None for v in (payload.choice, payload.distribution, payload.adjustment_set)
    )
    if populated == 0:
        raise ValueError(
            "Submit payload is empty. Provide exactly one of: "
            "choice, distribution, or adjustment_set."
        )
    if populated > 1:
        raise ValueError(
            "Submit payload has multiple fields populated. "
            "Provide exactly one of: choice, distribution, or adjustment_set."
        )

    if eval_type in DISTRIBUTION_EVAL_TYPES:
        if payload.distribution is None:
            raise ValueError(
                f"Eval type '{eval_type}' requires a 'distribution' "
                f"(dict of state -> probability), got {_populated_field(payload)}."
            )
        _validate_distribution(payload.distribution)

    elif eval_type in CHOICE_EVAL_TYPES:
        if payload.choice is None:
            raise ValueError(
                f"Eval type '{eval_type}' requires a 'choice' (string), "
                f"got {_populated_field(payload)}."
            )

    elif eval_type in SET_EVAL_TYPES:
        if payload.adjustment_set is None:
            raise ValueError(
                f"Eval type '{eval_type}' requires an 'adjustment_set' (list of strings), "
                f"got {_populated_field(payload)}."
            )

    else:
        raise ValueError(f"Unknown eval type: '{eval_type}'")


def _validate_distribution(dist: dict[str, float]) -> None:
    """Basic sanity checks on a probability distribution."""
    if not dist:
        raise ValueError("Distribution is empty.")
    for key, val in dist.items():
        if not isinstance(val, (int, float)):
            raise ValueError(f"Distribution value for '{key}' is not numeric: {val}")
        if val < 0:
            raise ValueError(f"Distribution value for '{key}' is negative: {val}")
    total = sum(dist.values())
    if abs(total - 1.0) > 0.05:
        raise ValueError(f"Distribution sums to {total:.4f}, expected ~1.0.")


def _populated_field(payload: SubmitPayload) -> str:
    """Return the name of the populated field for error messages."""
    if payload.choice is not None:
        return "choice"
    if payload.distribution is not None:
        return "distribution"
    if payload.adjustment_set is not None:
        return "adjustment_set"
    return "none"
