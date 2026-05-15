"""Harness manual: corre `ValidatorAgent` sobre WorldSpecs ya
producidos por el Architect, y deja artefactos para revisión humana.

Toma cada `<seed_id>.world.json` de un directorio de Architect
(default: el más reciente) y, por cada `IntendedPhenomenon` del
mundo, llama al `ValidatorAgent` con LLM real. Persiste:

- `<seed_id>/<phenomenon_id>.vote.json` — `ValidatorVote` completo.
- `<seed_id>/<phenomenon_id>.summary.txt` — vista resumida (vote,
  margin, fragility, fallar reason, evidence scripts).
- `<seed_id>/<phenomenon_id>.error.txt` — si el agent falla tras retry.

Uso::

    # Default: usa el último directorio de architect
    python scripts/run_validator.py

    # Specific architect run
    python scripts/run_validator.py --architect-dir experiments/architect/20260506_102825

    # Subset de seeds
    python scripts/run_validator.py --seeds smoking_birthweight

    # Override del modelo (default: AZURE_SOLVER_MODEL del .env)
    python scripts/run_validator.py --model gpt-5.4
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
import traceback
from datetime import datetime
from pathlib import Path

from sreg.inference.openai_client import OpenAIClient
from sreg.v1_5.agents import ValidatorAgent
from sreg.v1_5.contracts import IntendedPhenomenon, ValidatorVote, WorldSpec
from sreg.v1_5.environment import SCMEnvironmentAdapter
from sreg.v1_5.world import compile_scm

ROOT = Path(__file__).resolve().parent.parent
ARCHITECT_BASE = ROOT / "experiments" / "architect"
OUT_BASE = ROOT / "experiments" / "validator"


def _resolve_architect_dir(arg: str | None) -> Path:
    if arg:
        d = Path(arg)
        if not d.is_absolute():
            d = ROOT / d
        return d
    candidates = sorted(ARCHITECT_BASE.glob("*"))
    if not candidates:
        raise FileNotFoundError(
            f"No hay directorios en {ARCHITECT_BASE}. Corré primero "
            f"`scripts/run_architect.py`."
        )
    return candidates[-1]


def _list_seeds(arch_dir: Path, requested: list[str] | None) -> list[Path]:
    available = sorted(arch_dir.glob("*.world.json"))
    if requested:
        wanted = set(requested)
        return [p for p in available if p.stem.replace(".world", "") in wanted]
    return available


def _summarize_vote(
    vote: ValidatorVote, phenomenon: IntendedPhenomenon
) -> str:
    lines: list[str] = []
    lines.append(f"Phenomenon: {phenomenon.id} ({phenomenon.kind})")
    lines.append(
        f"Description: {textwrap.shorten(phenomenon.description, width=100)}"
    )
    lines.append(f"Relevant variables: {phenomenon.relevant_variables}")
    lines.append("")
    lines.append(f"vote      : {vote.vote}")
    lines.append(f"margin    : {vote.margin:.3f}")
    lines.append(f"fragility : {vote.fragility:.3f}")
    lines.append(f"iteration : {vote.iteration}")
    lines.append(f"validator : {vote.validator_id}")
    if vote.failure_reason:
        lines.append(f"failure_reason: {vote.failure_reason}")
    if vote.delta_from_previous:
        lines.append(f"delta_from_previous: {vote.delta_from_previous}")
    lines.append("")
    lines.append(f"Evidence ({len(vote.evidence)} artifact(s)):")
    for i, ev in enumerate(vote.evidence, start=1):
        tag = f" [tag={ev.tag}]" if ev.tag else ""
        lines.append(f"  ({i}){tag}")
        if ev.notes:
            lines.append(f"      notes: {textwrap.shorten(ev.notes, width=100)}")
        lines.append(f"      numerical_result: {ev.numerical_result}")
        lines.append("      script:")
        script_lines = ev.script.splitlines() or [""]
        for sl in script_lines[:40]:
            lines.append(f"        {sl}")
        if len(script_lines) > 40:
            lines.append(f"        ... ({len(script_lines) - 40} more lines)")
        lines.append("")
    if vote.diagnostics:
        lines.append(f"Diagnostics: {vote.diagnostics}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--architect-dir",
        default=None,
        help="Directorio con *.world.json (default: último de architect)",
    )
    parser.add_argument(
        "--seeds",
        nargs="+",
        default=None,
        help="seed_ids a procesar (default: todos los del dir)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override del modelo (default: AZURE_SOLVER_MODEL del .env)",
    )
    args = parser.parse_args()

    architect_dir = _resolve_architect_dir(args.architect_dir)
    seed_paths = _list_seeds(architect_dir, args.seeds)
    if not seed_paths:
        print(f"No hay seeds para procesar en {architect_dir}.", file=sys.stderr)
        return 1

    # Modelo: default AZURE_SOLVER_MODEL (codex-optimizado), override con --model.
    model = args.model or os.environ.get("AZURE_SOLVER_MODEL")
    if model is None:
        print(
            "WARNING: AZURE_SOLVER_MODEL no está seteado en .env. Usando "
            "AZURE_MODEL como fallback.",
            file=sys.stderr,
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT_BASE / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    client = OpenAIClient(model=model)
    agent = ValidatorAgent(client, model=model)

    print(f"Modelo: {client.default_model}")
    print(f"Architect dir: {architect_dir.relative_to(ROOT)}")
    print(f"Output dir: {out_dir.relative_to(ROOT)}")
    print(f"Seeds: {[p.stem.replace('.world', '') for p in seed_paths]}\n")

    total_phenomena = 0
    total_passes = 0
    total_weak = 0
    total_fails = 0
    total_errors = 0

    for seed_path in seed_paths:
        seed_id = seed_path.stem.replace(".world", "")
        try:
            world = WorldSpec.model_validate_json(
                seed_path.read_text(encoding="utf-8")
            )
        except Exception as exc:
            print(f"-> {seed_id}: BAD WORLD JSON: {exc}", file=sys.stderr)
            continue

        try:
            scm = compile_scm(world)
            env = SCMEnvironmentAdapter(scm)
        except Exception as exc:
            print(f"-> {seed_id}: COMPILE FAIL: {exc}", file=sys.stderr)
            continue

        seed_out = out_dir / seed_id
        seed_out.mkdir(exist_ok=True)

        if not world.intended_phenomena:
            print(f"-> {seed_id}: no intended_phenomena, skip")
            continue

        for phenomenon in world.intended_phenomena:
            total_phenomena += 1
            print(
                f"-> {seed_id} / {phenomenon.id} ({phenomenon.kind}) ...",
                end=" ",
                flush=True,
            )

            try:
                vote = agent.validate(
                    world=world,
                    env=env,
                    phenomenon=phenomenon,
                )
            except Exception as exc:
                print(f"FAIL: {type(exc).__name__}")
                (seed_out / f"{phenomenon.id}.error.txt").write_text(
                    f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}",
                    encoding="utf-8",
                )
                total_errors += 1
                continue

            (seed_out / f"{phenomenon.id}.vote.json").write_text(
                vote.model_dump_json(indent=2),
                encoding="utf-8",
            )
            (seed_out / f"{phenomenon.id}.summary.txt").write_text(
                _summarize_vote(vote, phenomenon),
                encoding="utf-8",
            )

            print(f"{vote.vote} (margin={vote.margin:.2f})")
            if vote.vote == "passes":
                total_passes += 1
            elif vote.vote == "weak_pass":
                total_weak += 1
            else:
                total_fails += 1

    print(f"\n{'=' * 70}")
    print(f"Resumen: {total_phenomena} fenómenos procesados")
    print(f"  passes    : {total_passes}")
    print(f"  weak_pass : {total_weak}")
    print(f"  fails     : {total_fails}")
    print(f"  errors    : {total_errors}")
    print(f"Artefactos en: {out_dir.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
