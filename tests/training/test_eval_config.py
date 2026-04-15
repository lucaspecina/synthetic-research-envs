"""Tests for sreg.training.eval_config.

The resolver carries the risky invariant: `api_key_var` must point at an
env var that actually holds a value. Otherwise verifiers.ClientConfig
reads a missing key at rollout time and rollouts fail silently with
opaque auth errors.
"""

from __future__ import annotations

import pytest

from sreg.training.eval_config import RoleConfig, resolve_role_config


# Minimal "everything on Azure" env (smoke-test default path).
AZURE_ENV = {
    "AZURE_FOUNDRY_BASE_URL": "https://azure.example.com/openai",
    "AZURE_MODEL": "gpt-5.4",
    "AZURE_INFERENCE_CREDENTIAL": "azure-key-123",
}


def test_defaults_to_azure_env_for_both_roles():
    """With only AZURE_* set, both roles resolve to the Azure endpoint."""
    policy = resolve_role_config("policy", env=AZURE_ENV)
    scorer = resolve_role_config("scorer", env=AZURE_ENV)

    assert policy.base_url == "https://azure.example.com/openai"
    assert policy.model == "gpt-5.4"
    assert policy.api_key_var == "AZURE_INFERENCE_CREDENTIAL"
    assert policy.api_key == "azure-key-123"
    assert scorer == policy  # same env, same output


def test_role_prefixed_env_overrides_azure_fallback():
    """POLICY_* env vars take precedence over AZURE_* fallback."""
    env = {
        **AZURE_ENV,
        "POLICY_BASE_URL": "http://localhost:8000/v1",
        "POLICY_MODEL": "Qwen/Qwen3-8B",
        "POLICY_API_KEY": "vllm-local-key",
    }
    policy = resolve_role_config("policy", env=env)
    scorer = resolve_role_config("scorer", env=env)

    assert policy.base_url == "http://localhost:8000/v1"
    assert policy.model == "Qwen/Qwen3-8B"
    assert policy.api_key_var == "POLICY_API_KEY"
    assert policy.api_key == "vllm-local-key"

    # Scorer is untouched — still on Azure.
    assert scorer.base_url == "https://azure.example.com/openai"
    assert scorer.api_key_var == "AZURE_INFERENCE_CREDENTIAL"


def test_cli_flags_override_env():
    """Explicit CLI overrides beat both role-prefixed and Azure env."""
    env = {
        **AZURE_ENV,
        "POLICY_BASE_URL": "http://from-env:8000/v1",
        "POLICY_MODEL": "env-model",
        "CUSTOM_KEY_VAR": "from-cli-key",
    }
    policy = resolve_role_config(
        "policy",
        cli_base_url="http://from-cli:9000/v1",
        cli_model="cli-model",
        cli_api_key_var="CUSTOM_KEY_VAR",
        env=env,
    )

    assert policy.base_url == "http://from-cli:9000/v1"
    assert policy.model == "cli-model"
    assert policy.api_key_var == "CUSTOM_KEY_VAR"
    assert policy.api_key == "from-cli-key"


def test_cli_api_key_var_missing_from_env_raises():
    """If --policy-api-key-var names an env var that doesn't exist, fail loud."""
    with pytest.raises(ValueError, match="no such key"):
        resolve_role_config(
            "policy",
            cli_api_key_var="NONEXISTENT_VAR",
            env=AZURE_ENV,
        )


def test_missing_base_url_raises():
    env = {k: v for k, v in AZURE_ENV.items() if k != "AZURE_FOUNDRY_BASE_URL"}
    with pytest.raises(ValueError, match="No base URL"):
        resolve_role_config("policy", env=env)


def test_missing_model_raises():
    env = {k: v for k, v in AZURE_ENV.items() if k != "AZURE_MODEL"}
    with pytest.raises(ValueError, match="No model"):
        resolve_role_config("policy", env=env)


def test_missing_api_key_raises():
    env = {k: v for k, v in AZURE_ENV.items() if k != "AZURE_INFERENCE_CREDENTIAL"}
    with pytest.raises(ValueError, match="No API key"):
        resolve_role_config("policy", env=env)


def test_empty_api_key_raises():
    """Env var exists but empty string → still a failure."""
    env = {**AZURE_ENV, "AZURE_INFERENCE_CREDENTIAL": ""}
    with pytest.raises(ValueError, match="No API key"):
        resolve_role_config("policy", env=env)


def test_invalid_role_raises():
    with pytest.raises(ValueError, match="must be 'policy' or 'scorer'"):
        resolve_role_config("bogus", env=AZURE_ENV)


def test_api_key_var_invariant_holds():
    """env[api_key_var] must equal api_key for every resolution path.

    Verifiers.ClientConfig(api_key_var=...) reads from env at rollout time.
    If api_key_var points at a different (or empty) env var than the one
    we resolved, rollouts fail with opaque auth errors.
    """
    scenarios = [
        # Azure-only (fallback path)
        AZURE_ENV,
        # Role-prefixed override
        {**AZURE_ENV, "POLICY_API_KEY": "policy-key", "POLICY_BASE_URL": "http://x", "POLICY_MODEL": "m"},
        # Mixed: policy has ROLE_*, scorer falls back
        {**AZURE_ENV, "POLICY_API_KEY": "pk", "POLICY_BASE_URL": "http://x", "POLICY_MODEL": "m"},
    ]
    for env in scenarios:
        for role in ("policy", "scorer"):
            cfg = resolve_role_config(role, env=env)
            assert env[cfg.api_key_var] == cfg.api_key, (
                f"Invariant violation for role={role}, env={env}: "
                f"api_key_var={cfg.api_key_var} but key mismatch."
            )


def test_roleconfig_is_frozen():
    """RoleConfig is frozen — prevents accidental mutation after resolution."""
    cfg = resolve_role_config("policy", env=AZURE_ENV)
    with pytest.raises(Exception):  # FrozenInstanceError in py3.11+
        cfg.base_url = "mutated"  # type: ignore[misc]
    # Still the original value
    assert cfg.base_url == "https://azure.example.com/openai"
