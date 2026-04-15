#!/usr/bin/env python3
"""Evaluate SregEnv with a real LLM as policy — pre-training sanity check.

Uses verifiers' Environment.evaluate with an Azure-backed chat completions
client as the mock policy. This is NOT training — it's the validation that
the env + dataset + scoring pipeline actually produces usable rollouts
before we commit to a full RL run on H100.

Policy vs scorer are configured independently (see --policy-* and --scorer-*
flags). For H100 training the policy will point at a local vLLM server and
the scorer stays on Azure; both default to AZURE_* env vars so the
"everything on Azure" smoke-test path still works.

Usage:
    # Everything on Azure (default)
    python scripts/eval_oi.py --src test_data/test_src.json

    # Policy on local vLLM, scorer on Azure (H100-style)
    python scripts/eval_oi.py --dir results/batch \\
        --policy-base-url http://localhost:8000/v1 \\
        --policy-model Qwen/Qwen3-8B \\
        --policy-api-key-var VLLM_API_KEY

What this validates:
  - Dataset loader builds HF Dataset from SRCs
  - SregEnv + tools invoke correctly
  - Policy model completes turns, calls tools, submits claims
  - Scoring (compiler + verifier + judge) returns finite scores
  - Reward function produces usable signal
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

# Path bootstrap
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

# Windows compat (prime_tunnel needs fcntl)
from sreg.training._compat import patch_fcntl_if_windows
patch_fcntl_if_windows()

import verifiers as vf  # noqa: E402

from sreg.training import (  # noqa: E402
    RoleConfig,
    SregEnv,
    build_dataset,
    load_srcs,
    load_srcs_from_paths,
    resolve_role_config,
)


def build_scorer_llm(cfg: RoleConfig):
    """Sync LLM callback for scoring (compiler + relevance judge).

    Uses the Responses API because the OI scoring pipeline expects it.
    """
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


def build_policy_client(cfg: RoleConfig) -> tuple[vf.Client, str]:
    """Build the policy client for verifiers rollouts (chat completions)."""
    config = vf.ClientConfig(
        api_base_url=cfg.base_url,
        api_key_var=cfg.api_key_var,
        client_type="openai_chat_completions",
        timeout=600.0,
        max_retries=2,
    )
    client = vf.OpenAIChatCompletionsClient(config)
    return client, cfg.model


def _redact_config(cfg: RoleConfig) -> dict:
    """Dict form of RoleConfig for logging/JSON dumps. Api key hidden."""
    return {
        "base_url": cfg.base_url,
        "model": cfg.model,
        "api_key_var": cfg.api_key_var,
        "api_key": "***REDACTED***",
    }


def _validate_rewards(rewards: list[float]) -> None:
    """Fail fast on NaN/inf rewards — they silently corrupt batch means."""
    bad = [
        (i, r) for i, r in enumerate(rewards)
        if not isinstance(r, (int, float)) or math.isnan(r) or math.isinf(r)
    ]
    if bad:
        print("\nERROR: non-finite rewards detected:", file=sys.stderr)
        for i, r in bad:
            print(f"  rollout {i}: reward={r!r}", file=sys.stderr)
        sys.exit(2)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--src", type=Path, default=None,
        help="Path to single src.json (alternative to --dir)",
    )
    parser.add_argument(
        "--dir", type=Path, default=None,
        help="Directory with case folders (pattern **/src.json)",
    )
    parser.add_argument(
        "--num-examples", type=int, default=-1,
        help="Number of SRCs to eval (-1 = all)",
    )
    parser.add_argument(
        "--rollouts", type=int, default=1,
        help="Rollouts per SRC (G for GRPO)",
    )
    parser.add_argument(
        "--max-concurrent", type=int, default=1,
        help="Max concurrent rollouts (keep low for Azure rate limits)",
    )
    parser.add_argument(
        "--max-turns", type=int, default=15,
        help="Max turns per rollout",
    )
    parser.add_argument(
        "--claim-cap", type=int, default=5,
        help="Max claims per submission",
    )
    parser.add_argument(
        "--n-mc", type=int, default=10_000,
        help="Monte Carlo samples for verification",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output path for results JSON",
    )
    # Policy config (the model being evaluated / trained)
    parser.add_argument(
        "--policy-base-url", default=None,
        help="Base URL for policy client (default: POLICY_BASE_URL or AZURE_FOUNDRY_BASE_URL)",
    )
    parser.add_argument(
        "--policy-model", default=None,
        help="Policy model identifier (default: POLICY_MODEL or AZURE_MODEL)",
    )
    parser.add_argument(
        "--policy-api-key-var", default=None,
        help="Env var name holding the policy API key (default: POLICY_API_KEY or AZURE_INFERENCE_CREDENTIAL)",
    )
    # Scorer config (LLM for OI scoring pipeline: compiler + judge)
    parser.add_argument(
        "--scorer-base-url", default=None,
        help="Base URL for scorer LLM (default: SCORER_BASE_URL or AZURE_FOUNDRY_BASE_URL)",
    )
    parser.add_argument(
        "--scorer-model", default=None,
        help="Scorer model identifier (default: SCORER_MODEL or AZURE_MODEL)",
    )
    parser.add_argument(
        "--scorer-api-key-var", default=None,
        help="Env var name holding the scorer API key (default: SCORER_API_KEY or AZURE_INFERENCE_CREDENTIAL)",
    )
    args = parser.parse_args()

    if not args.src and not args.dir:
        parser.error("Must provide --src or --dir")
    if args.src and args.dir:
        parser.error("Use --src OR --dir, not both")

    # Resolve role configs up front — fail fast if anything is missing.
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

    # 1. Load dataset
    print("=== Load SRCs ===")
    if args.src:
        valid = load_srcs_from_paths([args.src])
    else:
        valid = load_srcs(args.dir)
    if not valid:
        print("ERROR: no valid SRCs found")
        sys.exit(1)
    print(f"Valid SRCs: {len(valid)}")

    ds = build_dataset(
        valid, claim_cap=args.claim_cap, n_mc=args.n_mc,
    )
    print(f"Dataset rows: {len(ds)}")

    # 2. Build env
    print("\n=== Build env ===")
    llm_call = build_scorer_llm(scorer_cfg)
    env = SregEnv(
        dataset=ds,
        max_turns=args.max_turns,
        claim_cap=args.claim_cap,
        llm_call=llm_call,
        n_mc=args.n_mc,
    )
    print(f"Tools: {list(env.tool_map.keys())}")
    print(f"Max turns: {env.max_turns}")
    print(f"Scorer:  model={scorer_cfg.model}  base_url={scorer_cfg.base_url[:60]}...")

    # 3. Build policy client
    print("\n=== Build policy client ===")
    client, model = build_policy_client(policy_cfg)
    print(f"Policy:  model={model}  base_url={policy_cfg.base_url[:60]}...")
    if policy_cfg.base_url == scorer_cfg.base_url and policy_cfg.model == scorer_cfg.model:
        print("  (policy and scorer are the same endpoint — Azure smoke path)")

    # 4. Evaluate
    print(f"\n=== Evaluate ({args.num_examples} examples x {args.rollouts} rollouts) ===")
    t0 = time.time()
    results = env.evaluate_sync(
        client=client,
        model=model,
        num_examples=args.num_examples,
        rollouts_per_example=args.rollouts,
        max_concurrent=args.max_concurrent,
        state_columns=["problem_id"],
    )
    elapsed = time.time() - t0
    print(f"Eval complete: {elapsed:.1f}s")

    # 5. Report — GenerateOutputs is a TypedDict: {"outputs": [RolloutOutput, ...], "metadata": ...}
    print("\n=== Results ===")
    outputs = results.get("outputs", [])
    if not outputs:
        print("No outputs in results.")
        return

    rewards = [o.get("reward", 0.0) for o in outputs]
    # NaN/inf guard: non-finite rewards silently poison batch mean.
    _validate_rewards(rewards)

    completed = [o.get("is_completed", False) for o in outputs]
    truncated = [o.get("is_truncated", False) for o in outputs]
    stop_conditions = [o.get("stop_condition", "?") for o in outputs]
    errors = [o.get("error") for o in outputs]
    problem_ids = [o.get("problem_id") for o in outputs]

    import statistics
    print(f"N rollouts: {len(outputs)}")
    print(f"Reward: mean={statistics.mean(rewards):.4f}, min={min(rewards):.4f}, max={max(rewards):.4f}")
    print(f"Completed: {sum(completed)}/{len(completed)}")
    print(f"Truncated: {sum(truncated)}/{len(truncated)}")
    print(f"Stop conditions: {dict((c, stop_conditions.count(c)) for c in set(stop_conditions))}")
    if any(errors):
        print(f"Errors: {[e for e in errors if e]}")
    if any(problem_ids):
        unique_pids = sorted({p for p in problem_ids if p})
        print(f"Problem IDs: {len(unique_pids)} unique ({unique_pids[:5]}{'...' if len(unique_pids) > 5 else ''})")

    # Aggregate metrics across rollouts
    all_metric_keys = set()
    for o in outputs:
        all_metric_keys.update((o.get("metrics") or {}).keys())
    if all_metric_keys:
        print("\nMetrics (per rollout):")
        for k in sorted(all_metric_keys):
            vals = [(o.get("metrics") or {}).get(k) for o in outputs]
            vals = [v for v in vals if v is not None]
            if vals:
                try:
                    print(f"  {k}: mean={statistics.mean(vals):.4f}, vals={vals}")
                except Exception:
                    print(f"  {k}: {vals}")

    # Print first rollout trajectory summary
    print("\n=== Rollout 0 trajectory ===")
    o0 = outputs[0]
    traj = o0.get("trajectory", [])
    completion = o0.get("completion", [])
    print(f"Trajectory steps: {len(traj)}")
    print(f"Completion messages: {len(completion)}")
    print(f"Is completed: {o0.get('is_completed')}  truncated: {o0.get('is_truncated')}  stop: {o0.get('stop_condition')}")
    print(f"Problem ID: {o0.get('problem_id')}")
    tokens = o0.get("token_usage") or {}
    if tokens:
        print(f"Tokens: {tokens}")

    # Save full results if requested
    if args.output:
        output_data = {
            "config": {
                "args": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
                "policy": _redact_config(policy_cfg),
                "scorer": _redact_config(scorer_cfg),
            },
            "elapsed_s": elapsed,
            "num_examples": args.num_examples,
            "rollouts_per_example": args.rollouts,
            "rewards": rewards,
            "completed": completed,
            "truncated": truncated,
            "stop_conditions": stop_conditions,
            "errors": errors,
            "problem_ids": problem_ids,
            "metrics_per_rollout": [o.get("metrics") or {} for o in outputs],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, default=str)
        print(f"\nSaved results -> {args.output}")


if __name__ == "__main__":
    main()
