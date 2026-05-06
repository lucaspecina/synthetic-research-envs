"""Harness manual: corre Paper Digestion sobre un set de seeds y deja
los `PaperInsights` como JSON para revisión humana.

Uso::

    python scripts/run_paper_digestion.py
    # o con seeds custom:
    python scripts/run_paper_digestion.py --seeds selection_bias_police confounding_by_indication

Output: `experiments/paper_digestion/<timestamp>/<seed_id>.json` por cada seed.
Stdout: resumen amigable de cada PaperInsights (mecanismos, frases prohibidas, etc).

Codex pidió esto como instrumento de validación principal en lugar de pytest:
para juzgar si un agente "entiende" un seed, un test verde/rojo no sirve —
necesitás artefactos inspeccionables.
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from datetime import datetime
from pathlib import Path

from sreg.inference.openai_client import OpenAIClient
from sreg.v1_5.agents import PaperDigestionAgent

ROOT = Path(__file__).resolve().parent.parent
SEEDS_DIR = ROOT / "seeds"
OUT_BASE = ROOT / "experiments" / "paper_digestion"

DEFAULT_SEEDS = [
    "selection_bias_police",
    "confounding_by_indication",
    "identifiability_pollution",
]


def _read_seed(seed_id: str) -> str:
    md_path = SEEDS_DIR / f"{seed_id}.md"
    if md_path.exists():
        return md_path.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"No encontré seed '{seed_id}.md' en {SEEDS_DIR}. "
        f"Disponibles: {sorted(p.stem for p in SEEDS_DIR.glob('*.md'))}"
    )


def _print_summary(seed_id: str, insights_dict: dict) -> None:
    """Resumen amigable a stdout para revisión humana rápida."""
    print(f"\n{'=' * 70}")
    print(f"Seed: {seed_id}")
    print(f"{'=' * 70}")
    print(f"Objective: {insights_dict.get('objective', '<missing>')}")

    entities = insights_dict.get("entities", [])
    print(f"\nEntities ({len(entities)}):")
    for e in entities:
        print(f"  - {e}")

    mechanisms = insights_dict.get("mechanisms", [])
    print(f"\nMechanisms ({len(mechanisms)}):")
    for m in mechanisms:
        print(f"  - {textwrap.shorten(m, width=110)}")

    phenomena = insights_dict.get("phenomena", [])
    print(f"\nPhenomena ({len(phenomena)}):")
    for p in phenomena:
        print(f"  - {textwrap.shorten(p, width=110)}")

    capsule = insights_dict.get("narrative_capsule") or {}
    print("\nNarrative capsule:")
    print(f"  domain     : {capsule.get('domain', '<missing>')}")
    print(f"  population : {capsule.get('population', '<missing>')}")
    forbidden = capsule.get("forbidden_phrases", [])
    print(f"  forbidden  ({len(forbidden)}):")
    for fp in forbidden:
        print(f"    - {textwrap.shorten(fp, width=100)}")
    style = capsule.get("natural_question_style", [])
    print(f"  question_style ({len(style)}):")
    for s in style:
        print(f"    - {textwrap.shorten(s, width=100)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seeds",
        nargs="+",
        default=DEFAULT_SEEDS,
        help="seed_ids (sin extensión .md) a digerir",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override del modelo (default: AZURE_MODEL del .env)",
    )
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT_BASE / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    client = OpenAIClient(model=args.model)
    agent = PaperDigestionAgent(client, model=args.model)

    print(f"Modelo: {client.default_model}")
    print(f"Output dir: {out_dir}")
    print(f"Seeds: {args.seeds}\n")

    for seed_id in args.seeds:
        try:
            paper_text = _read_seed(seed_id)
        except FileNotFoundError as e:
            print(f"[SKIP] {seed_id}: {e}", file=sys.stderr)
            continue

        print(f"-> Digesting {seed_id} ...", end=" ", flush=True)
        try:
            insights = agent.digest(paper_text=paper_text, paper_id=seed_id)
        except Exception as e:
            print(f"FAIL: {e}", file=sys.stderr)
            (out_dir / f"{seed_id}.error.txt").write_text(
                f"{type(e).__name__}: {e}", encoding="utf-8"
            )
            continue

        # Persistir JSON.
        out_path = out_dir / f"{seed_id}.json"
        out_path.write_text(
            insights.model_dump_json(indent=2),
            encoding="utf-8",
        )
        print(f"OK -> {out_path.relative_to(ROOT)}")

        # Resumen humano.
        _print_summary(seed_id, json.loads(insights.model_dump_json()))

    print(f"\n{'=' * 70}")
    print(f"Listo. Artefactos en: {out_dir}")
    print("Revisá los JSON antes de avanzar al Architect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
