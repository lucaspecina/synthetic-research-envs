"""Tests for SregEnv (verifiers-compatible RL environment)."""

import asyncio
import json

from sreg.models.episode import ActionDef
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool
from sreg.training._compat import patch_fcntl_if_windows

patch_fcntl_if_windows()

import verifiers as vf  # noqa: E402
from datasets import Dataset  # noqa: E402

from sreg.training.env import (  # noqa: E402
    SregEnv,
    _invalid_actions_metric,
    _submitted_metric,
    _terminal_reward,
    _turns_metric,
)
from sreg.training.types import SubmitPayload  # noqa: E402


def _make_info_dict(seed=42):
    """Create a realistic info dict as would appear in a HuggingFace dataset row."""
    gen = WorldGenTool()
    world = gen.generate(WorldGenConfig(seed=seed, num_nodes=6, edge_strength=0.7))
    solver = ExactBayesSolver(world)
    true_state = solver.sample_state(seed=seed)

    ep_gen = EpisodeGenTool()
    episode = ep_gen.generate(world, EpisodeGenConfig(budget=4, seed=seed))

    # Add action_defs (rich mode)
    for node_name in episode.available_nodes:
        cost = episode.node_costs.get(node_name, 1)
        episode.action_defs.append(
            ActionDef(
                id=f"act_{node_name}",
                action_type="observe",
                nodes=[node_name],
                cost=cost,
            )
        )

    from sreg.models.world import NodeType

    target = next(n for n in world.nodes if n.type == NodeType.TARGET)
    prior = solver.posterior(target.name, {})

    return {
        "world_json": world.model_dump_json(),
        "episode_json": episode.model_dump_json(),
        "true_state": json.dumps(true_state),
        "eval_type": "infer_target",
        "correct_answer": {s: round(p, 6) for s, p in prior.items()},
    }


def _make_dummy_dataset(seed=42) -> Dataset:
    """Create a minimal HF Dataset for SregEnv tests."""
    info = _make_info_dict(seed=seed)
    row = {
        "prompt": [
            {"role": "system", "content": "You are a researcher."},
            {"role": "user", "content": "Investigate the variables."},
        ],
        "info": info,
    }
    return Dataset.from_list([row])


def _make_env(max_turns=5, **kwargs) -> SregEnv:
    """Create a SregEnv with a dummy dataset for testing."""
    ds = _make_dummy_dataset()
    return SregEnv(dataset=ds, max_turns=max_turns, **kwargs)


def _make_state_with_info(seed=42) -> vf.State:
    """Create a vf.State with info populated (simulates what verifiers provides)."""
    state = vf.State()
    state["info"] = _make_info_dict(seed=seed)
    return state


# ── Terminal reward tests ──


class TestTerminalReward:
    def test_submitted_correct_distribution(self):
        """Good distribution submission should give positive reward."""
        correct_answer = {"low": 0.3, "high": 0.7}
        payload = SubmitPayload(distribution=correct_answer)
        state = {
            "submitted": True,
            "submission_payload": payload.model_dump(),
            "eval_type": "infer_target",
            "correct_answer": correct_answer,
            "kl_cutoff": 5.0,
        }
        reward = _terminal_reward(state)
        assert reward > 0.5  # Exact match should give high reward

    def test_submitted_wrong_distribution(self):
        """Completely wrong distribution should give low reward."""
        correct_answer = {"low": 0.1, "high": 0.9}
        wrong_answer = {"low": 0.9, "high": 0.1}
        payload = SubmitPayload(distribution=wrong_answer)
        state = {
            "submitted": True,
            "submission_payload": payload.model_dump(),
            "eval_type": "infer_target",
            "correct_answer": correct_answer,
            "kl_cutoff": 5.0,
        }
        reward = _terminal_reward(state)
        assert reward < 0.5

    def test_submitted_no_payload(self):
        """Submitted but no payload should give 0."""
        state = {"submitted": True, "submission_payload": None}
        reward = _terminal_reward(state)
        assert reward == 0.0

    def test_not_submitted_no_tool_call(self):
        state = {"submitted": False, "done_reason": "no_tool_call"}
        reward = _terminal_reward(state)
        assert reward == -0.1

    def test_not_submitted_budget_exhausted(self):
        state = {"submitted": False, "done_reason": "budget_exhausted"}
        reward = _terminal_reward(state)
        assert reward == -0.05

    def test_not_submitted_max_turns(self):
        state = {"submitted": False, "done_reason": "max_turns"}
        reward = _terminal_reward(state)
        assert reward == -0.05

    def test_not_submitted_unknown(self):
        state = {"submitted": False, "done_reason": "unknown"}
        reward = _terminal_reward(state)
        assert reward == 0.0

    def test_correct_choice_submit(self):
        payload = SubmitPayload(choice="yes")
        state = {
            "submitted": True,
            "submission_payload": payload.model_dump(),
            "eval_type": "should_condition",
            "correct_answer": "yes",
            "kl_cutoff": 5.0,
        }
        reward = _terminal_reward(state)
        assert reward == 1.0

    def test_wrong_choice_submit(self):
        payload = SubmitPayload(choice="no")
        state = {
            "submitted": True,
            "submission_payload": payload.model_dump(),
            "eval_type": "should_condition",
            "correct_answer": "yes",
            "kl_cutoff": 5.0,
        }
        reward = _terminal_reward(state)
        assert reward == 0.0


# ── Metric function tests ──


class TestMetrics:
    def test_submitted_metric_true(self):
        assert _submitted_metric({"submitted": True}) == 1.0

    def test_submitted_metric_false(self):
        assert _submitted_metric({"submitted": False}) == 0.0

    def test_submitted_metric_missing(self):
        assert _submitted_metric({}) == 0.0

    def test_turns_metric(self):
        state = {"tool_trace": [{"tool": "a"}, {"tool": "b"}, {"tool": "c"}]}
        assert _turns_metric(state) == 3.0

    def test_turns_metric_empty(self):
        assert _turns_metric({"tool_trace": []}) == 0.0
        assert _turns_metric({}) == 0.0

    def test_invalid_actions_metric(self):
        assert _invalid_actions_metric({"invalid_action_count": 5}) == 5.0
        assert _invalid_actions_metric({}) == 0.0


# ── SregEnv instantiation ──


class TestSregEnvInit:
    def test_creates_env(self):
        env = _make_env(max_turns=5)
        assert isinstance(env, vf.StatefulToolEnv)

    def test_default_max_turns(self):
        env = _make_env(max_turns=10)
        assert env.max_turns == 10

    def test_tool_defs_registered(self):
        env = _make_env()
        tool_names = [t.name for t in env.tool_defs]
        assert "research_action" in tool_names
        assert "submit" in tool_names


# ── SregEnv.setup_state ──


class TestSregEnvSetupState:
    def test_setup_state_initializes_runner(self):
        env = _make_env()
        state = _make_state_with_info()
        state = asyncio.get_event_loop().run_until_complete(env.setup_state(state))

        from sreg.env.episode import EpisodeRunner

        assert isinstance(state["runner"], EpisodeRunner)
        assert state["eval_type"] == "infer_target"
        assert state["submitted"] is False
        assert state["done_reason"] is None
        assert state["invalid_action_count"] == 0
        assert state["budget_used"] == 0
        assert state["tool_trace"] == []
        assert isinstance(state["correct_answer"], dict)

    def test_setup_state_true_state_as_string(self):
        """true_state can be a JSON string (from HF dataset serialization)."""
        env = _make_env()
        state = _make_state_with_info()
        assert isinstance(state["info"]["true_state"], str)
        state = asyncio.get_event_loop().run_until_complete(env.setup_state(state))
        assert state["runner"] is not None

    def test_setup_state_true_state_as_dict(self):
        """true_state can also be a dict (pre-parsed)."""
        env = _make_env()
        state = _make_state_with_info()
        state["info"]["true_state"] = json.loads(state["info"]["true_state"])
        state = asyncio.get_event_loop().run_until_complete(env.setup_state(state))
        assert state["runner"] is not None

    def test_setup_state_kl_cutoff(self):
        env = _make_env(kl_cutoff=3.0)
        state = _make_state_with_info()
        state = asyncio.get_event_loop().run_until_complete(env.setup_state(state))
        assert state["kl_cutoff"] == 3.0


# ── SregEnv.update_tool_args ──


class TestSregEnvUpdateToolArgs:
    def test_injects_runner_and_state(self):
        env = _make_env()
        state = _make_state_with_info()
        state = asyncio.get_event_loop().run_until_complete(env.setup_state(state))

        tool_args = {"action_id": "act_something"}
        updated = env.update_tool_args("research_action", tool_args, [], state)

        assert "runner" in updated
        assert "state" in updated
        assert updated["action_id"] == "act_something"
        assert updated["runner"] is state["runner"]
        assert updated["state"] is state


# ── SregEnv.is_completed ──


class TestSregEnvIsCompleted:
    def test_not_completed_initially(self):
        env = _make_env()
        state = _make_state_with_info()
        state = asyncio.get_event_loop().run_until_complete(env.setup_state(state))
        runner = state["runner"]
        assert runner.budget_remaining > 0
        assert state["submitted"] is False

    def test_budget_zero_does_not_end_episode(self):
        """Budget=0 should NOT stop the episode — agent can still submit."""
        env = _make_env()
        state = _make_state_with_info()
        state = asyncio.get_event_loop().run_until_complete(env.setup_state(state))

        runner = state["runner"]
        runner._budget_remaining = 0
        # Need trajectory for super().is_completed() max_turns check
        state["trajectory"] = []

        completed = asyncio.get_event_loop().run_until_complete(env.is_completed(state))
        # Not completed because max_turns not reached and no_tools_called not triggered
        assert completed is False

    def test_max_turns_sets_correct_done_reason(self):
        """When max_turns is hit, done_reason should be 'max_turns' not 'no_tool_call'."""
        import time

        env = _make_env(max_turns=2)
        state = _make_state_with_info()
        state = asyncio.get_event_loop().run_until_complete(env.setup_state(state))

        # Simulate trajectory at max_turns + timing (required by verifiers internals)
        state["trajectory"] = [{"role": "assistant"}, {"role": "tool"}]
        state["timing"] = {"start_time": time.time()}

        completed = asyncio.get_event_loop().run_until_complete(env.is_completed(state))
        assert completed is True
        assert state["done_reason"] == "max_turns"
