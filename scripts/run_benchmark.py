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
import logging
import sys
from datetime import datetime
from pathlib import Path

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


def run_cladder(args: argparse.Namespace) -> None:
    """Run CLadder benchmark."""
    from sreg.benchmarks.cladder import CLadderAdapter
    from sreg.inference.openai_client import OpenAIClient

    data_path = args.data or "data/cladder-v1-balanced.json"
    if not Path(data_path).exists():
        logger.error(f"Dataset not found: {data_path}")
        logger.info("Download CLadder dataset:")
        logger.info(
            "  curl -L -o data/cladder-v1-balanced.json "
            "https://raw.githubusercontent.com/causalNLP/cladder/main/"
            "data/cladder-v1-balanced.json"
        )
        sys.exit(1)

    # Setup
    client = OpenAIClient(model=args.model)
    adapter = CLadderAdapter(data_path=data_path)

    # Load
    logger.info(f"Loading CLadder dataset (subset={args.subset})...")
    examples = adapter.load(subset=args.subset, seed=args.seed)
    logger.info(f"  {len(examples)} examples loaded")

    # Run
    logger.info(f"Running model={args.model}, temperature={args.temperature}...")
    results = adapter.run(
        client, examples, model=args.model, temperature=args.temperature
    )

    # Score
    benchmark = adapter.score(results, model_name=args.model, seed=args.seed)

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


BENCHMARKS = {
    "cladder": run_cladder,
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
        choices=["dev", "all"],
        help="Dataset subset: 'dev' (100 examples) or 'all' (full dataset)",
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
    args = parser.parse_args()

    runner = BENCHMARKS[args.benchmark]
    runner(args)


if __name__ == "__main__":
    main()
