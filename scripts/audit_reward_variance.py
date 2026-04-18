#!/usr/bin/env python3
"""Reward variance audit — GRPO signal check BEFORE spending H100 hours (#39).

GRPO normalizes advantages by intra-group std. If groups collapse
(all rollouts identical), advantage=0 and no gradient flows. This
script measures whether the current env + policy + reward combo
produces enough within-group spread to train on.

Runs N prompts x G rollouts each against the configured policy
(Azure by default — no GPU needed), then reports group-level
variance diagnostics and a PASS/BORDERLINE/FAIL verdict.

Usage:
    export SREG_P05_BATCH="/path/to/results/p05_canonical_batch"
    python scripts/audit_reward_variance.py \\
        --config configs/smoke_rl.yaml \\
        --num-cases 6 \\
        --rollouts-per-case 4

Output written to research/notes/variance_audit_YYYY-MM-DD/:
    - audit.json         aggregated report + verdict + run metadata
    - trajectories.jsonl per-rollout details (streamable)
    - report.md          human-readable interpretation
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

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
from sreg.training.eval_report import (  # noqa: E402
    run_metadata,
    variance_report,
    variance_verdict,
    write_trajectories_jsonl,
)


def _build_scorer_llm(cfg: RoleConfig):
    """Reused from scripts/train_sreg.py — sync LLM callback for scorer."""
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
    """Reused from scripts/train_sreg.py — verifiers policy client."""
    import verifiers as vf

    config = vf.ClientConfig(
        api_base_url=cfg.base_url,
        api_key_var=cfg.api_key_var,
        client_type="openai_chat_completions",
        timeout=600.0,
        max_retries=2,
    )
    return vf.OpenAIChatCompletionsClient(config), cfg.model


def _select_prompts(
    cfg: dict, num_cases: int, explicit: list[str] | None, seed: int,
) -> list[str]:
    """Pick the N prompts to audit.

    Codex (2026-04-17) flagged that blindly taking the first N by
    filesystem order gives non-reproducible samples across hosts. If
    --prompts is given we use it as-is; otherwise seeded random sample
    from train_cases.
    """
    train_cases = list(cfg["dataset"]["train_cases"])
    if explicit:
        unknown = set(explicit) - set(train_cases)
        if unknown:
            raise ValueError(
                f"--prompts contains cases not in train_cases: "
                f"{sorted(unknown)}"
            )
        return explicit
    if num_cases > len(train_cases):
        raise ValueError(
            f"--num-cases {num_cases} > train_cases available "
            f"({len(train_cases)}): {train_cases}"
        )
    rng = random.Random(seed)
    return sorted(rng.sample(train_cases, num_cases))


def _build_env_for_prompts(
    cfg: dict, scorer_cfg: RoleConfig, prompts: list[str],
) -> tuple[SregEnv, object]:
    """Load only the selected prompts into the dataset (not all train_cases).

    `SregEnv.evaluate_sync(num_examples=N)` would take the first N rows of
    the dataset. By filtering the dataset up-front to exactly our selected
    prompts, we get the prompts we chose regardless of disk ordering.
    """
    ds_dir = Path(cfg["dataset"]["dir"])
    all_srcs = load_srcs(ds_dir)
    selected_paths = {ds_dir / c / "src.json" for c in prompts}
    selected_srcs = [(s, p) for s, p in all_srcs if p in selected_paths]

    loaded = {p.parent.name for _, p in selected_srcs}
    missing = set(prompts) - loaded
    if missing:
        raise RuntimeError(
            f"failed to load prompts from {ds_dir}: missing "
            f"{sorted(missing)} (validation failure? check load_srcs logs)"
        )

    ds = build_dataset(
        selected_srcs,
        claim_cap=cfg["rollout"]["claim_cap"],
        seed=cfg["training"]["seed"],
        n_mc=cfg["rollout"]["n_mc"],
    )

    env = SregEnv(
        dataset=ds,
        max_turns=cfg["rollout"]["max_turns"],
        claim_cap=cfg["rollout"]["claim_cap"],
        llm_call=_build_scorer_llm(scorer_cfg),
        n_mc=cfg["rollout"]["n_mc"],
    )
    return env, ds


def _write_markdown(
    *, report: dict, verdict: dict, metadata: dict, args: argparse.Namespace,
    prompts: list[str], elapsed_s: float, out_path: Path,
) -> None:
    """Human-readable interpretation. The operator should be able to
    decide from this doc alone whether to proceed to H100."""
    zv = report["pct_zero_variance_groups"]
    sv = report["pct_single_reward_groups"]
    lo, hi = report["bootstrap_ci_95"]
    lines: list[str] = []
    lines.append(f"# Reward variance audit — {metadata['timestamp_utc'][:10]}\n")
    lines.append(f"**Verdict:** `{verdict['verdict']}`\n")
    lines.append(f"> {verdict['recommendation']}\n")
    lines.append("## Configuration\n")
    lines.append(f"- Config: `{args.config}`")
    lines.append(f"- Policy temperature: `{report.get('_temperature', args.temperature)}`")
    lines.append(f"- N prompts: **{report['n_groups']}**, "
                 f"G rollouts/prompt: **{args.rollouts_per_case}** "
                 f"(total rollouts: {report['n_rollouts']})")
    lines.append(f"- Prompts sampled: {prompts}")
    lines.append(f"- Wall-clock: {elapsed_s/60:.1f} min\n")
    lines.append("## Aggregate metrics\n")
    lines.append(f"- `mean_reward`: **{report['mean_reward']:.3f}**")
    lines.append(
        f"- `mean_intra_group_std`: **{report['mean_intra_group_std']:.3f}** "
        f"(95% CI: [{lo:.3f}, {hi:.3f}])"
    )
    lines.append(
        f"- `submitted_only_mean_std`: "
        f"**{report['submitted_only_mean_std']:.3f}** "
        f"(across {report['submitted_only_n_groups']} qualifying groups)"
    )
    lines.append(f"- `mean_top1_top2_gap`: **{report['mean_top1_top2_gap']:.3f}**")
    lines.append(f"- `submit_rate`: **{report['submit_rate']*100:.1f}%**")
    lines.append(f"- `pct_zero_variance_groups`: **{zv:.1f}%**")
    lines.append(f"- `pct_single_reward_groups`: **{sv:.1f}%**")
    corr = report["step_count_reward_correlation"]
    corr_str = "NaN" if corr != corr else f"{corr:+.3f}"
    lines.append(f"- `step_count_reward_correlation`: **{corr_str}** "
                 f"(negative = more effort → less reward, smell of penalty bug)\n")
    lines.append("## Gate results\n")
    lines.append("| Gate | Threshold | Passed |")
    lines.append("|---|---|---|")
    thr = verdict["thresholds"]
    gates = verdict["gates"]
    lines.append(
        f"| all_rewards_mean_std >= {thr['all_std_min']} | "
        f"{report['mean_intra_group_std']:.3f} | "
        f"{'YES' if gates['all_std_ok'] else 'NO'} |"
    )
    lines.append(
        f"| submitted_only_mean_std >= {thr['submitted_std_min']} | "
        f"{report['submitted_only_mean_std']:.3f} | "
        f"{'YES' if gates['submitted_std_ok'] else 'NO'} |"
    )
    lines.append(
        f"| pct_zero_variance_groups <= {thr['zero_var_max_pct']}% | "
        f"{zv:.1f}% | "
        f"{'YES' if gates['not_too_many_collapsed'] else 'NO'} |"
    )
    lines.append("\n## Stop condition distribution\n")
    for k, v in sorted(report["stop_condition_distribution"].items()):
        pct = 100.0 * v / report["n_rollouts"] if report["n_rollouts"] else 0
        lines.append(f"- `{k}`: {v} ({pct:.1f}%)")
    lines.append("\n## Per-group detail\n")
    lines.append("| problem_id | n | mean | std | n_unique | submitted | "
                 "submitted_only_std |")
    lines.append("|---|---|---|---|---|---|---|")
    for pid, g in sorted(report["per_group"].items()):
        sub_std = g["submitted_only_std"]
        sub_str = f"{sub_std:.3f}" if sub_std is not None else "—"
        lines.append(
            f"| {pid} | {g['n_rollouts']} | {g['reward_mean']:+.3f} | "
            f"{g['reward_std']:.3f} | {g['n_unique_rewards']} | "
            f"{g['submitted_count']}/{g['n_rollouts']} | {sub_str} |"
        )
    lines.append("\n## Reproducibility\n")
    lines.append(f"- Git SHA: `{metadata.get('git_sha', '?')}` "
                 f"(dirty={metadata.get('git_dirty')})")
    lines.append(f"- verifiers: `{metadata.get('verifiers_version', '?')}`")
    lines.append(f"- Python: `{metadata.get('python_version', '?')}`\n")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", type=Path, required=True,
                        help="YAML config path (reused from train_sreg.py)")
    parser.add_argument("--num-cases", type=int, default=6,
                        help="Number of prompts to audit (default 6)")
    parser.add_argument("--rollouts-per-case", type=int, default=4,
                        help="G rollouts per prompt (default 4)")
    parser.add_argument("--temperature", type=float, default=None,
                        help="Override rollout.temperature from config "
                             "(useful for comparing temps)")
    parser.add_argument("--prompts", type=str, default=None,
                        help="Comma-separated problem_ids to use instead "
                             "of random sample")
    parser.add_argument("--max-concurrent", type=int, default=2,
                        help="Parallel rollouts (default 2 — conservative "
                             "for Azure rate limits)")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Where to write outputs (default "
                             "research/notes/variance_audit_YYYY-MM-DD/)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Seed for prompt sampling (default 42)")
    # Role overrides — same names as eval_oi.py
    parser.add_argument("--policy-base-url", default=None)
    parser.add_argument("--policy-model", default=None)
    parser.add_argument("--policy-api-key-var", default=None)
    parser.add_argument("--scorer-base-url", default=None)
    parser.add_argument("--scorer-model", default=None)
    parser.add_argument("--scorer-api-key-var", default=None)
    args = parser.parse_args()

    print("=== REWARD VARIANCE AUDIT (#39) ===")
    print(f"Config: {args.config}")

    # 1. Config load + validate
    try:
        cfg = load_config(args.config)
        validate_config(cfg)
    except (FileNotFoundError, ValueError, TypeError) as e:
        print(f"\nERROR: config validation failed:\n  {e}", file=sys.stderr)
        sys.exit(2)

    if args.temperature is not None:
        cfg["rollout"]["temperature"] = args.temperature

    # 2. Resolve role configs
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

    # 3. Select prompts (seeded random sample unless --prompts given)
    explicit = [s.strip() for s in args.prompts.split(",")] if args.prompts else None
    prompts = _select_prompts(cfg, args.num_cases, explicit, args.seed)
    print(f"Prompts ({len(prompts)}): {prompts}")

    # 4. Build env + dataset, run rollouts
    env, ds = _build_env_for_prompts(cfg, scorer_cfg, prompts)
    client, model = _build_policy_client(policy_cfg)
    print(f"Policy:      {model} @ {policy_cfg.base_url[:50]}...")
    print(f"Scorer:      {scorer_cfg.model} @ {scorer_cfg.base_url[:50]}...")
    print(f"Temperature: {cfg['rollout']['temperature']}")
    print(f"G per prompt: {args.rollouts_per_case}")
    total = len(prompts) * args.rollouts_per_case
    print(f"Total rollouts: {total}")
    print(f"Max concurrent: {args.max_concurrent}")

    # Sampling args override the policy's defaults so this script actually
    # runs with the temperature reported in the MD. Without this, the
    # underlying OpenAI client may ignore our config.
    #
    # NOTE: we intentionally do NOT forward cfg.training.max_tokens here.
    # gpt-5.4 is a reasoning model where the per-turn cap includes hidden
    # reasoning tokens — a 1024 cap can be fully consumed by CoT, leaving
    # zero content/tool-call tokens, which verifiers-rl surfaces as
    # EmptyModelResponseError and kills the rollout (reward = -0.1 penalty).
    # Seen 2026-04-17: 24/24 rollouts failed this way. Drop the cap so the
    # audit measures genuine reward variance, not truncation-induced zeros.
    sampling_args = {
        "temperature": cfg["rollout"]["temperature"],
    }

    print("\nRunning rollouts (this will take a while — Azure-bound)...")
    t0 = time.time()
    results = env.evaluate_sync(
        client=client,
        model=model,
        num_examples=len(prompts),
        rollouts_per_example=args.rollouts_per_case,
        max_concurrent=args.max_concurrent,
        sampling_args=sampling_args,
        state_columns=["problem_id"],
    )
    elapsed = time.time() - t0
    outputs = results.get("outputs", [])
    print(f"Done in {elapsed/60:.1f} min; {len(outputs)} rollouts produced")

    # 5. Aggregate + verdict
    report = variance_report(outputs)
    report["_temperature"] = cfg["rollout"]["temperature"]
    verdict = variance_verdict(report)
    metadata = run_metadata()

    # 6. Dump outputs
    out_dir = args.output_dir or (
        Path(__file__).parent.parent / "research" / "notes"
        / f"variance_audit_{date.today().isoformat()}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    audit_payload = {
        "metadata": metadata,
        "args": {
            "config": str(args.config),
            "num_cases": args.num_cases,
            "rollouts_per_case": args.rollouts_per_case,
            "temperature": cfg["rollout"]["temperature"],
            "prompts": prompts,
            "max_concurrent": args.max_concurrent,
            "seed": args.seed,
        },
        "report": report,
        "verdict": verdict,
        "elapsed_s": elapsed,
    }
    with open(out_dir / "audit.json", "w", encoding="utf-8") as f:
        json.dump(audit_payload, f, indent=2, default=str)

    n_written = write_trajectories_jsonl(outputs, out_dir / "trajectories.jsonl")

    _write_markdown(
        report=report, verdict=verdict, metadata=metadata, args=args,
        prompts=prompts, elapsed_s=elapsed, out_path=out_dir / "report.md",
    )

    # 7. Print summary to stdout
    print("\n=== VERDICT ===")
    print(f"  {verdict['verdict']}")
    print(f"  {verdict['recommendation']}")
    print("\n=== KEY METRICS ===")
    print(f"  mean_reward                  : {report['mean_reward']:+.3f}")
    print(f"  mean_intra_group_std         : {report['mean_intra_group_std']:.3f} "
          f"(CI: [{report['bootstrap_ci_95'][0]:.3f}, "
          f"{report['bootstrap_ci_95'][1]:.3f}])")
    print(f"  submitted_only_mean_std      : {report['submitted_only_mean_std']:.3f}")
    print(f"  pct_zero_variance_groups     : {report['pct_zero_variance_groups']:.1f}%")
    print(f"  submit_rate                  : {report['submit_rate']*100:.1f}%")
    print(f"\nOutputs written to: {out_dir.resolve()}")
    print(f"  - audit.json         ({out_dir/'audit.json'})")
    print(f"  - trajectories.jsonl ({n_written} rollouts)")
    print("  - report.md          (human-readable)")

    sys.exit(0 if verdict["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
