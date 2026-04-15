#!/usr/bin/env python3
"""GRPO training harness for SregEnv — config-driven, dry-run aware.

Two modes:
    --dry-run   Validate config + run 1 rollout end-to-end with the
                configured env / dataset / policy / scorer. No gradients,
                no verifiers-rl required. This is the gate BEFORE paying
                for a real training run: if the wiring is broken, it
                surfaces here in ~3 min instead of 30 hours into a job.

    --train     Actual GRPO training loop. Requires verifiers-rl
                (Linux + CUDA). Currently a scaffold that raises
                NotImplementedError — the loop lands once the `rl`
                extra is defined and a Qwen3-8B LoRA config is wired.

Config:
    configs/smoke_rl.yaml (or whatever path is passed via --config)
    See src/sreg/training/train_config.py for the accepted schema.

Usage:
    # Windows dev / Azure scorer smoke
    export SREG_P05_BATCH="/path/to/results/p05_canonical_batch"
    python scripts/train_sreg.py --config configs/smoke_rl.yaml --dry-run

    # H100 smoke — policy on local vLLM, scorer on Azure
    python scripts/train_sreg.py --config configs/smoke_rl.yaml --dry-run \\
        --policy-base-url http://localhost:8000/v1 \\
        --policy-model Qwen/Qwen3-8B \\
        --policy-api-key-var VLLM_API_KEY

    # H100 real training (pending verifiers-rl)
    python scripts/train_sreg.py --config configs/smoke_rl.yaml --train
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Path bootstrap (must come before sreg imports)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

# Windows compat: prime_tunnel needs fcntl. Must be called before any
# verifiers import.
from sreg.training._compat import patch_fcntl_if_windows  # noqa: E402

patch_fcntl_if_windows()

from sreg.training import (  # noqa: E402
    RoleConfig,
    SregEnv,
    build_dataset,
    load_config,
    load_srcs,
    resolve_role_config,
    validate_config,
)


def _build_scorer_llm(cfg: RoleConfig):
    """Sync LLM callback for the OI scoring pipeline (compiler + judge)."""
    from openai import OpenAI

    client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key)

    def llm_call(messages):
        instructions = messages[0]["content"] if messages else ""
        input_items = [
            {"role": m["role"], "content": m["content"]}
            for m in messages[1:]
        ]
        resp = client.responses.create(
            model=cfg.model, instructions=instructions, input=input_items,
        )
        for item in resp.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        return part.text
        return ""

    return llm_call


def _build_policy_client(cfg: RoleConfig):
    """Build the policy client for verifiers rollouts (chat completions)."""
    import verifiers as vf

    config = vf.ClientConfig(
        api_base_url=cfg.base_url,
        api_key_var=cfg.api_key_var,
        client_type="openai_chat_completions",
        timeout=600.0,
        max_retries=2,
    )
    return vf.OpenAIChatCompletionsClient(config), cfg.model


def _build_env_and_dataset(cfg: dict, scorer_cfg: RoleConfig):
    """Load + filter train SRCs, build HF Dataset, build SregEnv.

    Holdout cases are deliberately NOT included in the training dataset —
    they exist to catch overfitting during eval passes, not as training
    inputs.
    """
    ds_dir = Path(cfg["dataset"]["dir"])
    train_cases = cfg["dataset"]["train_cases"]

    # Load + validate every SRC in the directory, then filter to train.
    # Doing validation on all SRCs (not just train) is cheap — it surfaces
    # problems with holdout cases too before they fail at holdout-eval
    # time.
    all_srcs = load_srcs(ds_dir)
    train_paths = {ds_dir / c / "src.json" for c in train_cases}
    train_srcs = [(s, p) for s, p in all_srcs if p in train_paths]

    if len(train_srcs) != len(train_cases):
        loaded = {p.parent.name for _, p in train_srcs}
        missing = set(train_cases) - loaded
        raise RuntimeError(
            f"failed to load all train_cases from {ds_dir}: missing "
            f"{sorted(missing)} (validation failure? check load_srcs logs)"
        )

    train_ds = build_dataset(
        train_srcs,
        claim_cap=cfg["rollout"]["claim_cap"],
        seed=cfg["training"]["seed"],
        n_mc=cfg["rollout"]["n_mc"],
    )

    env = SregEnv(
        dataset=train_ds,
        max_turns=cfg["rollout"]["max_turns"],
        claim_cap=cfg["rollout"]["claim_cap"],
        llm_call=_build_scorer_llm(scorer_cfg),
        n_mc=cfg["rollout"]["n_mc"],
    )
    return env, train_ds


def dry_run(cfg: dict, policy_cfg: RoleConfig, scorer_cfg: RoleConfig) -> bool:
    """Run 1 rollout end-to-end. Returns True if the rollout produced a
    finite reward, False otherwise.

    What this validates (the point of running it BEFORE --train):
      - YAML config loads and every named case resolves to a real src.json
      - Every SRC passes the SregEnv validation pipeline
      - Policy client can reach its endpoint and complete a rollout
      - Scorer client can reach its endpoint and score the submission
      - Reward function returns a finite float

    What it does NOT validate:
      - Training loop gradient updates
      - vLLM server behavior (dry-run can be run against Azure)
      - Long-horizon stability (1 rollout, not 50 steps)
    """
    print("\n=== DRY RUN ===")
    print(f"  Train cases ({len(cfg['dataset']['train_cases'])}): "
          f"{cfg['dataset']['train_cases']}")
    print(f"  Holdout ({len(cfg['dataset']['holdout_cases'])}): "
          f"{cfg['dataset']['holdout_cases']}")

    env, train_ds = _build_env_and_dataset(cfg, scorer_cfg)
    print(f"  Dataset rows loaded: {len(train_ds)}")
    print(f"  Tools: {list(env.tool_map.keys())}")

    client, model = _build_policy_client(policy_cfg)
    print(f"  Policy:  {model} @ {policy_cfg.base_url[:50]}...")
    print(f"  Scorer:  {scorer_cfg.model} @ {scorer_cfg.base_url[:50]}...")

    print("\n  Running 1 rollout on 1 example (this validates wiring)...")
    t0 = time.time()
    results = env.evaluate_sync(
        client=client,
        model=model,
        num_examples=1,
        rollouts_per_example=1,
        max_concurrent=1,
        state_columns=["problem_id"],
    )
    elapsed = time.time() - t0
    print(f"  Elapsed: {elapsed:.1f}s")

    outputs = results.get("outputs", [])
    if not outputs:
        print("  DRY RUN FAILED: no outputs from evaluate_sync")
        return False

    o = outputs[0]
    reward = o.get("reward")
    print(f"  problem_id: {o.get('problem_id')}")
    print(f"  reward: {reward}")
    print(f"  is_completed: {o.get('is_completed')}")
    print(f"  stop_condition: {o.get('stop_condition')}")
    if o.get("error"):
        print(f"  error: {o.get('error')}")

    ok = isinstance(reward, (int, float)) and reward == reward  # NaN-safe
    print(f"\n  DRY RUN {'PASSED' if ok else 'FAILED'}: "
          f"reward is{'' if ok else ' NOT'} a finite number")
    return ok


def train(cfg: dict, policy_cfg: RoleConfig, scorer_cfg: RoleConfig) -> None:
    """Run the actual GRPO training loop. Requires verifiers-rl.

    Currently a scaffold: the trainer integration lands when the `rl`
    extra is defined on a Linux+CUDA host. Use --dry-run until then.
    """
    try:
        import verifiers_rl  # noqa: F401
    except ImportError:
        print(
            "\nERROR: verifiers-rl is not installed.\n"
            "  This extra is Linux+CUDA only; it intentionally is NOT "
            "part of the `training` extra\n"
            "  because importing it on Windows dev would break the env.\n"
            "  On the training host: pip install verifiers-rl\n"
            "  (The `rl` extra in pyproject.toml will be added with the "
            "full trainer wiring.)\n"
            "  For now, only --dry-run is supported.",
            file=sys.stderr,
        )
        sys.exit(3)

    # Intentional: fail loud if someone runs --train before the trainer
    # integration is wired. Better to error here than silently no-op.
    raise NotImplementedError(
        "train() scaffold: needs verifiers-rl trainer API confirmed, "
        "Qwen3-8B LoRA config wired, and smoke on H100. Use --dry-run "
        "to validate the env/dataset/client wiring."
    )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", type=Path, required=True,
        help="Path to YAML config (e.g. configs/smoke_rl.yaml)",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run", action="store_true",
        help=(
            "Validate config + run 1 rollout end-to-end. No gradients, "
            "no verifiers-rl required. Always run this before --train "
            "on a new host — it catches missing env vars, broken SRCs, "
            "unreachable endpoints, etc. before paying for GPU time."
        ),
    )
    mode.add_argument(
        "--train", action="store_true",
        help=(
            "GRPO training loop. Requires verifiers-rl (Linux+CUDA). "
            "Currently a scaffold — raises NotImplementedError until "
            "the trainer integration lands."
        ),
    )
    # Role overrides — same names as eval_oi.py so muscle memory carries.
    parser.add_argument("--policy-base-url", default=None,
                        help="Override POLICY_BASE_URL / AZURE_FOUNDRY_BASE_URL")
    parser.add_argument("--policy-model", default=None,
                        help="Override POLICY_MODEL / AZURE_MODEL")
    parser.add_argument("--policy-api-key-var", default=None,
                        help="Override POLICY_API_KEY / AZURE_INFERENCE_CREDENTIAL")
    parser.add_argument("--scorer-base-url", default=None)
    parser.add_argument("--scorer-model", default=None)
    parser.add_argument("--scorer-api-key-var", default=None)
    args = parser.parse_args()

    print("=== SREG RL Training ===")
    print(f"Config: {args.config}")
    print(f"Mode:   {'DRY-RUN' if args.dry_run else 'TRAIN'}")

    # 1. Config load + validate (fails fast on bad YAML / missing env var /
    #    missing cases — BEFORE we stand up LLM clients).
    try:
        cfg = load_config(args.config)
        validate_config(cfg)
    except (FileNotFoundError, ValueError, TypeError) as e:
        print(f"\nERROR: config validation failed:\n  {e}", file=sys.stderr)
        sys.exit(2)

    # 2. Resolve role configs (may prompt env vars / fail if missing key).
    policy_cfg = resolve_role_config(
        "policy",
        cli_base_url=args.policy_base_url,
        cli_model=args.policy_model,
        cli_api_key_var=args.policy_api_key_var,
    )
    scorer_cfg = resolve_role_config(
        "scorer",
        cli_base_url=args.scorer_base_url,
        cli_model=args.scorer_model,
        cli_api_key_var=args.scorer_api_key_var,
    )

    # 3. Dispatch
    if args.dry_run:
        ok = dry_run(cfg, policy_cfg, scorer_cfg)
        sys.exit(0 if ok else 1)
    else:
        train(cfg, policy_cfg, scorer_cfg)


if __name__ == "__main__":
    main()
