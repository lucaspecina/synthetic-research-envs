"""QRData benchmark adapter.

Loads QRData dataset (411 questions on statistical + causal reasoning with
tabular data), prompts a model via ModelClient, parses answers, and computes
accuracy with numeric tolerance (3%) and exact match for multiple choice.

Dataset: https://github.com/xxxiaol/QRData
Paper: https://arxiv.org/abs/2402.17644 (ACL 2024 Findings)

Scoring follows the official eval.py: 3% relative tolerance for numerical,
case-insensitive prefix match for multiple choice.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from sreg.inference.protocol import ChatResponse, Message, MessageRole, ModelClient
from sreg.models.benchmark import BenchmarkResult, BenchmarkStatus

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an expert in statistics and causal inference. "
    "You will be given a dataset description, data, and a question. "
    "Analyze the data carefully and answer the question."
)

MAX_DATA_ROWS = 50  # max rows to include in prompt (truncate large CSVs)
MAX_DATA_CHARS = 3500  # max characters for data table in prompt


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class QRDataExample(BaseModel):
    """A single QRData question with metadata."""

    index: int  # position in original dataset (no ID field in QRData)
    data_description: str
    question: str
    answer: str
    data_files: list[str]
    question_type: str  # "numerical" or "multiple_choice"
    keywords: list[str]
    multiple_choices: list[str] | None = None  # only for MC questions
    is_causal: bool = False


class QRDataResult(BaseModel):
    """Result for a single QRData example."""

    index: int
    question_type: str
    is_causal: bool
    gold: str
    predicted: str | None = None
    raw_response: str = ""
    correct: bool = False
    error: bool = False


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class QRDataAdapter:
    """Load, run, and score QRData benchmark.

    Usage::

        adapter = QRDataAdapter(
            data_path="data/QRData.json",
            csv_dir="data/qrdata_csvs/data",
        )
        examples = adapter.load(subset="causal")
        results = adapter.run(client, examples, model="qwen3-8b")
        benchmark = adapter.score(results, model_name="qwen3-8b")
    """

    def __init__(self, data_path: str | Path, csv_dir: str | Path | None = None):
        self.data_path = Path(data_path)
        self.csv_dir = Path(csv_dir) if csv_dir else self.data_path.parent / "qrdata_csvs" / "data"

    def load(
        self,
        subset: str = "all",
        seed: int = 42,
        dev_count: int = 50,
    ) -> list[QRDataExample]:
        """Load QRData examples from JSON.

        Args:
            subset: "all", "causal", "statistical", or "dev"
            seed: random seed for dev subsampling
            dev_count: number of examples in dev mode
        """
        raw = json.loads(self.data_path.read_text(encoding="utf-8"))

        examples = []
        for i, item in enumerate(raw):
            meta = item.get("meta_data", {})
            keywords = meta.get("keywords", [])
            is_causal = "Causality" in keywords

            choices = meta.get("multiple_choices")

            examples.append(
                QRDataExample(
                    index=i,
                    data_description=item.get("data_description", ""),
                    question=item.get("question", ""),
                    answer=item.get("answer", ""),
                    data_files=item.get("data_files", []),
                    question_type=meta.get("question_type", "unknown"),
                    keywords=keywords,
                    multiple_choices=choices,
                    is_causal=is_causal,
                )
            )

        if subset == "causal":
            examples = [e for e in examples if e.is_causal]
        elif subset == "statistical":
            examples = [e for e in examples if not e.is_causal]
        elif subset == "dev":
            examples = self._deterministic_subsample(examples, seed, dev_count)

        logger.info(f"Loaded {len(examples)} QRData examples (subset={subset})")
        return examples

    def run(
        self,
        client: ModelClient,
        examples: list[QRDataExample],
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
        max_consecutive_errors: int = 5,
    ) -> list[QRDataResult]:
        """Run the model on QRData examples and collect results."""
        results: list[QRDataResult] = []
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
                predicted = self._parse_answer(raw, ex.question_type)
                correct = self._check_correct(predicted, ex.answer, ex.question_type)
                is_error = False
                consecutive_errors = 0
            except Exception as e:
                logger.warning(f"API error on example {ex.index}: {e}")
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
                QRDataResult(
                    index=ex.index,
                    question_type=ex.question_type,
                    is_causal=ex.is_causal,
                    gold=ex.answer,
                    predicted=predicted,
                    raw_response=raw,
                    correct=correct,
                    error=is_error,
                )
            )

            if (i + 1) % 20 == 0:
                logger.info(f"  Progress: {i + 1}/{len(examples)}")

        return results

    def score(
        self,
        results: list[QRDataResult],
        model_name: str,
        seed: int | None = None,
        prompt_version: str = "v1-cot",
    ) -> BenchmarkResult:
        """Compute aggregate metrics and return a BenchmarkResult."""
        total = len(results)
        errors = sum(1 for r in results if r.error)
        answered = total - errors
        correct = sum(1 for r in results if r.correct)
        unparseable = sum(1 for r in results if r.predicted is None and not r.error)

        # By question type
        by_type: dict[str, dict[str, int]] = {}
        for r in results:
            bucket = by_type.setdefault(r.question_type, {"total": 0, "correct": 0})
            bucket["total"] += 1
            if r.correct:
                bucket["correct"] += 1

        type_accuracy = {
            k: v["correct"] / v["total"] if v["total"] > 0 else 0.0
            for k, v in sorted(by_type.items())
        }

        # Causal vs statistical
        causal_results = [r for r in results if r.is_causal]
        stat_results = [r for r in results if not r.is_causal]

        causal_acc = (
            sum(1 for r in causal_results if r.correct) / len(causal_results)
            if causal_results
            else 0.0
        )
        stat_acc = (
            sum(1 for r in stat_results if r.correct) / len(stat_results)
            if stat_results
            else 0.0
        )

        code_version = _git_sha()

        return BenchmarkResult(
            benchmark="qrdata",
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
            dataset_version="v1",
            completed_at=datetime.now(timezone.utc),
            status=BenchmarkStatus.SUCCESS,
            summary={
                "by_question_type": type_accuracy,
                "causal_accuracy": causal_acc,
                "statistical_accuracy": stat_acc,
                "causal_count": len(causal_results),
                "statistical_count": len(stat_results),
                "unparseable": unparseable,
                "errors": errors,
                "answered": answered,
            },
        )

    def save_results(
        self,
        results: list[QRDataResult],
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

    def _compose_prompt(self, ex: QRDataExample) -> str:
        """Compose CoT-style prompt with data table included."""
        parts = []

        # Data description
        if ex.data_description.strip():
            parts.append(f"Dataset description:\n{ex.data_description.strip()}")

        # Load and include CSV data (truncated)
        data_text = self._load_csv_preview(ex.data_files)
        if data_text:
            parts.append(f"Data:\n{data_text}")

        # Multiple choice options
        if ex.multiple_choices:
            choices_text = "\n".join(
                f"  {chr(65 + i)}. {c}" for i, c in enumerate(ex.multiple_choices)
            )
            parts.append(f"Options:\n{choices_text}")

        # Question
        parts.append(f"Question: {ex.question.strip()}")

        # Answer format instruction
        parts.append(
            "Ensure that your final answer is positioned at the very end of "
            "your output, adhering to the format 'Final answer: [answer]'"
        )

        return "\n\n".join(parts)

    def _load_csv_preview(self, data_files: list[str]) -> str:
        """Load CSV files and return a truncated text preview."""
        if not data_files:
            return ""

        previews = []
        for fname in data_files:
            path = self.csv_dir / fname
            if not path.exists():
                logger.warning(f"CSV not found: {path}")
                continue

            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                lines = text.strip().split("\n")
                # Truncate to MAX_DATA_ROWS (header + data rows)
                if len(lines) > MAX_DATA_ROWS + 1:
                    truncated = lines[: MAX_DATA_ROWS + 1]
                    truncated.append(f"... ({len(lines) - MAX_DATA_ROWS - 1} more rows)")
                    text = "\n".join(truncated)

                if len(data_files) > 1:
                    previews.append(f"[{fname}]\n{text}")
                else:
                    previews.append(text)
            except Exception as e:
                logger.warning(f"Error reading {path}: {e}")

        result = "\n\n".join(previews)
        # Hard character limit
        if len(result) > MAX_DATA_CHARS:
            result = result[:MAX_DATA_CHARS] + "\n... (data truncated)"
        return result

    @staticmethod
    def _parse_answer(raw: str, question_type: str) -> str | None:
        """Parse answer from model output.

        Looks for "Final answer: X" pattern first, then falls back to
        extracting the last relevant value.
        """
        # Try "Final answer:" pattern
        match = re.search(r"[Ff]inal\s+[Aa]nswer\s*:\s*(.+?)(?:\n|$)", raw)
        if match:
            return match.group(1).strip().rstrip(".")

        # Fallback: for MC, look for standalone letter at end
        if question_type == "multiple_choice":
            # Look for "The answer is X" or just a letter at the end
            match = re.search(r"\b(?:answer\s+is|answer:)\s*([A-Da-d])\b", raw, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            # Last standalone letter
            match = re.search(r"\b([A-Da-d])\s*\.?\s*$", raw.strip())
            if match:
                return match.group(1).strip()

        # Fallback: for numerical, extract last number
        if question_type == "numerical":
            numbers = re.findall(r"-?\d+\.?\d*%?", raw)
            if numbers:
                return numbers[-1]

        return None

    @staticmethod
    def _check_correct(
        predicted: str | None,
        gold: str,
        question_type: str,
    ) -> bool:
        """Check if prediction matches gold answer.

        Follows official QRData eval.py scoring:
        - Numerical: 3% relative tolerance
        - Multiple choice: case-insensitive prefix match
        """
        if predicted is None:
            return False

        if question_type == "numerical":
            return _check_numerical(predicted, gold)
        else:
            return _check_multiple_choice(predicted, gold)

    @staticmethod
    def _deterministic_subsample(
        examples: list[QRDataExample],
        seed: int,
        count: int,
    ) -> list[QRDataExample]:
        """Select a balanced subsample."""
        import random

        rng = random.Random(seed)
        shuffled = list(examples)
        rng.shuffle(shuffled)
        return shuffled[:count]


# ---------------------------------------------------------------------------
# Scoring helpers (following official eval.py)
# ---------------------------------------------------------------------------


def _check_numerical(predicted: str, gold: str) -> bool:
    """Check numerical answer with 3% relative tolerance."""
    pred_num = _extract_number(predicted)
    gold_num = _extract_number(gold)

    if pred_num is None or gold_num is None:
        return False

    if gold_num == 0:
        return pred_num == 0

    lower = gold_num * 0.97
    upper = gold_num * 1.03
    if lower > upper:
        lower, upper = upper, lower

    return lower < pred_num < upper


def _check_multiple_choice(predicted: str, gold: str) -> bool:
    """Check multiple choice answer (case-insensitive prefix match)."""
    pred = predicted.strip().lower()
    gold_lower = gold.strip().lower()
    return gold_lower == pred[: len(gold_lower)]


def _extract_number(text: str) -> float | None:
    """Extract first number from text, handling percentages."""
    match = re.search(r"-?\d+\.?\d*%?", text)
    if not match:
        return None
    val = match.group()
    if val.endswith("%"):
        return float(val[:-1]) / 100
    return float(val)


def _git_sha() -> str | None:
    """Get current git SHA for reproducibility."""
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
