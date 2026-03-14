"""DiscoveryBench benchmark adapter.

Loads DiscoveryBench dataset (CSV), prompts a model to generate hypotheses
from data descriptions, and scores using HMS (Hypothesis Matching Score).

Dataset: https://huggingface.co/datasets/allenai/discoverybench
Paper: https://arxiv.org/abs/2407.01725

Scoring uses HMS via LLM judge (not deterministic).
"""

from __future__ import annotations

import csv
import json
import logging
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from sreg.benchmarks.discoverybench.hms import compute_hms
from sreg.inference.protocol import ChatResponse, Message, MessageRole, ModelClient
from sreg.models.benchmark import BenchmarkResult, BenchmarkStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a data scientist analyzing research datasets. Given a dataset "
    "description with column information and a research question, formulate "
    "a clear, specific hypothesis that answers the question. Your hypothesis "
    "should mention the relevant variables, their relationship, and any "
    "important context or conditions. Be concise but precise."
)


class DiscoveryBenchExample(BaseModel):
    """A single DiscoveryBench task."""

    index: int  # Row index in CSV
    domain: str
    workflow_tags: list[str]
    domain_knowledge: str
    datasets: list[dict]  # Dataset metadata (name, description, columns)
    question: str
    question_type: str
    gold_hypothesis: str


class DiscoveryBenchResult(BaseModel):
    """Result for a single DiscoveryBench example."""

    index: int
    domain: str
    question_type: str
    gold_hypothesis: str
    predicted_hypothesis: str = ""
    raw_response: str = ""
    hms_score: float = 0.0
    hms_detail: dict = {}
    error: bool = False


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

MAX_COLUMN_DISPLAY = 30  # Max columns to show in prompt


class DiscoveryBenchAdapter:
    """Load, run, and score DiscoveryBench.

    Usage::

        adapter = DiscoveryBenchAdapter(data_path="data/discoverybench_test.csv")
        examples = adapter.load(subset="dev", seed=42)
        results = adapter.run(client, examples)
        benchmark = adapter.score(results, client, model_name="gpt-5.2-chat")
    """

    def __init__(self, data_path: str | Path):
        self.data_path = Path(data_path)

    def load(
        self,
        subset: str = "all",
        seed: int = 42,
        dev_count: int = 20,
    ) -> list[DiscoveryBenchExample]:
        """Load DiscoveryBench examples from CSV.

        Args:
            subset: "all" for full dataset, "dev" for small subsample
            seed: random seed for deterministic subsampling
            dev_count: number of examples in dev mode
        """
        with open(self.data_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        examples = []
        for i, row in enumerate(rows):
            datasets = json.loads(row["datasets"])
            queries = json.loads(row["queries"])

            # Each row has exactly 1 query
            query = queries[0]

            # Parse workflow_tags
            wt = row.get("workflow_tags", "")
            if wt.startswith("["):
                workflow_tags = json.loads(wt)
            else:
                workflow_tags = [t.strip() for t in wt.split(",") if t.strip()]

            examples.append(
                DiscoveryBenchExample(
                    index=i,
                    domain=row.get("domain", "unknown"),
                    workflow_tags=workflow_tags,
                    domain_knowledge=row.get("domain_knowledge", ""),
                    datasets=datasets,
                    question=query.get("question", ""),
                    question_type=query.get("question_type", "unknown"),
                    gold_hypothesis=query.get("true_hypothesis", ""),
                )
            )

        if subset == "dev":
            examples = self._deterministic_subsample(examples, seed, dev_count)

        logger.info(f"Loaded {len(examples)} DiscoveryBench examples (subset={subset})")
        return examples

    def run(
        self,
        client: ModelClient,
        examples: list[DiscoveryBenchExample],
        model: str | None = None,
        temperature: float = 0.0,
        max_consecutive_errors: int = 5,
    ) -> list[DiscoveryBenchResult]:
        """Run the model on DiscoveryBench examples.

        For each example, prompts the model with dataset description + question
        and collects the predicted hypothesis.
        """
        results: list[DiscoveryBenchResult] = []
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
                    max_tokens=512,
                )
                raw = response.message.content or ""
                predicted = self._extract_hypothesis(raw)
                is_error = False
                consecutive_errors = 0
            except Exception as e:
                logger.warning(f"API error on example {ex.index}: {e}")
                raw = f"ERROR: {e}"
                predicted = ""
                is_error = True
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    raise RuntimeError(
                        f"Aborting: {max_consecutive_errors} consecutive API errors. "
                        f"Last error: {e}"
                    ) from e

            results.append(
                DiscoveryBenchResult(
                    index=ex.index,
                    domain=ex.domain,
                    question_type=ex.question_type,
                    gold_hypothesis=ex.gold_hypothesis,
                    predicted_hypothesis=predicted,
                    raw_response=raw,
                    error=is_error,
                )
            )

            if (i + 1) % 10 == 0:
                logger.info(f"  Progress: {i + 1}/{len(examples)}")

        return results

    def score(
        self,
        results: list[DiscoveryBenchResult],
        client: ModelClient,
        model_name: str = "unknown",
        model: str | None = None,
        seed: int = 42,
    ) -> BenchmarkResult:
        """Score results using HMS (requires LLM calls).

        Args:
            results: List of run results.
            client: LLM client for HMS evaluation.
            model_name: Name of the model being evaluated.
            model: Model override for HMS scorer.
            seed: Random seed used during run.
        """
        scored_results = []
        for i, r in enumerate(results):
            if r.error:
                scored_results.append(r)
                continue

            logger.info(f"  HMS scoring {i + 1}/{len(results)}...")
            try:
                hms = compute_hms(
                    gold_hypothesis=r.gold_hypothesis,
                    predicted_hypothesis=r.predicted_hypothesis,
                    client=client,
                    model=model,
                )
                r.hms_score = hms.score
                r.hms_detail = hms.model_dump()
            except Exception as e:
                logger.warning(f"HMS scoring failed for example {r.index}: {e}")
                r.hms_score = 0.0
                r.hms_detail = {"error": str(e)}

            scored_results.append(r)

        # Aggregate
        non_error = [r for r in scored_results if not r.error]
        hms_scores = [r.hms_score for r in non_error]
        mean_hms = sum(hms_scores) / len(hms_scores) if hms_scores else 0.0

        # By domain
        by_domain: dict[str, list[float]] = {}
        for r in non_error:
            by_domain.setdefault(r.domain, []).append(r.hms_score)
        domain_means = {d: sum(s) / len(s) for d, s in by_domain.items()}

        # By question type
        by_qtype: dict[str, list[float]] = {}
        for r in non_error:
            by_qtype.setdefault(r.question_type, []).append(r.hms_score)
        qtype_means = {q: sum(s) / len(s) for q, s in by_qtype.items()}

        errors = sum(1 for r in scored_results if r.error)

        # Get git version
        try:
            code_version = (
                subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:
            code_version = "unknown"

        return BenchmarkResult(
            benchmark="discoverybench",
            benchmark_version="v1",
            model_name=model_name,
            model_backend="openai",
            eval_split="all",
            metric_name="hms",
            metric_value=mean_hms,
            higher_is_better=True,
            num_examples=len(scored_results),
            num_correct=sum(1 for r in non_error if r.hms_score > 0.5),
            seed=seed,
            prompt_version="v1-zero-shot",
            code_version=code_version,
            dataset_version="v1-real",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            status=BenchmarkStatus.SUCCESS,
            summary={
                "mean_hms": mean_hms,
                "median_hms": sorted(hms_scores)[len(hms_scores) // 2]
                if hms_scores
                else 0.0,
                "by_domain": domain_means,
                "by_question_type": qtype_means,
                "errors": errors,
                "answered": len(non_error),
                "above_50": sum(1 for s in hms_scores if s > 0.5),
                "above_25": sum(1 for s in hms_scores if s > 0.25),
            },
        )

    def save_results(
        self,
        results: list[DiscoveryBenchResult],
        output_path: str | Path,
    ) -> None:
        """Save per-example results as JSONL."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            for r in results:
                # Exclude hms_detail from JSONL to keep it manageable
                data = r.model_dump()
                data.pop("hms_detail", None)
                f.write(json.dumps(data, ensure_ascii=False) + "\n")

        logger.info(f"Saved {len(results)} results to {output_path}")

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _compose_prompt(self, ex: DiscoveryBenchExample) -> str:
        """Compose the prompt for generating a hypothesis."""
        parts = []

        # Domain and context
        parts.append(f"Domain: {ex.domain}")
        if ex.domain_knowledge:
            parts.append(f"\nBackground: {ex.domain_knowledge}")

        # Dataset descriptions
        for ds in ex.datasets:
            parts.append(f"\nDataset: {ds.get('name', 'data.csv')}")
            desc = ds.get("description", "")
            if desc:
                parts.append(f"Description: {desc}")

            # Column info
            columns = ds.get("columns", {})
            raw_cols = columns.get("raw", [])
            if raw_cols:
                col_lines = []
                for col in raw_cols[:MAX_COLUMN_DISPLAY]:
                    name = col.get("name", "?")
                    cdesc = col.get("description", "")
                    if cdesc:
                        col_lines.append(f"  - {name}: {cdesc}")
                    else:
                        col_lines.append(f"  - {name}")
                if len(raw_cols) > MAX_COLUMN_DISPLAY:
                    col_lines.append(
                        f"  ... and {len(raw_cols) - MAX_COLUMN_DISPLAY} more columns"
                    )
                parts.append("Columns:\n" + "\n".join(col_lines))

        # Question
        parts.append(f"\nResearch question: {ex.question}")
        parts.append(
            "\nFormulate a specific, testable hypothesis that answers this question. "
            "Mention the relevant variables, their relationship (direction, type), "
            "and any important context. Be concise."
        )

        return "\n".join(parts)

    @staticmethod
    def _extract_hypothesis(raw: str) -> str:
        """Extract the hypothesis from the model's response.

        The model may wrap it in quotes, prefix it, etc. We try to clean it up.
        """
        text = raw.strip()
        if not text:
            return ""

        # If the response starts with "Hypothesis:" or similar, extract after it
        for prefix in ["**Hypothesis:**", "**Hypothesis**:", "Hypothesis:"]:
            if prefix.lower() in text.lower():
                idx = text.lower().index(prefix.lower()) + len(prefix)
                text = text[idx:].strip()
                break

        # Strip leading/trailing markdown bold markers
        while text.startswith("**"):
            text = text[2:].strip()
        while text.endswith("**"):
            text = text[:-2].strip()

        # Remove surrounding quotes
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1].strip()

        return text

    @staticmethod
    def _deterministic_subsample(
        examples: list[DiscoveryBenchExample],
        seed: int,
        count: int,
    ) -> list[DiscoveryBenchExample]:
        """Balanced subsample across domains."""
        rng = random.Random(seed)

        # Group by domain
        by_domain: dict[str, list[DiscoveryBenchExample]] = {}
        for ex in examples:
            by_domain.setdefault(ex.domain, []).append(ex)

        # Calculate per-domain quota
        n_domains = len(by_domain)
        per_domain = max(1, count // n_domains)

        selected = []
        for domain in sorted(by_domain.keys()):
            pool = by_domain[domain]
            rng.shuffle(pool)
            selected.extend(pool[:per_domain])

        # If we need more, fill from remaining
        if len(selected) < count:
            used_indices = {ex.index for ex in selected}
            remaining = [ex for ex in examples if ex.index not in used_indices]
            rng.shuffle(remaining)
            selected.extend(remaining[: count - len(selected)])

        return selected[:count]
