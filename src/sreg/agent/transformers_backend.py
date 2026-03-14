"""HuggingFace transformers backend for local model inference.

Provides loading, generation, and Hermes tool-call parsing for local models
(e.g., Qwen). This is the fallback when vLLM is not available (Windows, no GPU
server). Adapted from worktree rl-env-verifiers (dry_run.py).

Usage:
    from sreg.agent.transformers_backend import (
        load_transformers_model,
        solve_question_transformers,
    )
    model, tokenizer = load_transformers_model("Qwen/Qwen2.5-0.5B-Instruct")
    answer = solve_question_transformers(model, tokenizer, system, question, ...)
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Callable

logger = logging.getLogger(__name__)


def load_transformers_model(model_name: str):
    """Load a HuggingFace model and tokenizer for local inference.

    Returns (model, tokenizer). Requires torch and transformers installed.
    """
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


def generate_with_transformers(model, tokenizer, messages, tools=None, max_tokens=1024):
    """Generate a response using HuggingFace transformers with tool support.

    Uses the model's chat template (Qwen uses Hermes format for tool calling).
    Returns raw output string (needs parsing for tool calls).
    """
    import torch

    template_kwargs = {
        "tokenize": False,
        "add_generation_prompt": True,
    }
    if tools:
        template_kwargs["tools"] = tools

    text = tokenizer.apply_chat_template(messages, **template_kwargs)

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


def parse_hermes_tool_calls(raw_output: str) -> tuple[str, list[dict]]:
    """Parse Hermes-style tool calls from model output.

    Qwen models use: <tool_call>{"name":..., "arguments":...}</tool_call>
    Returns (text_content, list_of_tool_call_dicts).
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
            tool_calls.append({
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": parsed.get("name", ""),
                "arguments": json.dumps(parsed.get("arguments", {})),
            })
        except json.JSONDecodeError:
            text_parts.append(f"[malformed tool call: {call_json[:100]}]")

    text_parts.append(remaining)
    text_content = "".join(text_parts).strip()

    # Clean special tokens
    for token in ["<|im_end|>", "<|endoftext|>", "<|im_start|>"]:
        text_content = text_content.replace(token, "").strip()

    return text_content, tool_calls


def solve_question_transformers(
    model,
    tokenizer,
    system_prompt: str,
    user_prompt: str,
    tools: list[dict] | None = None,
    tool_handler: Callable[[str, dict], str] | None = None,
    max_iterations: int = 10,
    max_tokens: int = 1024,
) -> str:
    """Solve a question using local transformers model with tool calling.

    Same interface as solve_question (engine.py) but uses HuggingFace
    transformers instead of OpenAI API. Tool calls parsed from Hermes format.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # Convert tools to function format for chat template
    openai_tools = None
    if tools:
        openai_tools = []
        for t in tools:
            if "function" in t:
                openai_tools.append(t["function"])
            else:
                openai_tools.append(t)

    for _ in range(max_iterations):
        raw = generate_with_transformers(
            model, tokenizer, messages, tools=openai_tools, max_tokens=max_tokens
        )
        text_content, tool_calls = parse_hermes_tool_calls(raw)

        messages.append({"role": "assistant", "content": text_content})

        if not tool_calls or tool_handler is None:
            break

        for tc in tool_calls:
            try:
                args = json.loads(tc["arguments"])
            except json.JSONDecodeError:
                args = {}

            result_str = tool_handler(tc["name"], args)
            messages.append({
                "role": "tool",
                "name": tc["name"],
                "content": result_str,
            })

    # Return last assistant text
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            return msg["content"]

    return ""


__all__ = [
    "generate_with_transformers",
    "load_transformers_model",
    "parse_hermes_tool_calls",
    "solve_question_transformers",
]
