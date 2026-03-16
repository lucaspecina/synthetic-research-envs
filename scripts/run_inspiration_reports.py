"""Generate Inspiration Reports for existing eval experiments.

Reads each eval's src.json + its matching seed file, and produces
an inspiration_report.md in each experiment directory.

Usage:
    python scripts/run_inspiration_reports.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from openai import OpenAI

from sreg.harness.inspiration_report import generate_report
from sreg.models.task import Task
from sreg.models.world import World

# Map each eval to its seed file
EVAL_SEEDS = {
    "eval_alcohol": "seeds/alcohol_covid_hcw.md",
    "eval_coral": "seeds/coral_reef_bleaching.md",
    "eval_poverty": "seeds/poverty_reduction_china.md",
    "eval_school": "seeds/school_performance.md",
    "eval_smoking": "seeds/smoking_birthweight.md",
    "eval_soil": "seeds/soil_heavy_metals.md",
    "eval_vaca_muerta": "seeds/causal_observational.pdf",
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_seed(seed_path: str) -> str:
    """Read seed file content (markdown or PDF)."""
    full_path = os.path.join(BASE_DIR, seed_path)
    if seed_path.endswith(".pdf"):
        try:
            import pymupdf

            doc = pymupdf.open(full_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except ImportError:
            print(f"  pymupdf not installed, skipping PDF: {seed_path}")
            return ""
    else:
        with open(full_path, encoding="utf-8") as f:
            return f.read()


def main():
    base_url = os.environ.get("AZURE_FOUNDRY_BASE_URL")
    api_key = os.environ.get("AZURE_INFERENCE_CREDENTIAL")
    model = os.environ.get("AZURE_MODEL", "gpt-5.2-chat")

    if not base_url or not api_key:
        print("ERROR: Set AZURE_FOUNDRY_BASE_URL and AZURE_INFERENCE_CREDENTIAL")
        sys.exit(1)

    client = OpenAI(base_url=base_url, api_key=api_key)

    experiments_dir = os.path.join(BASE_DIR, "experiments")

    for eval_name, seed_path in EVAL_SEEDS.items():
        eval_dir = os.path.join(experiments_dir, eval_name)
        src_path = os.path.join(eval_dir, "src.json")
        report_path = os.path.join(eval_dir, "inspiration_report.md")

        if not os.path.exists(src_path):
            print(f"SKIP {eval_name}: no src.json")
            continue

        print(f"\n{'='*60}")
        print(f"Generating report for {eval_name}")
        print(f"  Seed: {seed_path}")

        # Read seed
        seed_text = read_seed(seed_path)
        if not seed_text:
            print(f"  SKIP: empty seed")
            continue

        # Load SRC
        with open(src_path, encoding="utf-8") as f:
            src_data = json.load(f)

        world = World(**src_data["world"])
        tasks = [Task(**t) for t in src_data["tasks"]]

        # Generate report
        try:
            report = generate_report(
                seed_text=seed_text,
                world=world,
                tasks=tasks,
                client=client,
                model=model,
            )

            # Write report
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report.to_markdown())

            print(f"  Saved: {report_path}")

        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == "__main__":
    main()
