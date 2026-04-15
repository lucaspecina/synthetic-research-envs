"""Config resolution for the eval/training harness.

Separates the policy LLM (the model being trained/evaluated, typically a
local vLLM server on H100) from the scorer LLM (the LLM used by the OI
scoring pipeline for compiling claims and judging relevance, typically
Azure). Before this split, both roles read the same AZURE_* env vars, so
pointing the policy at a local server was impossible.

Precedence (highest -> lowest):
  1. Explicit CLI flag (`--policy-base-url`, `--scorer-model`, etc).
  2. Role-prefixed env var (`POLICY_BASE_URL`, `SCORER_MODEL`).
  3. Legacy Azure env vars (`AZURE_FOUNDRY_BASE_URL`, `AZURE_MODEL`,
     `AZURE_INFERENCE_CREDENTIAL`) — keeps the "everything on Azure"
     smoke-test flow working without touching env setup.

The api_key_var returned always points at a populated env entry so
verifiers.ClientConfig(api_key_var=...) reads a real value. Callers that
need the key directly (e.g. OpenAI client for the scorer Responses API)
get it on `RoleConfig.api_key`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class RoleConfig:
    """Resolved configuration for a single LLM role (policy or scorer).

    Attributes:
        base_url: API base URL (e.g., https://.../openai).
        api_key: Actual API key value (already resolved from env).
        api_key_var: Env var name that holds `api_key`. Used by
            verifiers.ClientConfig(api_key_var=...) which reads env
            internally. Invariant: env[api_key_var] == api_key.
        model: Model identifier (e.g., "gpt-5.4", "Qwen/Qwen3-8B").
    """

    base_url: str
    api_key: str
    api_key_var: str
    model: str


def resolve_role_config(
    role: str,
    *,
    cli_base_url: str | None = None,
    cli_model: str | None = None,
    cli_api_key_var: str | None = None,
    env: Mapping[str, str] | None = None,
) -> RoleConfig:
    """Resolve LLM role config from CLI flags with env fallback.

    Args:
        role: "policy" or "scorer". Determines the env var prefix.
        cli_base_url: CLI override for base URL (e.g., from --policy-base-url).
        cli_model: CLI override for model.
        cli_api_key_var: CLI override for env var NAME holding the API key.
        env: Mapping to resolve env vars from. Defaults to os.environ.

    Raises:
        ValueError: If role is not "policy" or "scorer", or if any field
            cannot be resolved from CLI, role-prefixed env, or AZURE_* fallback.
    """
    if role not in ("policy", "scorer"):
        raise ValueError(f"role must be 'policy' or 'scorer', got {role!r}")

    env = env if env is not None else os.environ
    prefix = role.upper() + "_"

    # Base URL: CLI > ROLE_BASE_URL > AZURE_FOUNDRY_BASE_URL
    base_url = (
        cli_base_url
        or env.get(prefix + "BASE_URL")
        or env.get("AZURE_FOUNDRY_BASE_URL")
    )
    if not base_url:
        raise ValueError(
            f"No base URL for role {role}. Set --{role}-base-url, "
            f"{prefix}BASE_URL, or AZURE_FOUNDRY_BASE_URL."
        )

    # Model: CLI > ROLE_MODEL > AZURE_MODEL
    model = cli_model or env.get(prefix + "MODEL") or env.get("AZURE_MODEL")
    if not model:
        raise ValueError(
            f"No model for role {role}. Set --{role}-model, "
            f"{prefix}MODEL, or AZURE_MODEL."
        )

    # API key var: CLI > ROLE_API_KEY (if set) > AZURE_INFERENCE_CREDENTIAL.
    # We resolve the VAR NAME to one that has a real value, so downstream
    # consumers (verifiers.ClientConfig, direct env lookup) both work.
    if cli_api_key_var:
        api_key_var = cli_api_key_var
        if api_key_var not in env:
            raise ValueError(
                f"--{role}-api-key-var={api_key_var} but env has no such key."
            )
    elif env.get(prefix + "API_KEY"):
        api_key_var = prefix + "API_KEY"
    elif env.get("AZURE_INFERENCE_CREDENTIAL"):
        api_key_var = "AZURE_INFERENCE_CREDENTIAL"
    else:
        raise ValueError(
            f"No API key for role {role}. Set {prefix}API_KEY, "
            f"AZURE_INFERENCE_CREDENTIAL, or --{role}-api-key-var."
        )

    api_key = env[api_key_var]
    if not api_key:
        raise ValueError(
            f"Env var {api_key_var} exists but is empty for role {role}."
        )

    return RoleConfig(
        base_url=base_url,
        api_key=api_key,
        api_key_var=api_key_var,
        model=model,
    )


__all__ = ["RoleConfig", "resolve_role_config"]
