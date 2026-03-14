"""Integration test: full rollout simulation without LLM.

Simulates exactly what verifiers does during a GRPO rollout:
  1. Create HF dataset from a real SRC
  2. SregEnv.setup_state() — deserialize world, create runner
  3. research_action() calls — gather evidence
  4. submit() — provide final answer
  5. Rubric scoring — compute reward

This proves all pieces connect end-to-end.
"""

import asyncio
import json

from sreg.models.episode import ActionDef
from sreg.models.world import NodeType
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool
from sreg.training._compat import patch_fcntl_if_windows

patch_fcntl_if_windows()

import verifiers as vf  # noqa: E402
from datasets import Dataset  # noqa: E402

from sreg.training.env import SregEnv, _terminal_reward  # noqa: E402
from sreg.training.tools import research_action, submit  # noqa: E402


def _build_src_dataset(seed=42) -> tuple[Dataset, dict]:
    """Build a 1-row HF Dataset from a real SRC. Returns (dataset, metadata)."""
    gen = WorldGenTool()
    world = gen.generate(WorldGenConfig(seed=seed, num_nodes=8, edge_strength=0.6))
    solver = ExactBayesSolver(world)
    true_state = solver.sample_state(seed=seed)

    ep_gen = EpisodeGenTool()
    episode = ep_gen.generate(world, EpisodeGenConfig(budget=4, seed=seed))

    # Rich action_defs
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

    target = next(n for n in world.nodes if n.type == NodeType.TARGET)
    prior = solver.posterior(target.name, {})
    correct_answer = {s: round(p, 6) for s, p in prior.items()}

    info = {
        "world_json": world.model_dump_json(),
        "episode_json": episode.model_dump_json(),
        "true_state": json.dumps(true_state),
        "eval_type": "infer_target",
        "correct_answer": correct_answer,
    }

    row = {
        "prompt": [
            {"role": "system", "content": "You are a researcher."},
            {"role": "user", "content": f"Investigate the target variable '{target.name}'."},
        ],
        "info": info,
    }

    metadata = {
        "target": target.name,
        "correct_answer": correct_answer,
        "available_actions": [ad.id for ad in episode.action_defs],
        "budget": episode.budget,
        "num_nodes": len(world.nodes),
    }

    return Dataset.from_list([row]), metadata


class TestFullRolloutSimulation:
    """Simulates a complete verifiers rollout manually."""

    def test_observe_then_submit_correct(self):
        """Agent observes 2 nodes, then submits the correct answer. Should get high reward."""
        ds, meta = _build_src_dataset(seed=42)
        env = SregEnv(dataset=ds, max_turns=10)

        # Step 1: setup_state (what verifiers does at rollout start)
        state = vf.State()
        state["info"] = ds[0]["info"]
        state = asyncio.get_event_loop().run_until_complete(env.setup_state(state))

        runner = state["runner"]
        assert runner is not None
        assert runner.budget_remaining == meta["budget"]
        assert state["eval_type"] == "infer_target"

        # Step 2: research_action calls (simulating model tool calls)
        actions_used = meta["available_actions"][:2]
        for action_id in actions_used:
            result = asyncio.get_event_loop().run_until_complete(
                research_action(action_id=action_id, runner=runner, state=state)
            )
            assert "Error" not in result, f"research_action failed: {result}"
            assert "Budget remaining" in result

        assert state["budget_used"] > 0
        assert len(state["tool_trace"]) == 2

        # Step 3: submit correct answer
        correct_json = json.dumps(meta["correct_answer"])
        result = asyncio.get_event_loop().run_until_complete(
            submit(distribution=correct_json, state=state)
        )
        assert "submitted" in result.lower() or "complete" in result.lower()
        assert state["submitted"] is True
        assert state["done_reason"] == "submit"

        # Step 4: compute reward (what rubric does)
        reward = _terminal_reward(state)
        assert reward > 0.9, f"Correct answer should give reward > 0.9, got {reward}"

    def test_observe_then_submit_wrong(self):
        """Agent submits a completely wrong answer. Should get low reward."""
        ds, meta = _build_src_dataset(seed=42)
        env = SregEnv(dataset=ds, max_turns=10)

        state = vf.State()
        state["info"] = ds[0]["info"]
        state = asyncio.get_event_loop().run_until_complete(env.setup_state(state))
        runner = state["runner"]

        # One observation
        action_id = meta["available_actions"][0]
        asyncio.get_event_loop().run_until_complete(
            research_action(action_id=action_id, runner=runner, state=state)
        )

        # Submit inverted distribution
        correct = meta["correct_answer"]
        states = list(correct.keys())
        # Put all probability on the least likely state
        wrong_dist = {s: 0.0 for s in states}
        min_state = min(correct, key=correct.get)
        wrong_dist[min_state] = 1.0
        asyncio.get_event_loop().run_until_complete(
            submit(distribution=json.dumps(wrong_dist), state=state)
        )
        assert state["submitted"] is True

        reward = _terminal_reward(state)
        assert reward < 0.5, f"Wrong answer should give reward < 0.5, got {reward}"

    def test_no_submit_gets_penalty(self):
        """Agent never submits — should get negative reward."""
        ds, meta = _build_src_dataset(seed=42)
        env = SregEnv(dataset=ds, max_turns=10)

        state = vf.State()
        state["info"] = ds[0]["info"]
        state = asyncio.get_event_loop().run_until_complete(env.setup_state(state))

        # Simulate no_tool_call termination
        state["done_reason"] = "no_tool_call"
        reward = _terminal_reward(state)
        assert reward == -0.1

    def test_budget_zero_allows_submit(self):
        """After exhausting budget, agent can still submit."""
        ds, meta = _build_src_dataset(seed=42)
        env = SregEnv(dataset=ds, max_turns=10)

        state = vf.State()
        state["info"] = ds[0]["info"]
        state = asyncio.get_event_loop().run_until_complete(env.setup_state(state))
        runner = state["runner"]

        # Exhaust budget
        runner._budget_remaining = 0

        # Submit should still work
        result = asyncio.get_event_loop().run_until_complete(
            submit(
                distribution=json.dumps(meta["correct_answer"]),
                state=state,
            )
        )
        assert state["submitted"] is True
        assert "Error" not in result

        reward = _terminal_reward(state)
        assert reward > 0.9

    def test_invalid_json_distribution(self):
        """Model sends malformed JSON — should get error, not crash."""
        ds, _ = _build_src_dataset(seed=42)
        env = SregEnv(dataset=ds, max_turns=10)

        state = vf.State()
        state["info"] = ds[0]["info"]
        state = asyncio.get_event_loop().run_until_complete(env.setup_state(state))

        result = asyncio.get_event_loop().run_until_complete(
            submit(distribution="not valid json{{{", state=state)
        )
        assert "Error" in result
        assert state["submitted"] is False
        assert state["invalid_action_count"] == 1
        # Should be traced
        assert len(state["tool_trace"]) == 1

    def test_full_trace_recorded(self):
        """Verify the complete tool trace is recorded for RL diagnostics."""
        ds, meta = _build_src_dataset(seed=42)
        env = SregEnv(dataset=ds, max_turns=10)

        state = vf.State()
        state["info"] = ds[0]["info"]
        state = asyncio.get_event_loop().run_until_complete(env.setup_state(state))
        runner = state["runner"]

        # 1 valid research_action
        asyncio.get_event_loop().run_until_complete(
            research_action(
                action_id=meta["available_actions"][0], runner=runner, state=state
            )
        )
        # 1 invalid research_action
        asyncio.get_event_loop().run_until_complete(
            research_action(action_id="fake_action", runner=runner, state=state)
        )
        # 1 valid submit
        asyncio.get_event_loop().run_until_complete(
            submit(
                distribution=json.dumps(meta["correct_answer"]),
                state=state,
            )
        )

        assert len(state["tool_trace"]) == 3
        assert state["tool_trace"][0]["ok"] is True
        assert state["tool_trace"][0]["tool"] == "research_action"
        assert state["tool_trace"][1]["ok"] is False
        assert state["tool_trace"][1]["tool"] == "research_action"
        assert state["tool_trace"][2]["ok"] is True
        assert state["tool_trace"][2]["tool"] == "submit"
        assert state["invalid_action_count"] == 1

    def test_choice_eval_type_flow(self):
        """Full flow for a choice-type eval (should_condition)."""
        ds, meta = _build_src_dataset(seed=42)
        env = SregEnv(dataset=ds, max_turns=10)

        state = vf.State()
        state["info"] = ds[0]["info"]
        state = asyncio.get_event_loop().run_until_complete(env.setup_state(state))

        # Override eval_type to should_condition for this test
        state["eval_type"] = "should_condition"
        state["correct_answer"] = "yes"

        asyncio.get_event_loop().run_until_complete(
            submit(choice="yes", state=state)
        )
        assert state["submitted"] is True

        reward = _terminal_reward(state)
        assert reward == 1.0

    def test_update_tool_args_injection(self):
        """Verify update_tool_args correctly injects runner and state."""
        ds, _ = _build_src_dataset(seed=42)
        env = SregEnv(dataset=ds, max_turns=10)

        state = vf.State()
        state["info"] = ds[0]["info"]
        state = asyncio.get_event_loop().run_until_complete(env.setup_state(state))

        # Simulate what verifiers does: model sends tool_args, env injects hidden args
        model_args = {"action_id": "act_something"}
        full_args = env.update_tool_args("research_action", model_args, [], state)

        assert full_args["action_id"] == "act_something"
        assert full_args["runner"] is state["runner"]
        assert full_args["state"] is state

    def test_tool_schemas_visible_to_model(self):
        """Verify the tool schemas don't expose hidden args (runner, state)."""
        ds, _ = _build_src_dataset(seed=42)
        env = SregEnv(dataset=ds, max_turns=10)

        for tool_def in env.tool_defs:
            params = tool_def.parameters
            prop_names = set(params.get("properties", {}).keys())
            assert "runner" not in prop_names, f"runner leaked in {tool_def.name} schema"
            assert "state" not in prop_names, f"state leaked in {tool_def.name} schema"

            if tool_def.name == "research_action":
                assert "action_id" in prop_names
            elif tool_def.name == "submit":
                assert "choice" in prop_names
                assert "distribution" in prop_names
                assert "adjustment_set" in prop_names
