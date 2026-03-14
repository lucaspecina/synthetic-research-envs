"""Tests for dataset generation (T2.1)."""

from __future__ import annotations

import json

import pytest

from sreg.models.task import TaskType
from sreg.training.dataset import generate_dataset, generate_src, src_to_rows


class TestGenerateSrc:
    """Test programmatic SRC generation."""

    def test_generates_complete_src(self):
        world, problem, bundle, true_state = generate_src(seed=42)
        assert world is not None
        assert problem is not None
        assert bundle is not None
        assert len(true_state) > 0

    def test_world_has_cpds(self):
        """World must have CPDs for BN inference."""
        world, _, _, _ = generate_src(seed=42)
        # Nodes should exist
        assert len(world.nodes) >= 4

    def test_problem_has_actions(self):
        world, problem, _, _ = generate_src(seed=42)
        assert len(problem.available_actions) > 0
        assert problem.budget > 0
        assert problem.target_node is not None

    def test_true_state_covers_all_nodes(self):
        world, _, _, true_state = generate_src(seed=42)
        for node in world.nodes:
            assert node.name in true_state, f"Missing node {node.name} in true_state"

    def test_bundle_has_tasks(self):
        _, _, bundle, _ = generate_src(seed=42)
        assert len(bundle.tasks) > 0

    def test_different_seeds_different_worlds(self):
        w1, _, _, ts1 = generate_src(seed=42)
        w2, _, _, ts2 = generate_src(seed=99)
        # Different seeds should produce different true states
        assert ts1 != ts2

    def test_configurable_nodes_and_budget(self):
        world, problem, _, _ = generate_src(seed=42, num_nodes=10, budget=8)
        assert len(world.nodes) == 10
        assert problem.budget == 8


class TestSrcToRows:
    """Test SRC to dataset row conversion."""

    @pytest.fixture()
    def src(self):
        return generate_src(seed=42)

    def test_produces_rows(self, src):
        world, problem, bundle, true_state = src
        rows = src_to_rows(world, problem, bundle, true_state)
        assert len(rows) > 0

    def test_row_has_required_fields(self, src):
        world, problem, bundle, true_state = src
        rows = src_to_rows(world, problem, bundle, true_state)
        for row in rows:
            assert "prompt" in row
            assert "info" in row

            # Prompt is a message list
            prompt = row["prompt"]
            assert isinstance(prompt, list)
            assert len(prompt) >= 2
            assert prompt[0]["role"] == "system"
            assert prompt[1]["role"] == "user"

            # Info is a JSON string
            info = json.loads(row["info"])
            assert "world_json" in info
            assert "episode_json" in info
            assert "true_state" in info
            assert "eval_type" in info
            assert "correct_answer" in info

    def test_eval_type_is_valid(self, src):
        world, problem, bundle, true_state = src
        rows = src_to_rows(world, problem, bundle, true_state)
        valid_types = {t.value for t in TaskType}
        for row in rows:
            info = json.loads(row["info"])
            assert info["eval_type"] in valid_types

    def test_filter_by_eval_type(self, src):
        world, problem, bundle, true_state = src
        rows = src_to_rows(
            world,
            problem,
            bundle,
            true_state,
            eval_types=[TaskType.INFER_TARGET],
        )
        for row in rows:
            info = json.loads(row["info"])
            assert info["eval_type"] == "infer_target"

    def test_world_json_is_valid(self, src):
        """World JSON should be deserializable."""
        from sreg.models.world import World

        world, problem, bundle, true_state = src
        rows = src_to_rows(world, problem, bundle, true_state)
        for row in rows:
            info = json.loads(row["info"])
            w = World.model_validate_json(info["world_json"])
            assert len(w.nodes) > 0

    def test_episode_json_is_valid(self, src):
        """Episode JSON should be deserializable."""
        from sreg.models.episode import Episode

        world, problem, bundle, true_state = src
        rows = src_to_rows(world, problem, bundle, true_state)
        for row in rows:
            info = json.loads(row["info"])
            ep = Episode.model_validate_json(info["episode_json"])
            assert ep.budget > 0


class TestGenerateDataset:
    """Test full dataset generation."""

    def test_generates_hf_dataset(self):
        from datasets import Dataset

        ds = generate_dataset(n=2, seed=42)
        assert isinstance(ds, Dataset)
        assert len(ds) > 0

    def test_correct_columns(self):
        ds = generate_dataset(n=2, seed=42)
        assert "prompt" in ds.column_names
        assert "info" in ds.column_names

    def test_multiple_srcs(self):
        ds = generate_dataset(n=3, seed=42)
        # 3 SRCs, each with ~3 eval types = ~9 rows
        assert len(ds) >= 3

    def test_deterministic(self):
        ds1 = generate_dataset(n=2, seed=42)
        ds2 = generate_dataset(n=2, seed=42)
        assert len(ds1) == len(ds2)
        for r1, r2 in zip(ds1, ds2):
            assert r1["info"] == r2["info"]

    def test_filter_eval_type(self):
        ds = generate_dataset(n=3, seed=42, eval_types=[TaskType.INFER_TARGET])
        for row in ds:
            info = json.loads(row["info"])
            assert info["eval_type"] == "infer_target"


class TestDatasetWithSregEnv:
    """Test that generated dataset works with SregEnv."""

    def test_env_accepts_dataset(self):
        """SregEnv should accept the generated dataset."""
        from sreg.training._compat import patch_fcntl_if_windows

        patch_fcntl_if_windows()
        from sreg.training.env import SregEnv

        ds = generate_dataset(n=1, seed=42, eval_types=[TaskType.INFER_TARGET])
        env = SregEnv(dataset=ds, max_turns=5)
        assert env is not None

    def test_env_setup_state(self):
        """SregEnv.setup_state should work with generated rows."""
        import asyncio

        from sreg.training._compat import patch_fcntl_if_windows

        patch_fcntl_if_windows()

        import verifiers as vf

        from sreg.training.env import SregEnv

        ds = generate_dataset(n=1, seed=42, eval_types=[TaskType.INFER_TARGET])
        env = SregEnv(dataset=ds, max_turns=5)

        row = ds[0]
        state: vf.State = {
            "prompt": row["prompt"],
            "info": row["info"],
        }

        async def run():
            return await env.setup_state(state)

        state = asyncio.get_event_loop().run_until_complete(run())
        assert state["eval_type"] == "infer_target"
        assert state["runner"] is not None
        assert state["submitted"] is False
        assert "python_namespace" in state
