#!/usr/bin/env python
"""Run an external benchmark evaluation.

Usage:
    python scripts/run_benchmark.py --benchmark cladder --model gpt-4o --subset dev
    python scripts/run_benchmark.py --benchmark cladder --model qwen3-8b --subset all
    python scripts/run_benchmark.py --benchmark cladder --data data/cladder-v1-balanced.json

Results are saved to experiments/benchmarks/<benchmark>_<timestamp>/
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
from datetime import datetime
from pathlib import Path

# Windows cp1252 can't handle Unicode from model responses — force UTF-8
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_benchmark")


def _make_client(args: argparse.Namespace):
    """Build the appropriate ModelClient based on CLI flags."""
    backend = getattr(args, "backend", "azure")

    kwargs = {}
    if args.model:
        kwargs["model"] = args.model
    if args.base_url:
        kwargs["base_url"] = args.base_url
    if args.api_key:
        api_key = args.api_key
        if api_key.lower() == "none":
            api_key = "not-needed"
        kwargs["api_key"] = api_key

    if backend == "vllm":
        from sreg.inference.chat_client import ChatCompletionsClient
        # Only inject Qwen thinking-mode override when targeting a custom server
        # (not when testing Chat Completions path against Azure)
        if args.base_url:
            kwargs.setdefault("extra_body", {
                "chat_template_kwargs": {"enable_thinking": False},
            })
        base_client = ChatCompletionsClient(**kwargs)
        logger.info(f"Backend: Chat Completions (vLLM) — model={kwargs.get('model')}")
    else:
        from sreg.inference.openai_client import OpenAIClient
        base_client = OpenAIClient(**kwargs)
        logger.info(f"Backend: Responses API (Azure) — model={kwargs.get('model')}")

    if args.with_tools:
        from sreg.inference.tool_client import ToolEnrichedClient
        # max_iterations=20 matches the SREG solver (oi_driver.py:329)
        logger.info("Tools enabled: python_exec + think (max_iterations=20)")
        return ToolEnrichedClient(base_client, max_iterations=20)

    return base_client


def run_cladder(args: argparse.Namespace) -> None:
    """Run CLadder benchmark."""
    from sreg.benchmarks.cladder import CLadderAdapter

    data_path = args.data or "data/cladder-v1-q-balanced.json"
    if not Path(data_path).exists():
        logger.error(f"Dataset not found: {data_path}")
        logger.info("Download CLadder dataset:")
        logger.info(
            "  curl -L -o data/cladder-v1.zip "
            "https://raw.githubusercontent.com/causalNLP/cladder/main/"
            "data/cladder-v1.zip"
        )
        logger.info("  unzip data/cladder-v1.zip -d data/")
        sys.exit(1)

    # Setup
    client = _make_client(args)
    model_name = args.model or "gpt-4o"
    adapter = CLadderAdapter(data_path=data_path)

    # Load
    logger.info(f"Loading CLadder dataset (subset={args.subset})...")
    examples = adapter.load(subset=args.subset, seed=args.seed)
    logger.info(f"  {len(examples)} examples loaded")

    # Run
    logger.info(f"Running model={model_name}, temperature={args.temperature}...")
    results = adapter.run(
        client, examples, model=args.model, temperature=args.temperature
    )

    # Score
    benchmark = adapter.score(results, model_name=model_name, seed=args.seed)

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"experiments/benchmarks/before_v1/cladder_{model_name}_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    adapter.save_results(results, output_dir / "results.jsonl")

    bench_path = output_dir / "benchmark.json"
    bench_path.write_text(benchmark.model_dump_json(indent=2), encoding="utf-8")

    # Print summary
    print()
    print(f"=== CLadder Results ({args.model}) ===")
    print(f"  Overall accuracy: {benchmark.metric_value:.1%}")
    print(f"  Examples: {benchmark.num_examples}")
    print(f"  Correct: {benchmark.num_correct}")
    print(f"  Unparseable: {benchmark.summary.get('unparseable', 0)}")
    print()

    by_rung = benchmark.summary.get("by_rung", {})
    if by_rung:
        print("  By rung:")
        for rung, acc in sorted(by_rung.items()):
            print(f"    {rung}: {acc:.1%}")
        print()

    by_type = benchmark.summary.get("by_query_type", {})
    if by_type:
        print("  By query type:")
        for qtype, acc in sorted(by_type.items()):
            print(f"    {qtype}: {acc:.1%}")
        print()

    by_sensical = benchmark.summary.get("by_sensical", {})
    if by_sensical:
        print("  By sensical variant:")
        for variant, acc in sorted(by_sensical.items()):
            print(f"    {variant}: {acc:.1%}")
        print()

    print(f"  Results saved to: {output_dir}")


def run_qrdata(args: argparse.Namespace) -> None:
    """Run QRData benchmark."""
    from sreg.benchmarks.qrdata import QRDataAdapter

    data_path = args.data or "data/QRData.json"
    csv_dir = "data/qrdata_csvs/data"
    if not Path(data_path).exists():
        logger.error(f"Dataset not found: {data_path}")
        logger.info("Download QRData dataset:")
        logger.info(
            "  curl -L -o data/QRData.json "
            "https://raw.githubusercontent.com/xxxiaol/QRData/main/benchmark/QRData.json"
        )
        logger.info(
            "  curl -L -o data/qrdata-csvs.zip "
            "https://raw.githubusercontent.com/xxxiaol/QRData/main/benchmark/data.zip"
        )
        logger.info("  unzip data/qrdata-csvs.zip -d data/qrdata_csvs/")
        sys.exit(1)

    # Setup
    client = _make_client(args)
    model_name = args.model or "gpt-4o"
    subset = args.subset
    adapter = QRDataAdapter(data_path=data_path, csv_dir=csv_dir)

    # Load
    logger.info(f"Loading QRData dataset (subset={subset})...")
    examples = adapter.load(subset=subset, seed=args.seed)
    logger.info(f"  {len(examples)} examples loaded")

    # Run
    logger.info(f"Running model={model_name}, temperature={args.temperature}...")
    results = adapter.run(
        client, examples, model=args.model, temperature=args.temperature
    )

    # Score
    benchmark = adapter.score(results, model_name=model_name, seed=args.seed)

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"experiments/benchmarks/before_v1/qrdata_{model_name}_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    adapter.save_results(results, output_dir / "results.jsonl")

    bench_path = output_dir / "benchmark.json"
    bench_path.write_text(benchmark.model_dump_json(indent=2), encoding="utf-8")

    # Print summary
    print()
    print(f"=== QRData Results ({args.model}) ===")
    print(f"  Overall accuracy: {benchmark.metric_value:.1%}")
    print(f"  Examples: {benchmark.num_examples}")
    print(f"  Correct: {benchmark.num_correct}")
    print(f"  Causal accuracy: {benchmark.summary.get('causal_accuracy', 0):.1%}")
    print(f"  Statistical accuracy: {benchmark.summary.get('statistical_accuracy', 0):.1%}")
    print(f"  Unparseable: {benchmark.summary.get('unparseable', 0)}")
    print(f"  Errors: {benchmark.summary.get('errors', 0)}")
    print()

    by_type = benchmark.summary.get("by_question_type", {})
    if by_type:
        print("  By question type:")
        for qtype, acc in sorted(by_type.items()):
            print(f"    {qtype}: {acc:.1%}")
        print()

    print(f"  Results saved to: {output_dir}")


def _make_judge_client(args: argparse.Namespace):
    """Build a separate client for LLM-judge scoring (oracle separation).

    Uses --judge-model (defaults to AZURE_MODEL / gpt-5.4) regardless of
    the generator model. This ensures the same judge scores all runs.
    """
    from sreg.inference.openai_client import OpenAIClient

    judge_model = getattr(args, "judge_model", None)
    # Judge always uses Azure (the reference endpoint), never vLLM
    return OpenAIClient(model=judge_model), judge_model


def run_discoverybench(args: argparse.Namespace) -> None:
    """Run DiscoveryBench benchmark with multi-seed HMS scoring.

    Generation runs once (deterministic at temp=0.0). HMS scoring runs
    N_JUDGE_SEEDS times because the LLM judge is non-deterministic.
    Per-example score = median of N runs. Report includes std across runs.
    """
    import statistics

    from sreg.benchmarks.discoverybench import DiscoveryBenchAdapter

    JUDGE_SEEDS = [42, 0, 7]  # harness_decisions_v1.md D-DB-03

    # Train split has gold hypotheses; test split does not (held-out).
    data_path = args.data or "data/discoverybench_train.csv"
    if not Path(data_path).exists():
        logger.error(f"Dataset not found: {data_path}")
        logger.info("Download DiscoveryBench dataset:")
        logger.info(
            "  curl -L -o data/discoverybench_train.csv "
            "https://huggingface.co/datasets/allenai/discoverybench/"
            "resolve/main/train_relevant.csv"
        )
        sys.exit(1)

    # Setup — generator client (may be Qwen via vLLM) vs judge client (always Azure)
    client = _make_client(args)
    judge_client, judge_model = _make_judge_client(args)
    model_name = args.model or "gpt-4o"
    adapter = DiscoveryBenchAdapter(data_path=data_path)

    # Load
    logger.info(f"Loading DiscoveryBench dataset (subset={args.subset})...")
    examples = adapter.load(subset=args.subset, seed=args.seed)
    logger.info(f"  {len(examples)} examples loaded")

    # Run ONCE (generation is deterministic at temp=0.0)
    logger.info(f"Running model={model_name}, temperature={args.temperature}...")
    results = adapter.run(
        client, examples, model=args.model, temperature=args.temperature
    )

    # Score N times (HMS judge is non-deterministic)
    # Collect per-example HMS scores across judge runs
    all_run_scores: list[list[float]] = []  # [run][example]
    all_benchmarks = []

    for run_idx, judge_seed in enumerate(JUDGE_SEEDS):
        logger.info(
            f"HMS scoring run {run_idx + 1}/{len(JUDGE_SEEDS)} "
            f"(judge={judge_model or 'AZURE_MODEL default'})..."
        )
        benchmark = adapter.score(
            results, judge_client, model_name=model_name, model=judge_model,
            seed=judge_seed,
        )
        all_benchmarks.append(benchmark)
        # Extract per-example HMS from the scored results
        run_scores = [r.hms_score for r in results if not r.error]
        all_run_scores.append(run_scores)

    # Compute per-example median across judge runs
    n_examples = len(all_run_scores[0]) if all_run_scores else 0
    median_scores = []
    for i in range(n_examples):
        example_scores = [run[i] for run in all_run_scores if i < len(run)]
        median_scores.append(statistics.median(example_scores))

    mean_of_medians = statistics.mean(median_scores) if median_scores else 0.0
    # Std across run means (variability of the judge)
    run_means = [b.metric_value for b in all_benchmarks]
    std_across_runs = statistics.stdev(run_means) if len(run_means) > 1 else 0.0

    # Use last benchmark as template, override with median-based scores
    benchmark = all_benchmarks[-1]
    benchmark.metric_value = mean_of_medians
    benchmark.summary["mean_hms_median"] = mean_of_medians
    benchmark.summary["run_means"] = run_means
    benchmark.summary["std_across_runs"] = std_across_runs
    benchmark.summary["judge_seeds"] = JUDGE_SEEDS
    benchmark.summary["judge_model"] = judge_model or "AZURE_MODEL_default"

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"experiments/benchmarks/before_v1/discoverybench_{model_name}_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    adapter.save_results(results, output_dir / "results.jsonl")

    bench_path = output_dir / "benchmark.json"
    bench_path.write_text(benchmark.model_dump_json(indent=2), encoding="utf-8")

    # Save per-run details
    for i, bm in enumerate(all_benchmarks):
        run_path = output_dir / f"benchmark_run{i}_seed{JUDGE_SEEDS[i]}.json"
        run_path.write_text(bm.model_dump_json(indent=2), encoding="utf-8")

    # Print summary
    print()
    print(f"=== DiscoveryBench Results ({model_name}) ===")
    print(f"  Mean HMS (median of {len(JUDGE_SEEDS)} judge runs): {mean_of_medians:.3f}")
    print(f"  Std across runs: {std_across_runs:.3f}")
    print(f"  Per-run means: {', '.join(f'{m:.3f}' for m in run_means)}")
    print(f"  Judge model: {judge_model or 'AZURE_MODEL default'}")
    print(f"  Examples: {benchmark.num_examples}")
    print(f"  Above 0.50: {benchmark.summary.get('above_50', 0)}")
    print(f"  Above 0.25: {benchmark.summary.get('above_25', 0)}")
    print(f"  Errors: {benchmark.summary.get('errors', 0)}")
    print()

    by_domain = benchmark.summary.get("by_domain", {})
    if by_domain:
        print("  By domain:")
        for domain, score in sorted(by_domain.items()):
            print(f"    {domain}: {score:.3f}")
        print()

    by_type = benchmark.summary.get("by_question_type", {})
    if by_type:
        print("  By question type:")
        for qtype, score in sorted(by_type.items()):
            print(f"    {qtype}: {score:.3f}")
        print()

    print(f"  Results saved to: {output_dir}")


def run_crb(args: argparse.Namespace) -> None:
    """Run CausalReasoningBenchmark (CRB)."""
    from sreg.benchmarks.causalreasoning import CRBAdapter

    data_dir = args.data or "data/crb"
    if not Path(data_dir).exists():
        logger.error(f"CRB dataset not found: {data_dir}")
        logger.info("Download CRB dataset:")
        logger.info(
            "  git clone "
            "https://huggingface.co/datasets/syrgkanislab/CausalReasoningBenchmark "
            "data/crb"
        )
        sys.exit(1)

    # Setup
    client = _make_client(args)
    model_name = args.model or "gpt-4o"
    adapter = CRBAdapter(data_dir=data_dir)

    # Load
    logger.info(f"Loading CRB dataset (subset={args.subset})...")
    examples = adapter.load(subset=args.subset, seed=args.seed)
    logger.info(f"  {len(examples)} examples loaded")

    # Run
    logger.info(f"Running model={model_name}, temperature={args.temperature}...")
    results = adapter.run(
        client, examples, model=args.model, temperature=args.temperature
    )

    # Score
    benchmark = adapter.score(results, model_name=model_name, seed=args.seed)

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"experiments/benchmarks/before_v1/crb_{model_name}_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    adapter.save_results(results, output_dir / "results.jsonl")

    bench_path = output_dir / "benchmark.json"
    bench_path.write_text(benchmark.model_dump_json(indent=2), encoding="utf-8")

    # Print summary
    print()
    print(f"=== CRB Results ({model_name}) ===")
    print(f"  Full identification accuracy: {benchmark.metric_value:.1%}")
    print(f"  Examples: {benchmark.num_examples}")
    print(f"  Answered: {benchmark.summary.get('answered', 0)}")
    print(f"  Errors: {benchmark.summary.get('errors', 0)}")
    print()

    summary = benchmark.summary
    print(f"  Strategy accuracy:   {summary.get('strategy_accuracy', 0):.1%}")
    print(f"  Treatments accuracy: {summary.get('treatments_accuracy', 0):.1%}")
    print(f"  Outcomes accuracy:   {summary.get('outcomes_accuracy', 0):.1%}")
    print(f"  Controls accuracy:   {summary.get('controls_accuracy', 0):.1%}")
    print()

    if summary.get("within_ci_rate") is not None:
        print(f"  Within 95% CI rate:       {summary['within_ci_rate']:.1%}")
    if summary.get("null_hypothesis_accuracy") is not None:
        print(f"  Null hypothesis accuracy: {summary['null_hypothesis_accuracy']:.1%}")
    if summary.get("median_percentage_error") is not None:
        print(f"  Median % error:           {summary['median_percentage_error']:.1f}%")
    print()

    by_strategy = summary.get("by_strategy", {})
    if by_strategy:
        print("  By strategy:")
        for strat, info in sorted(by_strategy.items()):
            print(
                f"    {strat}: strategy={info['strategy_accuracy']:.0%}, "
                f"full_id={info['full_id_accuracy']:.0%} (n={info['count']})"
            )
        print()

    print(f"  Results saved to: {output_dir}")


BENCHMARKS = {
    "cladder": run_cladder,
    "qrdata": run_qrdata,
    "discoverybench": run_discoverybench,
    "crb": run_crb,
}


def main():
    parser = argparse.ArgumentParser(description="Run external benchmark evaluation")
    parser.add_argument(
        "--benchmark", "-b",
        required=True,
        choices=list(BENCHMARKS.keys()),
        help="Benchmark to run",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Model name (default: from AZURE_MODEL env var or gpt-4o)",
    )
    parser.add_argument(
        "--subset", "-s",
        default="dev",
        choices=["dev", "all", "causal", "statistical"],
        help="Dataset subset: 'dev', 'all', 'causal' (QRData), 'statistical' (QRData)",
    )
    parser.add_argument(
        "--data", "-d",
        default=None,
        help="Path to dataset file (default: data/<benchmark>-v1-balanced.json)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic subsampling (default: 42)",
    )
    parser.add_argument(
        "--temperature", "-t",
        type=float,
        default=0.0,
        help="Sampling temperature (default: 0.0 for deterministic)",
    )
    parser.add_argument(
        "--with-tools",
        action="store_true",
        help="Give the model python_exec + think tools (solver capabilities). "
             "Especially useful for QRData where data analysis improves scores.",
    )
    parser.add_argument(
        "--backend",
        choices=["azure", "vllm"],
        default="azure",
        help="LLM backend: 'azure' (Responses API) or 'vllm' (Chat Completions). "
             "Default: azure.",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Base URL for LLM backend (default: AZURE_FOUNDRY_BASE_URL). "
             "Use http://localhost:8000/v1 for vLLM.",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key for LLM backend (default: AZURE_INFERENCE_CREDENTIAL). "
             "Use 'none' for vLLM.",
    )
    parser.add_argument(
        "--judge-model",
        type=str,
        default=None,
        help="Model for LLM-judge scoring (DiscoveryBench HMS). "
             "Default: AZURE_MODEL (gpt-5.4). Must differ from generator "
             "model for oracle separation.",
    )
    args = parser.parse_args()

    runner = BENCHMARKS[args.benchmark]
    runner(args)


if __name__ == "__main__":
    main()
