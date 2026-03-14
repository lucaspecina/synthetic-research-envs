#!/usr/bin/env python3
"""Dry run: validate SregEnv end-to-end with a real model.

Two inference backends, auto-detected:
  - Linux  -> vLLM (OpenAI-compatible API server, fast, GPU)
  - Other  -> transformers (local inference, no server needed)

Usage:
    # Auto-detect backend (transformers on Windows, vLLM on Linux):
    python scripts/dry_run.py --model Qwen/Qwen2.5-0.5B-Instruct

    # Force a backend:
    python scripts/dry_run.py --backend transformers --model Qwen/Qwen2.5-0.5B-Instruct
    python scripts/dry_run.py --backend vllm --api-url http://localhost:8000/v1

    # Dataset only (no model):
    python scripts/dry_run.py --dataset-only --num-srcs 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import platform
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sreg.training._compat import patch_fcntl_if_windows

patch_fcntl_if_windows()

import verifiers as vf  # noqa: E402

from sreg.training.dataset import generate_dataset  # noqa: E402
from sreg.training.env import SregEnv  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Transformers backend: local inference with manual rollout loop
# ---------------------------------------------------------------------------


def _load_transformers_model(model_name: str):
    """Load model and tokenizer with transformers."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    logger.info("Loading model %s with transformers...", model_name)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=dtype,
        device_map=device,
        trust_remote_code=True,
    )

    logger.info("Model loaded on %s (%s)", device, model.dtype)
    return model, tokenizer


def _tool_defs_to_openai_format(env: SregEnv) -> list[dict]:
    """Convert verifiers Tool objects to OpenAI function format."""
    tools = []
    for td in env.tool_defs:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": td.name,
                    "description": td.description,
                    "parameters": td.parameters,
                },
            }
        )
    return tools


def _generate_with_tools(model, tokenizer, messages, tools, max_tokens=1024):
    """Generate a response using the chat template with tools."""
    import torch

    text = tokenizer.apply_chat_template(
        messages,
        tools=tools,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    input_len = inputs["input_ids"].shape[1]

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )

    new_tokens = outputs[0][input_len:]
    return tokenizer.decode(new_tokens, skip_special_tokens=False)


def _parse_tool_calls(raw_output: str) -> tuple[str, list[dict]]:
    """Parse tool calls from model output.

    Qwen uses Hermes-style: <tool_call>{"name":..., "arguments":...}</tool_call>
    Returns (text_content, list_of_tool_calls).
    """
    tool_calls = []
    text_parts = []
    remaining = raw_output

    while "<tool_call>" in remaining:
        before, _, rest = remaining.partition("<tool_call>")
        text_parts.append(before)

        if "</tool_call>" in rest:
            call_json, _, remaining = rest.partition("</tool_call>")
        else:
            call_json = rest
            remaining = ""

        call_json = call_json.strip()
        try:
            parsed = json.loads(call_json)
            tool_calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "name": parsed.get("name", ""),
                    "arguments": json.dumps(parsed.get("arguments", {})),
                }
            )
        except json.JSONDecodeError:
            text_parts.append(f"[malformed tool call: {call_json[:100]}]")

    text_parts.append(remaining)
    text_content = "".join(text_parts).strip()

    # Clean up special tokens from text
    for token in ["<|im_end|>", "<|endoftext|>", "<|im_start|>"]:
        text_content = text_content.replace(token, "").strip()

    return text_content, tool_calls


async def _run_transformers_rollouts(
    env: SregEnv,
    ds,
    model_name: str,
    max_turns: int,
) -> list[dict]:
    """Run rollouts using transformers (no external server)."""
    model, tokenizer = _load_transformers_model(model_name)
    tools = _tool_defs_to_openai_format(env)

    results = []

    for idx in range(len(ds)):
        row = ds[idx]
        logger.info("--- Rollout %d/%d ---", idx + 1, len(ds))

        # Setup state
        state: vf.State = {
            "prompt": row["prompt"],
            "info": row["info"],
        }
        state = await env.setup_state(state)

        # Build initial messages
        messages = list(row["prompt"])
        if isinstance(messages[0], str):
            messages = json.loads(messages[0])

        turn = 0
        while turn < max_turns:
            turn += 1

            # Generate
            raw = _generate_with_tools(model, tokenizer, messages, tools)
            logger.debug("  Raw output: %s", repr(raw[:200]))
            text_content, tool_calls = _parse_tool_calls(raw)

            if not tool_calls:
                # No tool calls — model just responded with text
                logger.info(
                    "  Turn %d: no tool call. Text: %s",
                    turn,
                    text_content[:120],
                )
                state["done_reason"] = "no_tool_call"
                break

            # Process each tool call
            assistant_msg = {"role": "assistant", "content": text_content}
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"],
                        },
                    }
                    for tc in tool_calls
                ]
            messages.append(assistant_msg)

            for tc in tool_calls:
                tool_name = tc["name"]
                try:
                    tool_args = json.loads(tc["arguments"])
                except json.JSONDecodeError:
                    tool_args = {}

                # Inject hidden args
                tool_args = env.update_tool_args(tool_name, tool_args, messages, state)

                try:
                    result_msg = await env.call_tool(tool_name, tool_args, tc["id"])
                    tool_result = result_msg.content
                except Exception as e:
                    tool_result = f"Error: {e}"

                logger.info(
                    "  Turn %d: %s(%s) -> %s",
                    turn,
                    tool_name,
                    json.dumps(
                        {k: v for k, v in tool_args.items() if k not in ("runner", "state")},
                    )[:60],
                    str(tool_result)[:80],
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": str(tool_result),
                    }
                )

            # Check if episode is done
            if state.get("submitted") or state.get("done_reason"):
                break

        # Compute reward
        info = json.loads(row["info"])
        reward = 0.0
        if state.get("submitted"):
            from sreg.training.rubric import score_submission
            from sreg.training.types import SubmitPayload

            payload = SubmitPayload(**state["submission_payload"])
            reward = score_submission(
                payload,
                info["eval_type"],
                info["correct_answer"],
                kl_cutoff=state.get("kl_cutoff", 5.0),
            )
        elif state.get("done_reason") == "no_tool_call":
            reward = -0.1
        else:
            reward = -0.05

        results.append(
            {
                "eval_type": info["eval_type"],
                "reward": reward,
                "submitted": state.get("submitted", False),
                "turns": turn,
                "done_reason": state.get("done_reason", "max_turns"),
                "invalid_actions": state.get("invalid_action_count", 0),
                "python_exec_count": state.get("python_exec_count", 0),
            }
        )

        logger.info(
            "  Result: reward=%.4f, submitted=%s, turns=%d, reason=%s",
            reward,
            state.get("submitted"),
            turn,
            state.get("done_reason"),
        )

    return results


# ---------------------------------------------------------------------------
# vLLM backend: use verifiers evaluate() with OpenAI-compatible API
# ---------------------------------------------------------------------------


async def _run_vllm_rollouts(
    env: SregEnv,
    ds,
    model_name: str,
    api_url: str,
    api_key: str,
    max_concurrent: int,
) -> list[dict]:
    """Run rollouts using vLLM via verifiers evaluate()."""
    client_config = vf.ClientConfig(
        client_type="openai_chat_completions",
        api_base_url=api_url,
        api_key_var="__INLINE__",
    )
    os.environ["__INLINE__"] = api_key

    sampling_args = vf.SamplingArgs(
        temperature=0.7,
        top_p=0.9,
        max_tokens=1024,
    )

    gen_outputs = await env.evaluate(
        client=client_config,
        model=model_name,
        sampling_args=sampling_args,
        max_concurrent=max_concurrent,
    )

    outputs = list(gen_outputs.get("outputs", []))
    results = []
    for o in outputs:
        if isinstance(o, dict):
            results.append(
                {
                    "reward": o.get("score", 0.0),
                    "submitted": bool(o.get("metrics", {}).get("_submitted_metric", 0)),
                    "turns": int(o.get("metrics", {}).get("_turns_metric", 0)),
                }
            )
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def detect_backend() -> str:
    """Auto-detect inference backend. Linux -> vllm, else -> transformers."""
    if platform.system() == "Linux":
        return "vllm"
    return "transformers"


def resolve_api_key(args: argparse.Namespace) -> str:
    """Resolve API key from args or environment."""
    if args.api_key:
        return args.api_key
    for var in [
        "VLLM_API_KEY",
        "AZURE_INFERENCE_CREDENTIAL",
        "OPENAI_API_KEY",
    ]:
        val = os.environ.get(var)
        if val:
            return val
    return "no-key"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SREG dry run with real model")
    p.add_argument(
        "--backend",
        choices=["vllm", "transformers", "auto"],
        default="auto",
        help="Inference backend (default: auto-detect)",
    )
    p.add_argument(
        "--model",
        default="Qwen/Qwen2.5-0.5B-Instruct",
        help="Model name/path",
    )
    p.add_argument(
        "--api-url",
        default="http://localhost:8000/v1",
        help="vLLM API URL (only for vllm backend)",
    )
    p.add_argument("--api-key", default=None, help="API key (for vllm)")
    p.add_argument("--num-srcs", type=int, default=3, help="Number of SRCs to generate")
    p.add_argument("--num-nodes", type=int, default=6, help="Nodes per world")
    p.add_argument("--budget", type=int, default=5, help="Agent budget per episode")
    p.add_argument("--seed", type=int, default=42, help="Base random seed")
    p.add_argument("--max-turns", type=int, default=8, help="Max turns per episode")
    p.add_argument(
        "--max-concurrent",
        type=int,
        default=1,
        help="Max concurrent rollouts (vllm only)",
    )
    p.add_argument(
        "--dataset-only",
        action="store_true",
        help="Just generate dataset, don't run model",
    )
    p.add_argument("--output", default=None, help="Save dataset to this path")
    p.add_argument(
        "--eval-type",
        default=None,
        help="Only include this eval type (e.g. infer_target)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # --- Step 1: Generate dataset ---
    logger.info(
        "Generating dataset: %d SRCs, %d nodes, budget=%d, seed=%d",
        args.num_srcs,
        args.num_nodes,
        args.budget,
        args.seed,
    )

    eval_types = None
    if args.eval_type:
        from sreg.models.task import TaskType

        type_map = {t.value: t for t in TaskType}
        if args.eval_type not in type_map:
            logger.error(
                "Unknown eval type: %s. Options: %s",
                args.eval_type,
                list(type_map.keys()),
            )
            sys.exit(1)
        eval_types = [type_map[args.eval_type]]

    ds = generate_dataset(
        n=args.num_srcs,
        seed=args.seed,
        num_nodes=args.num_nodes,
        budget=args.budget,
        eval_types=eval_types,
    )

    # Show dataset summary
    eval_type_counts: dict[str, int] = {}
    for row in ds:
        info = json.loads(row["info"])
        et = info["eval_type"]
        eval_type_counts[et] = eval_type_counts.get(et, 0) + 1
    print("\n=== Dataset Summary ===")
    print(f"Total rows: {len(ds)}")
    for et, count in sorted(eval_type_counts.items()):
        print(f"  {et}: {count}")

    if args.output:
        ds.save_to_disk(args.output)
        logger.info("Dataset saved to %s", args.output)

    if args.dataset_only:
        print("\n--dataset-only: done.")
        return

    # --- Step 2: Resolve backend ---
    backend = args.backend if args.backend != "auto" else detect_backend()
    print(f"\n=== Backend: {backend} ===")
    print(f"Model: {args.model}")
    print(f"Rollouts: {len(ds)}")
    print(f"Max turns: {args.max_turns}")

    # --- Step 3: Create environment ---
    env = SregEnv(dataset=ds, max_turns=args.max_turns)

    # --- Step 4: Run rollouts ---
    if backend == "transformers":
        results = asyncio.run(_run_transformers_rollouts(env, ds, args.model, args.max_turns))
    elif backend == "vllm":
        api_key = resolve_api_key(args)
        results = asyncio.run(
            _run_vllm_rollouts(
                env,
                ds,
                args.model,
                args.api_url,
                api_key,
                args.max_concurrent,
            )
        )
    else:
        logger.error("Unknown backend: %s", backend)
        sys.exit(1)

    # --- Step 5: Print results ---
    print("\n=== Results ===")
    if not results:
        print("No results.")
        return

    rewards = [r["reward"] for r in results]
    submitted = sum(1 for r in results if r.get("submitted"))
    avg_turns = sum(r.get("turns", 0) for r in results) / len(results)

    print(f"Rollouts: {len(results)}")
    print(f"Mean reward: {sum(rewards) / len(rewards):.4f}")
    print(f"Min/Max: {min(rewards):.4f} / {max(rewards):.4f}")
    print(f"Submitted: {submitted}/{len(results)}")
    print(f"Avg turns: {avg_turns:.1f}")

    # Per eval-type breakdown
    by_type: dict[str, list[float]] = {}
    for r in results:
        et = r.get("eval_type", "unknown")
        by_type.setdefault(et, []).append(r["reward"])

    if len(by_type) > 1:
        print("\nPer eval type:")
        for et, scores in sorted(by_type.items()):
            print(f"  {et}: mean={sum(scores) / len(scores):.4f} (n={len(scores)})")


if __name__ == "__main__":
    main()
