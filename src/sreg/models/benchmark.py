"""Benchmark result models for BEFORE/AFTER transfer evaluation.

Standard format for recording benchmark evaluations. Used by benchmark
adapters (CLadder, QRData, etc.) and comparison tooling.

Reproducibility metadata is mandatory — without it, BEFORE/AFTER
comparisons are unreliable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class BenchmarkStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class BenchmarkResult(BaseModel):
    """Result of evaluating a model on a benchmark.

    One instance per (benchmark, model, split) combination.
    """

    # Identity
    run_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    benchmark: str  # "cladder", "qrdata", "discoverybench", "scigym"
    benchmark_version: str | None = None

    # Model
    model_name: str  # "qwen3-8b", "qwen3-0.5b"
    model_backend: Literal["openai", "vllm", "other"] = "openai"
    inference_config: dict[str, Any] = Field(default_factory=dict)

    # Evaluation
    eval_split: str  # "test", "causal_subset", "rung_2", "q-nonsense"
    metric_name: str  # "accuracy", "hms", "graph_edit_distance", "kl"
    metric_value: float
    higher_is_better: bool = True
    num_examples: int
    num_correct: int | None = None

    # Reproducibility
    seed: int | None = None
    prompt_version: str | None = None
    code_version: str | None = None  # git sha
    dataset_version: str | None = None
    toolset_version: str | None = None  # agent toolset version

    # Timing
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    status: BenchmarkStatus = BenchmarkStatus.SUCCESS

    # Details
    summary: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class BenchmarkComparison(BaseModel):
    """BEFORE/AFTER comparison of two benchmark runs.

    Used to measure transfer: did training on SREG improve the model?
    """

    before: BenchmarkResult
    after: BenchmarkResult
    delta: float  # after.metric_value - before.metric_value (or ratio)
    relative_delta: float | None = None  # delta / before.metric_value
    significant: bool | None = None  # statistical significance (if computed)
    notes: str = ""
