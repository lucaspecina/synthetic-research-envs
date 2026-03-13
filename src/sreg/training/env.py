"""SregEnv: SREG as a verifiers-compatible RL environment.

Wraps SREG's EpisodeRunner as a StatefulToolEnv for training with
verifiers/prime-rl. Each rollout = one SRC (research case).

Usage:
    from sreg.training.env import SregEnv
    env = SregEnv(dataset=hf_dataset, max_turns=10)
    # Then use with vf.RLTrainer or vf-eval
"""

from __future__ import annotations

from sreg.training._compat import patch_fcntl_if_windows

patch_fcntl_if_windows()

import json  # noqa: E402
from typing import Any  # noqa: E402

import verifiers as vf  # noqa: E402

from sreg.env.episode import EpisodeRunner  # noqa: E402
from sreg.models.episode import Episode, Observation  # noqa: E402
from sreg.models.world import World  # noqa: E402
from sreg.training.rubric import score_submission  # noqa: E402
from sreg.training.tools import research_action, submit  # noqa: E402
from sreg.training.types import SubmitPayload  # noqa: E402


def _terminal_reward(state: dict, **kwargs: Any) -> float:
    """Compute terminal reward from submission.

    This is the SINGLE authority for reward in training.
    """
    if state.get("submitted"):
        payload_data = state.get("submission_payload")
        if payload_data is None:
            return 0.0
        payload = SubmitPayload(**payload_data)
        eval_type = state.get("eval_type", "")
        correct_answer = state.get("correct_answer", {})
        kl_cutoff = state.get("kl_cutoff", 5.0)
        return score_submission(payload, eval_type, correct_answer, kl_cutoff=kl_cutoff)

    # Not submitted — penalize based on reason
    done_reason = state.get("done_reason", "unknown")
    if done_reason == "no_tool_call":
        return -0.1
    if done_reason in ("budget_exhausted", "max_turns"):
        return -0.05
    return 0.0


def _submitted_metric(state: dict, **kwargs: Any) -> float:
    return 1.0 if state.get("submitted", False) else 0.0


def _turns_metric(state: dict, **kwargs: Any) -> float:
    return float(len(state.get("tool_trace", [])))


def _invalid_actions_metric(state: dict, **kwargs: Any) -> float:
    return float(state.get("invalid_action_count", 0))


def _build_rubric() -> vf.Rubric:
    rubric = vf.Rubric(
        funcs=[_terminal_reward],
        weights=[1.0],
    )
    rubric.add_metric(_submitted_metric)
    rubric.add_metric(_turns_metric)
    rubric.add_metric(_invalid_actions_metric)
    return rubric


class SregEnv(vf.StatefulToolEnv):
    """SREG research environment for RL training.

    Each rollout corresponds to one SRC. The agent uses research_action
    to gather evidence and submit to provide a final answer.

    Dataset rows must have:
        - prompt: list of message dicts (system + user with case description)
        - info: dict with keys:
            - world_json: serialized World model (JSON string)
            - episode_json: serialized Episode model (JSON string)
            - true_state: dict[str, str] (hidden ground truth)
            - eval_type: str (one of 9 eval types)
            - correct_answer: dict (ground truth for scoring)
    """

    def __init__(
        self,
        max_turns: int = 10,
        kl_cutoff: float = 5.0,
        **kwargs: Any,
    ):
        self._kl_cutoff = kl_cutoff

        # Pass tools=[] to avoid schema generation for unserializable types
        # (EpisodeRunner). Register tools via add_tool with args_to_skip instead.
        super().__init__(
            rubric=_build_rubric(),
            tools=[],
            max_turns=max_turns,
            **kwargs,
        )
        self.add_tool(research_action, args_to_skip=["runner", "state"])
        self.add_tool(submit, args_to_skip=["runner", "state"])

    async def setup_state(self, state: vf.State) -> vf.State:
        state = await super().setup_state(state)

        info = state.get("info", {})

        # Deserialize world and episode
        world = World.model_validate_json(info["world_json"])
        episode = Episode.model_validate_json(info["episode_json"])
        true_state = info["true_state"]
        if isinstance(true_state, str):
            true_state = json.loads(true_state)

        runner = EpisodeRunner(world=world, episode=episode, true_state=true_state)

        state["runner"] = runner
        state["eval_type"] = info["eval_type"]
        state["correct_answer"] = info["correct_answer"]
        state["kl_cutoff"] = self._kl_cutoff
        state["submitted"] = False
        state["submission_payload"] = None
        state["done_reason"] = None
        state["invalid_action_count"] = 0
        state["budget_used"] = 0
        state["tool_trace"] = []
        return state

    def update_tool_args(
        self,
        tool_name: str,
        tool_args: dict,
        messages: Any,
        state: vf.State,
        **kwargs: Any,
    ) -> dict:
        return {
            **tool_args,
            "runner": state.get("runner"),
            "state": state,
        }

    async def is_completed(self, state: vf.State, **kwargs: Any) -> bool:
        # Note: budget exhaustion is NOT a stop condition. The agent can always
        # submit (costs 0 budget). Budget only gates research_action, which
        # returns an error when budget is insufficient.

        completed = await super().is_completed(state, **kwargs)
        if completed and not state.get("submitted") and state.get("done_reason") is None:
            # Distinguish max_turns from no_tool_call
            trajectory = state.get("trajectory", [])
            if self.max_turns > 0 and len(trajectory) >= self.max_turns:
                state["done_reason"] = "max_turns"
            else:
                state["done_reason"] = "no_tool_call"
        return completed


def _deserialize_observations(obs_list: list[dict]) -> list[Observation]:
    """Helper to deserialize observation dicts."""
    return [Observation(**o) for o in obs_list]
