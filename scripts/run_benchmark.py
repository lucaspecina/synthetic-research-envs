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
    from sreg.inference.openai_client import OpenAIClient

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

    base_client = OpenAIClient(**kwargs)

    if args.with_tools:
        from sreg.inference.tool_client import ToolEnrichedClient
        logger.info("Tools enabled: python_exec + think")
        return ToolEnrichedClient(base_client)

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
    output_dir = Path(f"experiments/benchmarks/cladder_{timestamp}")
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
    output_dir = Path(f"experiments/benchmarks/qrdata_{timestamp}")
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


def run_discoverybench(args: argparse.Namespace) -> None:
    """Run DiscoveryBench benchmark."""
    from sreg.benchmarks.discoverybench import DiscoveryBenchAdapter

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

    # Setup
    client = _make_client(args)
    model_name = args.model or "gpt-4o"
    adapter = DiscoveryBenchAdapter(data_path=data_path)

    # Load
    logger.info(f"Loading DiscoveryBench dataset (subset={args.subset})...")
    examples = adapter.load(subset=args.subset, seed=args.seed)
    logger.info(f"  {len(examples)} examples loaded")

    # Run (generate hypotheses)
    logger.info(f"Running model={model_name}, temperature={args.temperature}...")
    results = adapter.run(
        client, examples, model=args.model, temperature=args.temperature
    )

    # Score (HMS via LLM — this makes additional API calls)
    logger.info("Scoring with HMS (LLM-based, this will make additional API calls)...")
    benchmark = adapter.score(
        results, client, model_name=model_name, model=args.model, seed=args.seed
    )

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"experiments/benchmarks/discoverybench_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    adapter.save_results(results, output_dir / "results.jsonl")

    bench_path = output_dir / "benchmark.json"
    bench_path.write_text(benchmark.model_dump_json(indent=2), encoding="utf-8")

    # Print summary
    print()
    print(f"=== DiscoveryBench Results ({model_name}) ===")
    print(f"  Mean HMS: {benchmark.metric_value:.3f}")
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


BENCHMARKS = {
    "cladder": run_cladder,
    "qrdata": run_qrdata,
    "discoverybench": run_discoverybench,
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
    args = parser.parse_args()

    runner = BENCHMARKS[args.benchmark]
    runner(args)


if __name__ == "__main__":
    main()
