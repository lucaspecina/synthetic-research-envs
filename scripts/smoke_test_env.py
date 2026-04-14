#!/usr/bin/env python3
"""Smoke test: verify SregEnv works end-to-end with a real SRC.

Loads a real src.json, constructs a dataset row, instantiates SregEnv,
calls setup_state, simulates tool calls (python_exec + submit_claims),
and verifies scoring works.

Usage:
    python scripts/smoke_test_env.py test_data/test_src.json

Requires Azure credentials in .env for scoring (compiler + relevance judge).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Setup path and env
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

# Windows compat
from sreg.training._compat import patch_fcntl_if_windows
patch_fcntl_if_windows()


def build_llm_call():
    """Build sync llm_call callback for OIEpisodeRunner (compiler + judge).

    Same pattern as scripts/run_oi.py:build_compiler_llm.
    """
    from openai import OpenAI

    base_url = os.environ.get("AZURE_FOUNDRY_BASE_URL", "")
    api_key = os.environ.get("AZURE_INFERENCE_CREDENTIAL", "")
    model = os.environ.get("AZURE_MODEL", "gpt-5.4")

    if not base_url or not api_key:
        print("ERROR: Azure credentials missing. Set AZURE_FOUNDRY_BASE_URL "
              "and AZURE_INFERENCE_CREDENTIAL in .env")
        sys.exit(1)

    client = OpenAI(base_url=base_url, api_key=api_key)
    print(f"  LLM: {model} @ {base_url[:40]}...")

    def llm_call(messages):
        instructions = messages[0]["content"] if messages else ""
        input_items = [
            {"role": m["role"], "content": m["content"]}
            for m in messages[1:]
        ]
        resp = client.responses.create(
            model=model, instructions=instructions, input=input_items,
        )
        for item in resp.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        return part.text
        return ""

    return llm_call


def build_dataset_row(src: dict, claim_cap: int = 15) -> dict:
    """Build a single HF Dataset-compatible row from a src.json dict."""
    from sreg.training.prompts import render_prompt_from_src

    prompt = render_prompt_from_src(src, claim_cap=claim_cap)
    info = {"src_json": json.dumps(src)}

    return {
        "prompt": prompt,
        "info": json.dumps(info),
        "task": "oi_investigation",
    }


async def run_smoke_test(src_path: str):
    """Run the full smoke test."""
    print(f"\n=== SregEnv Smoke Test ===")
    print(f"SRC: {src_path}")

    # 1. Load SRC
    src = json.load(open(src_path, encoding="utf-8"))
    print(f"  Title: {src['problem'].get('title', '?')}")
    print(f"  SQs: {len(src.get('sub_questions_v2', []))}")

    # 2. Build dataset row
    row = build_dataset_row(src, claim_cap=5)
    print(f"  Prompt: {len(row['prompt'])} messages")

    # 3. Build LLM callback
    print("\nSetting up LLM callback...")
    llm_call = build_llm_call()

    # 4. Create SregEnv with single-row dataset
    print("\nCreating SregEnv...")
    from datasets import Dataset
    from sreg.training.env import SregEnv

    ds = Dataset.from_dict({
        "prompt": [row["prompt"]],
        "info": [row["info"]],
        "task": [row["task"]],
    })

    env = SregEnv(
        dataset=ds,
        max_turns=10,
        claim_cap=5,
        llm_call=llm_call,
        n_mc=10_000,  # fewer MC samples for speed
    )
    print(f"  Tools: {list(env.tool_map.keys())}")
    print(f"  Max turns: {env.max_turns}")

    # 5. Build state manually (simulating what verifiers does)
    print("\nCalling setup_state...")
    from verifiers.types import State

    state = State()
    state["input"] = {
        "prompt": row["prompt"],
        "info": row["info"],
        "task": row["task"],
        "example_id": 0,
    }
    # State forwards input fields
    state["prompt"] = row["prompt"]
    state["info"] = row["info"]
    state["task"] = row["task"]

    t0 = time.time()
    state = await env.setup_state(state)
    print(f"  setup_state: {time.time() - t0:.2f}s")
    print(f"  runner: {'OK' if state.get('runner') else 'MISSING'}")
    print(f"  submitted: {state.get('submitted')}")

    # 6. Simulate python_exec: load first artifact
    runner = state["runner"]
    first_artifact = None
    for a in src["problem"].get("data_assets", []):
        if a.get("artifact_id"):
            first_artifact = a["artifact_id"]
            break

    if first_artifact:
        print(f"\nCalling python_exec: load_artifact('{first_artifact}')...")
        from sreg.training.tools import python_exec

        result = await python_exec(
            code=f"df = load_artifact('{first_artifact}')\nprint(df.shape)\nprint(df.columns.tolist())",
            runner=runner,
            state=state,
        )
        print(f"  Result: {result[:200]}")
    else:
        print("\n  WARNING: no artifacts found, skipping python_exec")

    # 7. Simulate submit_claims with a simple valid claim
    print("\nCalling submit_claims...")
    from sreg.training.tools import submit_claims

    # Build a minimal valid claim
    test_claims = [
        {
            "claim_id": "c1",
            "claim_text": "There appears to be a positive association between the main variables in the study based on initial data examination.",
            "focus_variables": src["problem"].get("data_assets", [{}])[0].get("columns", ["x"])[:2] if src["problem"].get("data_assets") else ["x"],
            "confidence": 0.5,
            "evidence_basis": [
                {
                    "artifact_id": first_artifact or "dataset_bg",
                    "rationale": "Initial examination of the main dataset shows this pattern in the raw data.",
                }
            ],
        }
    ]

    t0 = time.time()
    result = await submit_claims(
        claims=test_claims,
        runner=runner,
        state=state,
    )
    scoring_time = time.time() - t0
    print(f"  Result: {result}")
    print(f"  Scoring time: {scoring_time:.2f}s")

    # 8. Verify state
    print(f"\n=== Results ===")
    print(f"  submitted: {state.get('submitted')}")
    print(f"  submit_error: {state.get('submit_error')}")
    score = state.get("score")
    if score:
        print(f"  score.total: {score.total:.4f}")
        print(f"  score.correctness: {score.correctness:.4f}")
        print(f"  score.weighted_coverage: {score.weighted_coverage:.4f}")
        print(f"  score.coverage: {score.coverage:.4f}")
    else:
        print("  score: None (scoring failed)")

    # 9. Verify reward
    from sreg.training.reward import terminal_reward
    reward = terminal_reward(state)
    print(f"  reward: {reward:.4f}")
    print(f"  reward is finite float: {isinstance(reward, float) and reward == reward}")

    # Summary
    print(f"\n=== Smoke Test {'PASSED' if state.get('submitted') else 'FAILED'} ===")
    return state.get("submitted", False)


def main():
    src_path = sys.argv[1] if len(sys.argv) > 1 else "test_data/test_src.json"
    if not Path(src_path).exists():
        print(f"ERROR: {src_path} not found")
        sys.exit(1)

    success = asyncio.run(run_smoke_test(src_path))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
