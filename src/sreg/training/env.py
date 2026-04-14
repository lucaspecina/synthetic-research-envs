"""SregEnv: SREG as a verifiers-compatible RL environment.

Wraps OIEpisodeRunner as a StatefulToolEnv for training with
verifiers/GRPO. Each rollout = one frozen SRC (research case).

The scoring pipeline (compiler + verifier + relevance judge) runs
inside the submit_claims tool call. The reward function reads the
result from state — no re-computation.

Usage:
    from sreg.training.env import SregEnv
    env = SregEnv(dataset=hf_dataset, llm_call=my_llm_callback)
"""

from __future__ import annotations

from sreg.training._compat import patch_fcntl_if_windows

patch_fcntl_if_windows()

import hashlib  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
from threading import Lock  # noqa: E402
from typing import Any  # noqa: E402

import verifiers as vf  # noqa: E402

from sreg.training.reward import (
    step_count_metric,
    submit_error_metric,
    submitted_metric,
    terminal_reward,
)
from sreg.training.tools import python_exec, submit_claims, think

logger = logging.getLogger(__name__)

# Module-level world cache: avoids reconstructing SCMWorld for each
# rollout when multiple rollouts share the same SRC (GRPO G>1).
_world_cache: dict[str, Any] = {}
_world_cache_lock = Lock()
_MAX_CACHE_SIZE = 128


def _cache_key(scm_construct_json: str) -> str:
    """Stable hash for scm_construct args."""
    return hashlib.sha256(scm_construct_json.encode()).hexdigest()[:16]


def _get_or_build_world(scm_construct_json: str):
    """Get world from cache or reconstruct from scm_construct args."""
    key = _cache_key(scm_construct_json)

    with _world_cache_lock:
        if key in _world_cache:
            return _world_cache[key]

    # Reconstruct outside lock (CPU-bound, ~50-100ms)
    scm_args = json.loads(scm_construct_json)
    world = _reconstruct_world_from_args(scm_args)

    with _world_cache_lock:
        if len(_world_cache) >= _MAX_CACHE_SIZE:
            # Evict oldest entry (simple FIFO)
            oldest = next(iter(_world_cache))
            del _world_cache[oldest]
        _world_cache[key] = world

    return world


def _reconstruct_world_from_args(scm_args: dict):
    """Reconstruct SCMWorld from scm_construct args.

    Adapted from scripts/run_oi.py:reconstruct_world.
    """
    from sreg.models.scm_spec import SCMSpec
    from sreg.tools.scm_world_gen import SCMWorldGenTool

    # Handle edge format: list of dicts -> list of tuples
    if scm_args.get("edges") and isinstance(scm_args["edges"][0], dict):
        scm_args = dict(scm_args)  # don't mutate cached input
        scm_args["edges"] = [(e["from"], e["to"]) for e in scm_args["edges"]]

    spec = SCMSpec(**scm_args)
    gen = SCMWorldGenTool()
    return gen.generate(spec, seed=42)


def _extract_scm_construct(src: dict) -> dict:
    """Extract scm_construct args from src.json process data."""
    for tc in src.get("process", {}).get("tools_called", []):
        if tc.get("tool") == "scm_construct":
            res = tc.get("result", {})
            if "world_id" in res or "error" not in res:
                return tc["args"]
    # Fallback: take first scm_construct call
    for tc in src.get("process", {}).get("tools_called", []):
        if tc.get("tool") == "scm_construct":
            return tc["args"]
    raise ValueError("No scm_construct call found in src.json")


def _override_tool_schema(
    env: vf.StatefulToolEnv, name: str, oai_schema: dict
) -> None:
    """Replace auto-generated tool schema with a custom one.

    Args:
        env: The environment with tool_defs to modify.
        name: Tool name to replace.
        oai_schema: OpenAI API format schema ({"type": "function", "function": {...}}).

    Asserts the replacement happened to catch API changes early.
    """
    from verifiers.types import Tool

    # Convert OpenAI format to verifiers Tool
    fn = oai_schema["function"]
    new_tool = Tool(
        name=fn["name"],
        description=fn.get("description", ""),
        parameters=fn.get("parameters", {}),
    )

    replaced = False
    for i, td in enumerate(env.tool_defs):
        td_name = td.name if hasattr(td, "name") else None
        if td_name == name:
            env.tool_defs[i] = new_tool
            replaced = True
            break
    assert replaced, f"Failed to replace tool schema for '{name}'"


class SregEnv(vf.StatefulToolEnv):
    """SREG research environment for RL training.

    Each rollout corresponds to one frozen SRC. The agent uses
    python_exec to analyze data, think to reason, and submit_claims
    to report findings. Scoring uses the full OI pipeline:
    compiler (LLM) + verifier (deterministic) + relevance judge (LLM).

    Dataset rows must have:
        prompt: list of message dicts (system + user with case description)
        info: JSON string or dict with:
            src_json: full src.json content (string or dict)
            seed: random seed (default 42)
            n_mc: Monte Carlo samples for verification (default 20000)
    """

    def __init__(
        self,
        *,
        max_turns: int = 15,
        claim_cap: int = 15,
        llm_call: Any | None = None,
        n_mc: int = 20_000,
        **kwargs: Any,
    ):
        self._claim_cap = claim_cap
        self._llm_call = llm_call
        self._default_n_mc = n_mc

        # Build rubric: terminal reward + tracking metrics
        rubric = vf.Rubric(funcs=[terminal_reward], weights=[1.0])
        rubric.add_metric(submitted_metric)
        rubric.add_metric(step_count_metric)
        rubric.add_metric(submit_error_metric)

        super().__init__(
            rubric=rubric,
            tools=[],
            max_turns=max_turns,
            **kwargs,
        )

        # Register tools with hidden args
        self.add_tool(python_exec, args_to_skip=["runner", "state"])
        self.add_tool(think, args_to_skip=["state"])
        self.add_tool(submit_claims, args_to_skip=["runner", "state"])

        # Replace submit_claims auto-schema with detailed version
        from sreg.tools.oi_driver import build_oi_solver_tools

        oi_schemas = build_oi_solver_tools(claim_cap)
        submit_schema = next(
            s for s in oi_schemas if s["function"]["name"] == "submit_claims"
        )
        _override_tool_schema(self, "submit_claims", submit_schema)

    async def setup_state(self, state: vf.State, **kwargs) -> vf.State:
        """Initialize per-rollout state from the dataset row.

        Reconstructs SCMWorld (cached), builds OIEpisodeRunner,
        loads pre-grounded sub-questions.
        """
        state = await super().setup_state(state, **kwargs)

        info = state.get("info", {})
        if isinstance(info, str):
            info = json.loads(info)

        # Parse src.json (may be nested string or dict)
        src = info.get("src_json", {})
        if isinstance(src, str):
            src = json.loads(src)

        # Reconstruct world (cached by scm_construct hash)
        scm_args = _extract_scm_construct(src)
        scm_json = json.dumps(scm_args, sort_keys=True)
        world = _get_or_build_world(scm_json)

        # Build problem
        from sreg.models.research_problem import ResearchProblem

        problem = ResearchProblem(**src["problem"])

        # Load pre-grounded sub-questions
        from sreg.models.open_investigation import load_sub_questions_v2_robust

        sqs_v2_raw = src.get("sub_questions_v2", [])
        load_result = load_sub_questions_v2_robust(sqs_v2_raw)
        sqs_v2 = load_result.loaded
        if not sqs_v2:
            raise ValueError(
                "No valid sub_questions_v2 in SRC. Cannot score without SQs."
            )

        # Build runner
        from sreg.tools.oi_runner import OIEpisodeRunner

        seed = info.get("seed", 42)
        n_mc = info.get("n_mc", self._default_n_mc)

        runner = OIEpisodeRunner(
            problem,
            world,
            seed=seed,
            n_mc=n_mc,
            llm_call=self._llm_call,
            claim_cap=self._claim_cap,
        )
        runner.set_subquestions_v2(sqs_v2)

        # Per-rollout state
        state["runner"] = runner
        state["submitted"] = False
        state["submit_error"] = None
        state["score"] = None
        state["step_count"] = 0

        return state

    def update_tool_args(
        self,
        tool_name: str,
        tool_args: dict,
        messages: Any,
        state: vf.State,
        **kwargs: Any,
    ) -> dict:
        """Inject hidden args (runner, state) into tool calls."""
        updated = dict(tool_args)
        updated["state"] = state

        if tool_name in ("python_exec", "submit_claims"):
            updated["runner"] = state.get("runner")

        return updated


__all__ = ["SregEnv"]
