"""CausalReasoningBenchmark (CRB) adapter.

Loads CRB dataset (173 queries on 138 real-world datasets), prompts a model
to produce a structured identification spec + estimation, and scores against
gold-standard specs and estimates.

Dataset: https://huggingface.co/datasets/syrgkanislab/CausalReasoningBenchmark
Paper: arXiv:2602.20571

Scoring is deterministic:
- Identification: binary per-field (strategy, treatments, outcomes, controls, etc.)
- Estimation: point error, percentage error, CI containment, null hypothesis decision
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
# Constants
# ---------------------------------------------------------------------------

STRATEGIES = [
    "RCT",
    "Conditional Exogeneity",
    "Instrumental Variable",
    "Regression Discontinuity",
    "Difference-in-Differences",
]

MAX_DATA_ROWS = 50
MAX_DATA_CHARS = 4000

SYSTEM_PROMPT = (
    "You are an expert in causal inference and econometrics. You will be given "
    "a research question, dataset metadata, and data. Your task is to:\n"
    "1. Identify the correct causal identification strategy\n"
    "2. Specify the treatment, outcome, and control variables\n"
    "3. Estimate the causal effect with a standard error\n\n"
    "Return your answer as a JSON object."
)

OUTPUT_FORMAT = """\
Return ONLY a JSON object with these fields:
{
  "strategy": "RCT | Conditional Exogeneity | Instrumental Variable | Regression Discontinuity | Difference-in-Differences",
  "causal_quantity": "ATE | ATT | ATC | LATE | CATE | Other",
  "treatments": ["treatment_var_name"],
  "outcomes": ["outcome_var_name"],
  "controls": ["control_var1", "control_var2"],
  "effect_estimate": 1.23,
  "standard_error": 0.45,
  "instrument": ["instrument_var"],
  "is_encouragement_design": false,
  "running_variable": "score_var",
  "cutoff": 50,
  "time_variable": "year_var",
  "group_variable": "group_var"
}

Include strategy-specific fields only when relevant:
- Instrumental Variable: instrument, is_encouragement_design
- Regression Discontinuity: running_variable, cutoff
- Difference-in-Differences: time_variable, group_variable

You MUST include strategy, treatments, outcomes, controls, effect_estimate, and standard_error.
Return ONLY the JSON, no other text."""


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class CRBExample(BaseModel):
    """A single CRB query with metadata."""

    index: int
    dataset_group: str  # "research_papers" or "textbook"
    causal_question: str
    vague_question: str
    identification_strategy: str  # gold strategy
    metadata_text: str  # loaded metadata content
    data_preview: str  # truncated CSV data
    data_path: str  # relative path to full CSV (for python_exec loading)
    gold_spec: dict  # loaded identification spec JSON
    gold_effect: float
    gold_se: float


class CRBResult(BaseModel):
    """Result for a single CRB query."""

    index: int
    gold_strategy: str
    gold_effect: float
    gold_se: float
    predicted: dict | None = None  # parsed JSON from model
    raw_response: str = ""
    error: bool = False
    # Identification metrics
    strategy_correct: bool = False
    treatments_correct: bool = False
    outcomes_correct: bool = False
    controls_correct: bool = False
    identification_correct: bool = False  # full spec correct
    # Estimation metrics
    estimation_error: float | None = None
    percentage_error: float | None = None
    within_ci: bool | None = None
    null_hypothesis_correct: bool | None = None


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class CRBAdapter:
    """Load, run, and score CausalReasoningBenchmark.

    Expects the dataset cloned to a local directory::

        git clone https://huggingface.co/datasets/syrgkanislab/CausalReasoningBenchmark data/crb

    Usage::

        adapter = CRBAdapter(data_dir="data/crb")
        examples = adapter.load()
        results = adapter.run(client, examples, model="gpt-5.4")
        benchmark = adapter.score(results, model_name="gpt-5.4")
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)

    def load(
        self,
        subset: str = "all",
        seed: int = 42,
        dev_count: int = 30,
    ) -> list[CRBExample]:
        """Load CRB examples from the dataset directory.

        Args:
            subset: "all" for full dataset (173), "dev" for subsample
            seed: random seed for dev subsampling
            dev_count: number of examples in dev mode
        """
        queries_path = self.data_dir / "causal_queries.json"
        if not queries_path.exists():
            raise FileNotFoundError(
                f"CRB queries not found: {queries_path}\n"
                "Download with: git clone "
                "https://huggingface.co/datasets/syrgkanislab/CausalReasoningBenchmark "
                "data/crb"
            )

        raw = json.loads(queries_path.read_text(encoding="utf-8"))

        # Dataset is a dict keyed by index (string), not a list
        items = raw.values() if isinstance(raw, dict) else raw

        examples = []
        for item in items:
            idx = int(item["index"])

            # Load metadata
            metadata_text = self._load_metadata(item.get("metadata_path", ""))

            # Load data preview
            data_preview = self._load_data_preview(item.get("data_path", ""))

            # Load gold identification spec
            gold_spec = self._load_identification_spec(
                item.get("identification_spec", "")
            )

            examples.append(
                CRBExample(
                    index=idx,
                    dataset_group=item.get("dataset_group", "unknown"),
                    causal_question=item.get("causal_question", ""),
                    vague_question=item.get("vague_question", ""),
                    identification_strategy=item.get("identification_strategy", ""),
                    metadata_text=metadata_text,
                    data_preview=data_preview,
                    data_path=item.get("data_path", ""),
                    gold_spec=gold_spec,
                    gold_effect=float(item.get("effect", 0.0)),
                    gold_se=float(item.get("standard_error", 0.0)),
                )
            )

        if subset == "dev":
            examples = self._deterministic_subsample(examples, seed, dev_count)

        logger.info(f"Loaded {len(examples)} CRB examples (subset={subset})")
        return examples

    def run(
        self,
        client: ModelClient,
        examples: list[CRBExample],
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        max_consecutive_errors: int = 5,
    ) -> list[CRBResult]:
        """Run the model on CRB examples and collect results."""
        results: list[CRBResult] = []
        consecutive_errors = 0

        for i, ex in enumerate(examples):
            # Load full CSV data into client's python_exec namespace (if supported)
            data_assets = self._load_data_assets(ex.data_path)
            if hasattr(client, "set_data"):
                client.set_data(data_assets if data_assets else None)

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
                predicted = self._parse_json_response(raw)
                is_error = False
                consecutive_errors = 0
            except Exception as e:
                logger.warning(f"API error on query {ex.index}: {e}")
                raw = f"ERROR: {e}"
                predicted = None
                is_error = True
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    raise RuntimeError(
                        f"Aborting: {max_consecutive_errors} consecutive API errors. "
                        f"Last error: {e}"
                    ) from e

            # Score this example
            id_metrics = self._score_identification(predicted, ex)
            est_metrics = self._score_estimation(predicted, ex)

            results.append(
                CRBResult(
                    index=ex.index,
                    gold_strategy=ex.identification_strategy,
                    gold_effect=ex.gold_effect,
                    gold_se=ex.gold_se,
                    predicted=predicted,
                    raw_response=raw,
                    error=is_error,
                    **id_metrics,
                    **est_metrics,
                )
            )

            if (i + 1) % 20 == 0:
                logger.info(f"  Progress: {i + 1}/{len(examples)}")

        return results

    def score(
        self,
        results: list[CRBResult],
        model_name: str,
        seed: int | None = None,
        prompt_version: str = "v1",
    ) -> BenchmarkResult:
        """Compute aggregate metrics and return a BenchmarkResult."""
        total = len(results)
        errors = sum(1 for r in results if r.error)
        answered = total - errors
        non_error = [r for r in results if not r.error]

        # Identification metrics
        strategy_acc = (
            sum(1 for r in non_error if r.strategy_correct) / answered
            if answered else 0.0
        )
        treatments_acc = (
            sum(1 for r in non_error if r.treatments_correct) / answered
            if answered else 0.0
        )
        outcomes_acc = (
            sum(1 for r in non_error if r.outcomes_correct) / answered
            if answered else 0.0
        )
        controls_acc = (
            sum(1 for r in non_error if r.controls_correct) / answered
            if answered else 0.0
        )
        full_id_acc = (
            sum(1 for r in non_error if r.identification_correct) / answered
            if answered else 0.0
        )

        # By strategy
        by_strategy: dict[str, dict[str, int]] = {}
        for r in non_error:
            bucket = by_strategy.setdefault(
                r.gold_strategy, {"total": 0, "strategy_ok": 0, "full_id_ok": 0}
            )
            bucket["total"] += 1
            if r.strategy_correct:
                bucket["strategy_ok"] += 1
            if r.identification_correct:
                bucket["full_id_ok"] += 1

        strategy_breakdown = {
            k: {
                "strategy_accuracy": v["strategy_ok"] / v["total"] if v["total"] else 0,
                "full_id_accuracy": v["full_id_ok"] / v["total"] if v["total"] else 0,
                "count": v["total"],
            }
            for k, v in sorted(by_strategy.items())
        }

        # Estimation metrics
        est_errors = [r.estimation_error for r in non_error if r.estimation_error is not None]
        pct_errors = [r.percentage_error for r in non_error if r.percentage_error is not None]
        within_ci = [r for r in non_error if r.within_ci is not None]
        ci_rate = (
            sum(1 for r in within_ci if r.within_ci) / len(within_ci)
            if within_ci else 0.0
        )
        null_hyp = [r for r in non_error if r.null_hypothesis_correct is not None]
        null_hyp_rate = (
            sum(1 for r in null_hyp if r.null_hypothesis_correct) / len(null_hyp)
            if null_hyp else 0.0
        )

        code_version = _git_sha()

        return BenchmarkResult(
            benchmark="crb",
            benchmark_version="v1",
            model_name=model_name,
            eval_split="all",
            metric_name="full_identification_accuracy",
            metric_value=full_id_acc,
            higher_is_better=True,
            num_examples=total,
            num_correct=sum(1 for r in non_error if r.identification_correct),
            seed=seed,
            prompt_version=prompt_version,
            code_version=code_version,
            dataset_version="v1-hf",
            completed_at=datetime.now(timezone.utc),
            status=BenchmarkStatus.SUCCESS,
            summary={
                "strategy_accuracy": strategy_acc,
                "treatments_accuracy": treatments_acc,
                "outcomes_accuracy": outcomes_acc,
                "controls_accuracy": controls_acc,
                "full_identification_accuracy": full_id_acc,
                "by_strategy": strategy_breakdown,
                "mean_estimation_error": (
                    sum(est_errors) / len(est_errors) if est_errors else None
                ),
                "median_percentage_error": (
                    sorted(pct_errors)[len(pct_errors) // 2] if pct_errors else None
                ),
                "within_ci_rate": ci_rate,
                "null_hypothesis_accuracy": null_hyp_rate,
                "errors": errors,
                "answered": answered,
            },
        )

    def save_results(
        self,
        results: list[CRBResult],
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
    # Prompt composition
    # -----------------------------------------------------------------------

    def _compose_prompt(self, ex: CRBExample) -> str:
        """Compose the prompt for a single CRB query."""
        parts = []

        if ex.metadata_text:
            parts.append(f"Dataset metadata:\n{ex.metadata_text}")

        if ex.data_preview:
            parts.append(f"Data (first rows):\n{ex.data_preview}")

        parts.append(f"Research question: {ex.causal_question}")
        parts.append(OUTPUT_FORMAT)

        return "\n\n".join(parts)

    # -----------------------------------------------------------------------
    # Response parsing
    # -----------------------------------------------------------------------

    @staticmethod
    def _parse_json_response(raw: str) -> dict | None:
        """Extract JSON object from model response."""
        text = raw.strip()
        # Remove markdown fences
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Find JSON object in text
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
        logger.warning(f"Failed to parse JSON from CRB response: {text[:200]}")
        return None

    # -----------------------------------------------------------------------
    # Scoring — Identification
    # -----------------------------------------------------------------------

    @staticmethod
    def _score_identification(predicted: dict | None, ex: CRBExample) -> dict:
        """Score identification metrics against gold spec."""
        if predicted is None:
            return {
                "strategy_correct": False,
                "treatments_correct": False,
                "outcomes_correct": False,
                "controls_correct": False,
                "identification_correct": False,
            }

        gold = ex.gold_spec

        # Strategy
        pred_strategy = (predicted.get("strategy") or "").strip()
        gold_strategy = ex.identification_strategy.strip()
        strategy_ok = pred_strategy.lower() == gold_strategy.lower()

        # Treatments
        pred_treatments = _normalize_var_set(predicted.get("treatments", []))
        gold_treatments = _normalize_var_set(gold.get("treatments", []))
        treatments_ok = pred_treatments == gold_treatments

        # Outcomes
        pred_outcomes = _normalize_var_set(predicted.get("outcomes", []))
        gold_outcomes = _normalize_var_set(gold.get("outcomes", []))
        outcomes_ok = pred_outcomes == gold_outcomes

        # Controls — gold uses "minimal_controlling_set" and checks
        # post_treatment_variables are excluded
        gold_controls = _normalize_var_set(
            gold.get("minimal_controlling_set", gold.get("controls", []))
        )
        gold_post_treatment = _normalize_var_set(
            gold.get("post_treatment_variables", [])
        )
        pred_controls = _normalize_var_set(predicted.get("controls", []))

        # Controls correct = gold controls subset of predicted AND
        # no post-treatment variables included
        controls_subset_ok = gold_controls.issubset(pred_controls)
        no_post_treatment = not pred_controls.intersection(gold_post_treatment)
        controls_ok = controls_subset_ok and no_post_treatment

        # Full identification = all above correct
        full_ok = strategy_ok and treatments_ok and outcomes_ok and controls_ok

        return {
            "strategy_correct": strategy_ok,
            "treatments_correct": treatments_ok,
            "outcomes_correct": outcomes_ok,
            "controls_correct": controls_ok,
            "identification_correct": full_ok,
        }

    # -----------------------------------------------------------------------
    # Scoring — Estimation
    # -----------------------------------------------------------------------

    @staticmethod
    def _score_estimation(predicted: dict | None, ex: CRBExample) -> dict:
        """Score estimation metrics against gold effect and SE."""
        if predicted is None:
            return {
                "estimation_error": None,
                "percentage_error": None,
                "within_ci": None,
                "null_hypothesis_correct": None,
            }

        pred_effect = predicted.get("effect_estimate")
        pred_se = predicted.get("standard_error")

        if pred_effect is None:
            return {
                "estimation_error": None,
                "percentage_error": None,
                "within_ci": None,
                "null_hypothesis_correct": None,
            }

        try:
            pred_effect = float(pred_effect)
        except (ValueError, TypeError):
            return {
                "estimation_error": None,
                "percentage_error": None,
                "within_ci": None,
                "null_hypothesis_correct": None,
            }

        gold_effect = ex.gold_effect
        gold_se = ex.gold_se

        # Absolute estimation error
        est_error = abs(pred_effect - gold_effect)

        # Percentage error
        pct_error = (
            (est_error / abs(gold_effect)) * 100 if gold_effect != 0 else None
        )

        # Within 95% CI of gold: gold_effect +/- 1.96 * gold_se
        if gold_se > 0:
            ci_lower = gold_effect - 1.96 * gold_se
            ci_upper = gold_effect + 1.96 * gold_se
            within = ci_lower <= pred_effect <= ci_upper
        else:
            within = pred_effect == gold_effect

        # Null hypothesis decision: both reject or both fail to reject at alpha=0.05
        # H0: effect = 0. Reject if |effect/se| > 1.96
        null_correct = None
        if pred_se is not None:
            try:
                pred_se = float(pred_se)
                if pred_se > 0 and gold_se > 0:
                    gold_reject = abs(gold_effect / gold_se) > 1.96
                    pred_reject = abs(pred_effect / pred_se) > 1.96
                    null_correct = gold_reject == pred_reject
            except (ValueError, TypeError):
                pass

        return {
            "estimation_error": est_error,
            "percentage_error": pct_error,
            "within_ci": within,
            "null_hypothesis_correct": null_correct,
        }

    # -----------------------------------------------------------------------
    # Data loading helpers
    # -----------------------------------------------------------------------

    def _load_data_assets(self, rel_path: str) -> list[dict]:
        """Load full CSV as data assets for python_exec namespace."""
        import csv as csv_mod

        if not rel_path:
            return []
        path = self.data_dir / rel_path
        if not path.exists():
            return []
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                reader = csv_mod.DictReader(f)
                data = list(reader)
            if data:
                return [{"data": data, "format": "tabular"}]
        except Exception as e:
            logger.warning(f"Error loading {path} as data asset: {e}")
        return []

    def _load_metadata(self, rel_path: str) -> str:
        """Load metadata text file."""
        if not rel_path:
            return ""
        path = self.data_dir / rel_path
        if not path.exists():
            logger.warning(f"Metadata not found: {path}")
            return ""
        try:
            return path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception as e:
            logger.warning(f"Error reading metadata {path}: {e}")
            return ""

    def _load_data_preview(self, rel_path: str) -> str:
        """Load CSV data file and return truncated preview."""
        if not rel_path:
            return ""
        path = self.data_dir / rel_path
        if not path.exists():
            logger.warning(f"Data file not found: {path}")
            return ""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.strip().split("\n")
            if len(lines) > MAX_DATA_ROWS + 1:
                truncated = lines[: MAX_DATA_ROWS + 1]
                truncated.append(f"... ({len(lines) - MAX_DATA_ROWS - 1} more rows)")
                text = "\n".join(truncated)
            if len(text) > MAX_DATA_CHARS:
                text = text[:MAX_DATA_CHARS] + "\n... (data truncated)"
            return text
        except Exception as e:
            logger.warning(f"Error reading data {path}: {e}")
            return ""

    def _load_identification_spec(self, rel_path: str) -> dict:
        """Load gold identification spec JSON."""
        if not rel_path:
            return {}
        path = self.data_dir / rel_path
        if not path.exists():
            logger.warning(f"Identification spec not found: {path}")
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Error reading spec {path}: {e}")
            return {}

    # -----------------------------------------------------------------------
    # Subsampling
    # -----------------------------------------------------------------------

    @staticmethod
    def _deterministic_subsample(
        examples: list[CRBExample],
        seed: int,
        count: int,
    ) -> list[CRBExample]:
        """Balanced subsample across strategies."""
        import random

        rng = random.Random(seed)

        by_strategy: dict[str, list[CRBExample]] = {}
        for ex in examples:
            by_strategy.setdefault(ex.identification_strategy, []).append(ex)

        n_strategies = len(by_strategy)
        per_strategy = max(1, count // n_strategies)

        selected = []
        for strategy in sorted(by_strategy.keys()):
            pool = by_strategy[strategy]
            rng.shuffle(pool)
            selected.extend(pool[:per_strategy])

        if len(selected) < count:
            used = {ex.index for ex in selected}
            remaining = [ex for ex in examples if ex.index not in used]
            rng.shuffle(remaining)
            selected.extend(remaining[: count - len(selected)])

        return selected[:count]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_var_set(vars_: list | None) -> frozenset[str]:
    """Normalize a list of variable names to a comparable frozenset."""
    if not vars_:
        return frozenset()
    return frozenset(v.strip().lower() for v in vars_ if isinstance(v, str))


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
