"""CLadder benchmark adapter.

Loads CLadder dataset (JSON), prompts a model via ModelClient, parses
yes/no answers, and computes accuracy by rung and query type.

Dataset: https://github.com/causalNLP/cladder
Paper: https://arxiv.org/abs/2312.04350 (NeurIPS 2023)

Scoring is deterministic binary accuracy (exact match on yes/no).
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from sreg.inference.protocol import ChatResponse, Message, MessageRole, ModelClient
from sreg.models.benchmark import BenchmarkResult, BenchmarkStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are an expert in causal inference. The following question is not a "
    "typical commonsense query, but rather a meticulously designed question "
    "created by a professor specializing in causal inference, intended to "
    "assess the students' mastery of the course content."
)


class CLadderExample(BaseModel):
    """A single CLadder question with metadata."""

    question_id: str
    background: str
    given_info: str
    question: str
    answer: str  # "yes" or "no"
    rung: int  # 1, 2, or 3
    query_type: str  # "ate", "backdoor", "nde", etc.
    sensical: int  # 1 = commonsense, -1 = anti, 0 = nonsense


class CLadderResult(BaseModel):
    """Result for a single CLadder example."""

    question_id: str
    rung: int
    query_type: str
    sensical: int
    gold: str
    predicted: str | None = None  # parsed yes/no, None if unparseable
    raw_response: str = ""
    correct: bool = False
    error: bool = False  # True if API/infra error (not a model answer)


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class CLadderAdapter:
    """Load, run, and score CLadder benchmark.

    Usage::

        adapter = CLadderAdapter(data_path="data/cladder-v1-balanced.json")
        examples = adapter.load(subset="dev", seed=42)
        results = adapter.run(client, examples, model="qwen3-8b")
        benchmark = adapter.score(results, model_name="qwen3-8b")
    """

    def __init__(self, data_path: str | Path):
        self.data_path = Path(data_path)

    def load(
        self,
        subset: str = "all",
        seed: int = 42,
        dev_per_type: int = 10,
    ) -> list[CLadderExample]:
        """Load CLadder examples from JSON.

        Args:
            subset: "all" for full dataset, "dev" for deterministic subsample
            seed: random seed for deterministic subsampling
            dev_per_type: examples per query_type in dev mode
        """
        raw = json.loads(self.data_path.read_text(encoding="utf-8"))

        examples = []
        for item in raw:
            meta = item.get("meta", {})
            # v1 balanced: rung/query_type are directly in meta (not nested under "query")
            # Other variants may use meta.query.rung — support both
            query = meta.get("query", {})
            rung = meta.get("rung", query.get("rung", 0))
            query_type = meta.get("query_type", query.get("query_type", "unknown"))
            sensical = item.get("sensical", meta.get("sensical", 1))

            # given_info may be a string or list of strings
            given_info = item.get("given_info", "")
            if isinstance(given_info, list):
                given_info = " ".join(given_info)

            examples.append(
                CLadderExample(
                    question_id=str(item.get("question_id", item.get("ID", ""))),
                    background=item.get("background", ""),
                    given_info=given_info,
                    question=item.get("question", ""),
                    answer=item.get("answer", "").lower().strip(),
                    rung=int(rung),
                    query_type=str(query_type),
                    sensical=int(sensical),
                )
            )

        if subset == "dev":
            examples = self._deterministic_subsample(examples, seed, dev_per_type)

        logger.info(f"Loaded {len(examples)} CLadder examples (subset={subset})")
        return examples

    def run(
        self,
        client: ModelClient,
        examples: list[CLadderExample],
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 256,
        max_consecutive_errors: int = 5,
    ) -> list[CLadderResult]:
        """Run the model on CLadder examples and collect results.

        Args:
            client: ModelClient implementation (e.g. OpenAIClient)
            examples: list of CLadderExample to evaluate
            model: model name override (uses client default if None)
            temperature: sampling temperature (0.0 for deterministic)
            max_tokens: max output tokens (yes/no + reasoning, 256 is plenty)
            max_consecutive_errors: abort after N consecutive API errors

        Raises:
            RuntimeError: if max_consecutive_errors is exceeded
        """
        results: list[CLadderResult] = []
        consecutive_errors = 0

        for i, ex in enumerate(examples):
            prompt = self._compose_prompt(ex)
            messages = [
                Message(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT),
                Message(role=MessageRole.USER, content=prompt),
            ]

            try:
                response: ChatResponse = client.chat(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                raw = response.message.content or ""
                predicted = self._parse_answer(raw)
                correct = predicted is not None and predicted == ex.answer
                is_error = False
                consecutive_errors = 0
            except Exception as e:
                logger.warning(f"API error on example {ex.question_id}: {e}")
                raw = f"ERROR: {e}"
                predicted = None
                correct = False
                is_error = True
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    raise RuntimeError(
                        f"Aborting: {max_consecutive_errors} consecutive API errors. "
                        f"Last error: {e}"
                    ) from e

            results.append(
                CLadderResult(
                    question_id=ex.question_id,
                    rung=ex.rung,
                    query_type=ex.query_type,
                    sensical=ex.sensical,
                    gold=ex.answer,
                    predicted=predicted,
                    raw_response=raw,
                    correct=correct,
                    error=is_error,
                )
            )

            if (i + 1) % 50 == 0:
                logger.info(f"  Progress: {i + 1}/{len(examples)}")

        return results

    def score(
        self,
        results: list[CLadderResult],
        model_name: str,
        seed: int | None = None,
        prompt_version: str = "v1-zero-shot",
    ) -> BenchmarkResult:
        """Compute aggregate metrics and return a BenchmarkResult.

        Returns overall accuracy + per-rung + per-query-type breakdown in summary.
        """
        total = len(results)
        errors = sum(1 for r in results if r.error)
        answered = total - errors
        correct = sum(1 for r in results if r.correct)
        unparseable = sum(1 for r in results if r.predicted is None and not r.error)

        # Per-rung accuracy
        by_rung: dict[int, dict[str, int]] = {}
        for r in results:
            bucket = by_rung.setdefault(r.rung, {"total": 0, "correct": 0})
            bucket["total"] += 1
            if r.correct:
                bucket["correct"] += 1

        rung_accuracy = {
            f"rung_{k}": v["correct"] / v["total"] if v["total"] > 0 else 0.0
            for k, v in sorted(by_rung.items())
        }

        # Per-query-type accuracy
        by_type: dict[str, dict[str, int]] = {}
        for r in results:
            bucket = by_type.setdefault(r.query_type, {"total": 0, "correct": 0})
            bucket["total"] += 1
            if r.correct:
                bucket["correct"] += 1

        type_accuracy = {
            k: v["correct"] / v["total"] if v["total"] > 0 else 0.0
            for k, v in sorted(by_type.items())
        }

        # Per-sensical accuracy
        by_sensical: dict[int, dict[str, int]] = {}
        for r in results:
            bucket = by_sensical.setdefault(r.sensical, {"total": 0, "correct": 0})
            bucket["total"] += 1
            if r.correct:
                bucket["correct"] += 1

        sensical_labels = {1: "commonsense", -1: "anticommonsense", 0: "nonsense"}
        sensical_accuracy = {
            sensical_labels.get(k, str(k)): v["correct"] / v["total"]
            if v["total"] > 0
            else 0.0
            for k, v in sorted(by_sensical.items())
        }

        code_version = _git_sha()

        return BenchmarkResult(
            benchmark="cladder",
            benchmark_version="v1",
            model_name=model_name,
            eval_split="all",
            metric_name="accuracy",
            metric_value=correct / total if total > 0 else 0.0,
            higher_is_better=True,
            num_examples=total,
            num_correct=correct,
            seed=seed,
            prompt_version=prompt_version,
            code_version=code_version,
            dataset_version="v1-balanced",
            completed_at=datetime.now(timezone.utc),
            status=BenchmarkStatus.SUCCESS,
            summary={
                "by_rung": rung_accuracy,
                "by_query_type": type_accuracy,
                "by_sensical": sensical_accuracy,
                "unparseable": unparseable,
                "errors": errors,
                "answered": answered,
            },
        )

    def save_results(
        self,
        results: list[CLadderResult],
        output_path: str | Path,
    ) -> None:
        """Save per-example results as JSONL."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            for r in results:
                f.write(r.model_dump_json() + "\n")
        logger.info(f"Saved {len(results)} results to {output}")

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _compose_prompt(ex: CLadderExample) -> str:
        """Compose the prompt for a single CLadder question.

        Follows the official prompt format from the CLadder paper.
        """
        parts = []
        if ex.background.strip():
            parts.append(ex.background.strip())
        if ex.given_info.strip():
            parts.append(ex.given_info.strip())
        if ex.question.strip():
            parts.append(ex.question.strip())

        prompt = " ".join(parts)
        prompt += (
            '\nStart your answer with "Yes" or "No", followed by additional '
            "reasoning or evidence to support your explanation."
        )
        return prompt

    @staticmethod
    def _parse_answer(raw: str) -> str | None:
        """Parse a yes/no answer from model output.

        Handles common model output patterns:
        - "Yes, because..." / "No, the evidence..."
        - "**Yes**" / "**No**"
        - "Answer: Yes" / "Answer: No"
        - "The answer is yes/no"

        Returns "yes", "no", or None if unparseable.
        """
        import re

        text = raw.strip().lower()
        # Remove leading markdown bold/italic markers
        text = re.sub(r"^[\s*_#]+", "", text)

        if text.startswith("yes"):
            return "yes"
        if text.startswith("no"):
            return "no"

        # Fallback: check for "answer: yes/no" or "answer is yes/no" patterns
        match = re.search(r"\banswer\s*(?:is|:)\s*(yes|no)\b", text)
        if match:
            return match.group(1)

        return None

    @staticmethod
    def _deterministic_subsample(
        examples: list[CLadderExample],
        seed: int,
        per_type: int,
    ) -> list[CLadderExample]:
        """Select a balanced subsample: per_type examples per query_type.

        Deterministic given the same seed — sorts by question_id, then
        selects every Nth example to get per_type from each group.
        """
        import random

        rng = random.Random(seed)

        by_type: dict[str, list[CLadderExample]] = {}
        for ex in examples:
            by_type.setdefault(ex.query_type, []).append(ex)

        selected: list[CLadderExample] = []
        for qtype in sorted(by_type.keys()):
            group = sorted(by_type[qtype], key=lambda e: e.question_id)
            rng_copy = random.Random(seed)
            rng_copy.shuffle(group)
            selected.extend(group[:per_type])

        rng.shuffle(selected)
        return selected


def _git_sha() -> str | None:
    """Get current git SHA for reproducibility, or None if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None
