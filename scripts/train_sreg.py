#!/usr/bin/env python3
"""GRPO training harness for SregEnv — config-driven, dry-run aware.

Two modes:
    --dry-run   Validate config + run 1 rollout end-to-end with the
                configured env / dataset / policy / scorer. No gradients,
                no verifiers-rl required. This is the gate BEFORE paying
                for a real training run: if the wiring is broken, it
                surfaces here in ~3 min instead of 30 hours into a job.

    --train     GRPO training loop via verifiers_rl.RLTrainer.
                Requires `pip install -e ".[rl]"` on a Linux+CUDA host
                AND a vLLM server running at the host:port specified in
                `training.vllm_server_*`. Fails fast with a clear
                message on Windows dev or if vLLM is unreachable.

Config:
    configs/smoke_rl.yaml (or whatever path is passed via --config)
    See src/sreg/training/train_config.py for the accepted schema.

Usage:
    # Windows dev / Azure scorer smoke (gate — always run before --train)
    export SREG_P05_BATCH="/path/to/results/p05_canonical_batch"
    python scripts/train_sreg.py --config configs/smoke_rl.yaml --dry-run

    # H100 smoke — policy on local vLLM, scorer on Azure
    # Step 1 (separate pane): vf-vllm serve Qwen/Qwen3-8B ...
    # Step 2:
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


def _build_rl_config(cfg: dict):
    """Map our YAML `training:` section to `verifiers_rl.RLConfig`.

    We keep a YAML schema (not TOML as the upstream `vf-rl` convention
    expects) because the same file drives the `--dry-run` gate + dataset
    split + role configs, none of which fit into `RLConfig` cleanly.
    Price paid: this mapping function. Cheap.

    Fields NOT mapped here use RLConfig defaults (lora_dropout, bf16,
    lr_scheduler_type, save_strategy, mask_env_responses, etc.). That
    keeps the YAML focused on decisions we've actually made.
    """
    from verifiers_rl.rl.trainer import RLConfig

    t = cfg["training"]
    # Precision defaults: bf16=True, fp16=False — right for Ampere+/Hopper
    # (H100 canonical). T4 (Turing sm_75) has no bf16 tensor cores, so smoke
    # configs on T4 must flip these. Optional in YAML so H100 paths stay terse.
    # `use_liger` default True is verifiers-rl's own; T4 can't run liger
    # kernels so smoke_t4 disables it. `attn_implementation` is applied in
    # `train()` at model load, not here — RLConfig has no such field.
    kwargs = dict(
        run_name=t["run_name"],
        output_dir=f"outputs/{t['run_name']}",
        rollouts_per_example=t["rollouts_per_example"],
        batch_size=t["batch_size"],
        micro_batch_size=t["micro_batch_size"],
        max_concurrent=t["max_concurrent"],
        max_steps=t["total_steps"],
        seed=t["seed"],
        max_tokens=t["max_tokens"],
        max_seq_len=t["max_seq_len"],
        temperature=cfg["rollout"]["temperature"],
        learning_rate=t["learning_rate"],
        use_lora=t["use_lora"],
        lora_rank=t["lora_rank"],
        lora_alpha=t["lora_alpha"],
        vllm_server_host=t["vllm_server_host"],
        vllm_server_port=t["vllm_server_port"],
        bf16=t.get("bf16", True),
        fp16=t.get("fp16", False),
        use_liger=t.get("use_liger", True),
        save_steps=t["save_steps"],
        logging_steps=t["logging_steps"],
        report_to=t["report_to"] if t["report_to"] is not None else "none",
    )
    return RLConfig(**kwargs)


def _dump_config_snapshot(cfg: dict, rl_config, output_dir: Path) -> None:
    """Dump resolved YAML + RLConfig to the run's output dir.

    Reproducibility: the run YAML is env-var-expanded and maps into
    RLConfig with defaults filled in. A year from now nobody remembers
    what RLConfig defaults were on this date. Snapshot both so the
    training run is self-describing.
    """
    import json

    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "config_resolved.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, default=str)

    # RLConfig is a dataclass extending TrainingArguments — not trivially
    # json-serializable (has Path, dtype, enum). to_dict() on
    # TrainingArguments handles it.
    try:
        rl_dict = rl_config.to_dict()
    except Exception:
        rl_dict = {"_note": "rl_config.to_dict() failed; see RLConfig source"}
    with open(output_dir / "rl_config.json", "w", encoding="utf-8") as f:
        json.dump(rl_dict, f, indent=2, default=str)


def train(cfg: dict, policy_cfg: RoleConfig, scorer_cfg: RoleConfig) -> None:
    """Run the GRPO training loop via verifiers_rl.RLTrainer.

    Requires verifiers-rl (Linux+CUDA). Before calling this, a vLLM
    server must be serving the model at `training.vllm_server_host:port`
    — typically launched via `vf-vllm` or `vf-rl` in a separate tmux
    pane. We do NOT start vLLM from here because it needs its own GPUs.

    Flow:
      1. Import verifiers_rl (fails hard w/ clear error on Windows dev)
      2. Build env + train dataset (same wiring as dry-run)
      3. Build RLConfig from YAML
      4. Snapshot resolved config to outputs/<run_name>/
      5. RLTrainer(model, env, args).train()

    The scorer is still on Azure — embedded in SregEnv via `llm_call`.
    On H100 the policy rollouts (vLLM) are fast; the Azure scorer is the
    bottleneck. See smoke_rl.yaml for the tuning tradeoff.
    """
    try:
        from verifiers_rl.rl.trainer import RLTrainer
    except ImportError as e:
        print(
            "\nERROR: verifiers-rl is not installed.\n"
            "  This extra is Linux+CUDA only; it intentionally is NOT "
            "part of the `training` extra\n"
            "  because importing it on Windows dev would break the env.\n"
            f"  Import error: {e}\n"
            "  On the H100 host: pip install -e \".[rl]\"\n"
            "  Then make sure a vLLM server is running at "
            "training.vllm_server_host:port before calling --train.",
            file=sys.stderr,
        )
        sys.exit(3)

    print("\n=== TRAIN ===")
    print(f"  Model:   {cfg['training']['model']}")
    print(f"  Run:     {cfg['training']['run_name']}")
    print(f"  Steps:   {cfg['training']['total_steps']}")
    print(f"  G:       {cfg['training']['rollouts_per_example']}")
    print(f"  Batch:   {cfg['training']['batch_size']} rollouts/step "
          f"({cfg['training']['batch_size'] // cfg['training']['rollouts_per_example']} "
          f"prompts/step)")

    # Same wiring as dry-run: SregEnv + HF train dataset built from YAML.
    # Note: the policy_cfg is ignored at train time — the trainer reads
    # the model name from YAML and connects to the vLLM server directly.
    # policy_cfg is still resolved up in main() because it's needed for
    # eval hooks (if we add them later) and for symmetry with --dry-run.
    env, train_ds = _build_env_and_dataset(cfg, scorer_cfg)
    print(f"  Dataset rows: {len(train_ds)}")
    print(f"  Scorer:  {scorer_cfg.model} @ {scorer_cfg.base_url[:50]}...")
    print(f"  vLLM:    http://{cfg['training']['vllm_server_host']}:"
          f"{cfg['training']['vllm_server_port']}")

    rl_config = _build_rl_config(cfg)
    output_dir = Path(rl_config.output_dir)
    _dump_config_snapshot(cfg, rl_config, output_dir)
    print(f"  Output:  {output_dir.resolve()}")

    # Pre-load model so we can pick dtype + attn_implementation per-host.
    # verifiers-rl's default loader hardcodes bf16 + flash_attention_2, which
    # breaks on T4 (Turing). When we pass a str model name, the trainer calls
    # that loader; passing a PreTrainedModel skips it. See
    # verifiers_rl/rl/trainer/utils.py:get_model.
    import torch
    from verifiers_rl import get_model_and_tokenizer

    t = cfg["training"]
    dtype = torch.float16 if t.get("fp16", False) else torch.bfloat16
    model_kwargs = {"dtype": dtype, "use_cache": False}
    attn_impl = t.get("attn_implementation")
    if attn_impl is not None:
        model_kwargs["attn_implementation"] = attn_impl
    model_obj, tokenizer = get_model_and_tokenizer(
        t["model"],
        use_liger=t.get("use_liger", True),
        model_kwargs=model_kwargs,
    )

    # RLTrainer instantiation triggers:
    #   - LoRA wrap (if use_lora)
    #   - vLLM client init (requires server to be up)
    #   - Orchestrator start + first batch submit
    # If vLLM is down this is where we fail fast.
    trainer = RLTrainer(
        model=model_obj, env=env, args=rl_config, processing_class=tokenizer
    )

    print("\n  Starting trainer.train() — this blocks until max_steps hit.")
    trainer.train()
    print("\n=== TRAIN COMPLETE ===")


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
            "GRPO training loop via verifiers_rl.RLTrainer. Requires "
            "verifiers-rl installed (Linux+CUDA host) AND a vLLM server "
            "up at training.vllm_server_host:port. Fails fast with exit "
            "code 3 if the import fails (e.g. running on Windows dev)."
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
