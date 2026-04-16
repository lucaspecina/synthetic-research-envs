"""Tests for sreg.training.train_config.

Validation is load-bearing: a config with a typo'd case id or a missing
env var would silently train on the wrong data (or produce opaque
"loaded 9/10" warnings at runtime). These tests pin the fail-fast
contract so the script errors out with a clear message instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sreg.training.train_config import load_config, validate_config


def _write_case(dir_path: Path, name: str) -> None:
    """Create a stub <dir>/<case>/src.json so validate_config's existence
    check passes. Contents don't matter — we're not loading SRCs here."""
    case_dir = dir_path / name
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "src.json").write_text("{}", encoding="utf-8")


def _write_yaml(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "cfg.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def _valid_cfg(dataset_dir: Path) -> dict:
    """Minimal valid cfg dict. Mutate in individual tests to trigger failures.

    Keep this in sync with `_REQUIRED` in train_config.py — every required
    field must be present here or every test blows up on MissingKey.
    """
    return {
        "dataset": {
            "dir": str(dataset_dir),
            "train_cases": ["a", "b"],
            "holdout_cases": ["c"],
        },
        "rollout": {
            "temperature": 0.7,
            "max_turns": 15,
            "claim_cap": 15,
            "n_mc": 10000,
        },
        "training": {
            "model": "Qwen/Qwen3-8B",
            "run_name": "test_run",
            "rollouts_per_example": 4,
            "batch_size": 8,
            "micro_batch_size": 1,
            "max_concurrent": 8,
            "total_steps": 10,
            "seed": 42,
            "max_tokens": 1024,
            "max_seq_len": 8192,
            "learning_rate": 1.0e-5,
            "use_lora": True,
            "lora_rank": 16,
            "lora_alpha": 32,
            "vllm_server_host": "0.0.0.0",
            "vllm_server_port": 8000,
            "save_steps": 10,
            "logging_steps": 1,
            "report_to": None,
        },
    }


def _valid_dir_with_cases(tmp_path: Path, cases: list[str]) -> Path:
    d = tmp_path / "dataset"
    d.mkdir()
    for c in cases:
        _write_case(d, c)
    return d


class TestLoadConfig:
    def test_loads_simple_yaml(self, tmp_path):
        p = _write_yaml(tmp_path, "foo: bar\nbaz: 42\n")
        cfg = load_config(p)
        assert cfg == {"foo": "bar", "baz": 42}

    def test_expands_env_vars_dollar_brace(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_PATH", "/resolved/absolute/path")
        p = _write_yaml(tmp_path, "dataset:\n  dir: ${MY_PATH}\n")
        cfg = load_config(p)
        assert cfg["dataset"]["dir"] == "/resolved/absolute/path"

    def test_expands_env_vars_plain_dollar(self, tmp_path, monkeypatch):
        """os.path.expandvars handles both $VAR and ${VAR}."""
        monkeypatch.setenv("MY_PATH", "/resolved")
        p = _write_yaml(tmp_path, "x: $MY_PATH/sub\n")
        cfg = load_config(p)
        assert cfg["x"] == "/resolved/sub"

    def test_unresolved_env_var_stays_literal(self, tmp_path, monkeypatch):
        """os.path.expandvars leaves unresolved $VAR as-is. Downstream
        validation catches it as a nonexistent path instead of silently
        pointing somewhere wrong."""
        monkeypatch.delenv("DEFINITELY_NOT_SET", raising=False)
        p = _write_yaml(tmp_path, "x: ${DEFINITELY_NOT_SET}\n")
        cfg = load_config(p)
        assert cfg["x"] == "${DEFINITELY_NOT_SET}"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "does_not_exist.yaml")

    def test_empty_file_raises(self, tmp_path):
        p = _write_yaml(tmp_path, "")
        with pytest.raises(ValueError, match="empty"):
            load_config(p)

    def test_non_mapping_top_level_raises(self, tmp_path):
        """A YAML top-level list or scalar is not a valid config."""
        p = _write_yaml(tmp_path, "- a\n- b\n")
        with pytest.raises(ValueError, match="mapping"):
            load_config(p)


class TestValidateConfig:
    def test_valid_config_passes(self, tmp_path):
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        validate_config(_valid_cfg(d))

    def test_missing_dataset_section(self, tmp_path):
        cfg = _valid_cfg(_valid_dir_with_cases(tmp_path, ["a", "b", "c"]))
        del cfg["dataset"]
        with pytest.raises(ValueError, match="missing key: dataset"):
            validate_config(cfg)

    def test_missing_nested_key(self, tmp_path):
        cfg = _valid_cfg(_valid_dir_with_cases(tmp_path, ["a", "b", "c"]))
        del cfg["rollout"]["n_mc"]
        with pytest.raises(ValueError, match="rollout.n_mc"):
            validate_config(cfg)

    def test_wrong_type(self, tmp_path):
        cfg = _valid_cfg(_valid_dir_with_cases(tmp_path, ["a", "b", "c"]))
        cfg["rollout"]["max_turns"] = "fifteen"
        with pytest.raises(TypeError, match="max_turns"):
            validate_config(cfg)

    def test_unexpanded_env_var_in_dir(self, tmp_path):
        """A literal $VAR in dataset.dir means the env var wasn't set —
        fail fast with a clear message instead of 'not a directory'."""
        cfg = _valid_cfg(tmp_path)
        cfg["dataset"]["dir"] = "${NEVER_SET}"
        with pytest.raises(ValueError, match="unexpanded env var"):
            validate_config(cfg)

    def test_dataset_dir_not_a_directory(self, tmp_path):
        cfg = _valid_cfg(tmp_path / "nope")
        with pytest.raises(ValueError, match="does not exist"):
            validate_config(cfg)

    def test_empty_train_cases(self, tmp_path):
        d = _valid_dir_with_cases(tmp_path, ["c"])
        cfg = _valid_cfg(d)
        cfg["dataset"]["train_cases"] = []
        with pytest.raises(ValueError, match="train_cases is empty"):
            validate_config(cfg)

    def test_overlap_train_and_holdout(self, tmp_path):
        """Training on the holdout defeats the purpose — must fail."""
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["dataset"]["train_cases"] = ["a", "b"]
        cfg["dataset"]["holdout_cases"] = ["b", "c"]
        with pytest.raises(ValueError, match="overlap.*'b'"):
            validate_config(cfg)

    def test_duplicates_in_train_cases(self, tmp_path):
        d = _valid_dir_with_cases(tmp_path, ["a", "b"])
        cfg = _valid_cfg(d)
        cfg["dataset"]["train_cases"] = ["a", "a", "b"]
        cfg["dataset"]["holdout_cases"] = []
        with pytest.raises(ValueError, match="duplicates"):
            validate_config(cfg)

    def test_case_missing_src_json(self, tmp_path):
        """A typo'd case id must fail here, not silently at runtime."""
        d = _valid_dir_with_cases(tmp_path, ["a", "b"])
        cfg = _valid_cfg(d)
        cfg["dataset"]["train_cases"] = ["a", "typoed_case"]
        cfg["dataset"]["holdout_cases"] = ["b"]
        with pytest.raises(ValueError, match="missing src.json.*typoed_case"):
            validate_config(cfg)

    def test_case_dir_exists_but_src_json_missing(self, tmp_path):
        """A dir with no src.json is as broken as a missing dir."""
        d = tmp_path / "dataset"
        d.mkdir()
        (d / "a" / "src.json").parent.mkdir()
        (d / "a" / "src.json").write_text("{}", encoding="utf-8")
        (d / "b").mkdir()  # no src.json inside
        cfg = _valid_cfg(d)
        cfg["dataset"]["train_cases"] = ["a", "b"]
        cfg["dataset"]["holdout_cases"] = []
        with pytest.raises(ValueError, match="missing src.json.*'b'"):
            validate_config(cfg)

    def test_negative_max_turns(self, tmp_path):
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["rollout"]["max_turns"] = 0
        with pytest.raises(ValueError, match="max_turns"):
            validate_config(cfg)

    def test_temperature_out_of_range(self, tmp_path):
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["rollout"]["temperature"] = 2.5
        with pytest.raises(ValueError, match="temperature"):
            validate_config(cfg)

    def test_zero_rollouts_per_example(self, tmp_path):
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["training"]["rollouts_per_example"] = 0
        with pytest.raises(ValueError, match="rollouts_per_example"):
            validate_config(cfg)

    def test_zero_total_steps(self, tmp_path):
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["training"]["total_steps"] = 0
        with pytest.raises(ValueError, match="total_steps"):
            validate_config(cfg)

    def test_empty_holdout_is_allowed(self, tmp_path):
        """You can train without a holdout (you shouldn't, but the loader
        shouldn't block it — that's a config-file policy decision, not a
        validation invariant)."""
        d = _valid_dir_with_cases(tmp_path, ["a"])
        cfg = _valid_cfg(d)
        cfg["dataset"]["train_cases"] = ["a"]
        cfg["dataset"]["holdout_cases"] = []
        validate_config(cfg)  # no raise

    # --- trainer-specific invariants ---

    def test_rollouts_per_example_min_2(self, tmp_path):
        """GRPO requires G >= 2. RLConfig asserts this too — catch at config."""
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["training"]["rollouts_per_example"] = 1
        cfg["training"]["batch_size"] = 8  # divisible so we hit the G check
        with pytest.raises(ValueError, match="rollouts_per_example.*>= 2"):
            validate_config(cfg)

    def test_batch_size_not_divisible_by_G(self, tmp_path):
        """batch_size / G must be an integer (prompts_per_step)."""
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["training"]["batch_size"] = 7
        cfg["training"]["rollouts_per_example"] = 4
        with pytest.raises(ValueError, match="divisible by"):
            validate_config(cfg)

    def test_batch_size_smaller_than_G(self, tmp_path):
        """Need at least 1 prompt per step, so batch_size >= G."""
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["training"]["batch_size"] = 2
        cfg["training"]["rollouts_per_example"] = 4
        with pytest.raises(ValueError, match=">= rollouts_per_example"):
            validate_config(cfg)

    def test_max_seq_len_smaller_than_max_tokens(self, tmp_path):
        """max_seq_len has to fit at least one generation."""
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["training"]["max_tokens"] = 2048
        cfg["training"]["max_seq_len"] = 1024
        with pytest.raises(ValueError, match="max_seq_len.*>= max_tokens"):
            validate_config(cfg)

    def test_zero_max_tokens(self, tmp_path):
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["training"]["max_tokens"] = 0
        with pytest.raises(ValueError, match="max_tokens"):
            validate_config(cfg)

    def test_negative_learning_rate(self, tmp_path):
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["training"]["learning_rate"] = -1.0e-5
        with pytest.raises(ValueError, match="learning_rate"):
            validate_config(cfg)

    def test_zero_learning_rate(self, tmp_path):
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["training"]["learning_rate"] = 0
        with pytest.raises(ValueError, match="learning_rate"):
            validate_config(cfg)

    def test_lora_rank_zero_when_use_lora(self, tmp_path):
        """If use_lora=True, rank must be >= 1. If use_lora=False we skip."""
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["training"]["use_lora"] = True
        cfg["training"]["lora_rank"] = 0
        with pytest.raises(ValueError, match="lora_rank"):
            validate_config(cfg)

    def test_lora_rank_zero_ok_when_use_lora_false(self, tmp_path):
        """LoRA disabled -> the LoRA knobs don't matter, don't block."""
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["training"]["use_lora"] = False
        cfg["training"]["lora_rank"] = 0  # stale but ignored
        validate_config(cfg)  # no raise

    def test_vllm_port_out_of_range(self, tmp_path):
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["training"]["vllm_server_port"] = 70000
        with pytest.raises(ValueError, match="vllm_server_port"):
            validate_config(cfg)

    def test_zero_micro_batch_size(self, tmp_path):
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["training"]["micro_batch_size"] = 0
        with pytest.raises(ValueError, match="micro_batch_size"):
            validate_config(cfg)

    def test_report_to_none_is_ok(self, tmp_path):
        """Smoke can run without wandb — report_to: null in YAML."""
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["training"]["report_to"] = None
        validate_config(cfg)  # no raise

    def test_report_to_wandb_is_ok(self, tmp_path):
        d = _valid_dir_with_cases(tmp_path, ["a", "b", "c"])
        cfg = _valid_cfg(d)
        cfg["training"]["report_to"] = "wandb"
        validate_config(cfg)  # no raise
