"""Harness manual: corre Architect sobre PaperInsights existentes y deja
artefactos para revisión humana.

Toma cada `*.json` de un directorio de Paper Digestion (default: el más
reciente) y produce, por cada uno:

- `<seed_id>.world.json` — `WorldSpec` completo.
- `<seed_id>.sample.csv` — DataFrame de `n=1000` filas (incluyendo
  variables latentes para inspección humana, NO lo que vería el
  Investigator).
- `<seed_id>.summary.txt` — describe + topología (variables, edges,
  intended_phenomena) para audit rápido.
- `<seed_id>.error.txt` — si el agent falla incluso tras retry.

Uso::

    # Default: usa el último directorio de paper_digestion + saca identifiability_pollution
    python scripts/run_architect.py

    # Specific input dir
    python scripts/run_architect.py --insights-dir experiments/paper_digestion/20260505_161757

    # Subset de seeds
    python scripts/run_architect.py --seeds selection_bias_police confounding_by_indication
"""

from __future__ import annotations

import argparse
import sys
import textwrap
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd

from sreg.inference.openai_client import OpenAIClient
from sreg.v1_5.agents import ArchitectAgent
from sreg.v1_5.contracts import PaperInsights
from sreg.v1_5.environment import SCMEnvironmentAdapter
from sreg.v1_5.world import compile_scm

ROOT = Path(__file__).resolve().parent.parent
DIGESTION_BASE = ROOT / "experiments" / "paper_digestion"
OUT_BASE = ROOT / "experiments" / "architect"

# Por defecto excluimos identifiability_pollution: Codex (2026-05-05)
# señaló que ese seed mezcla proxy error + agregación ecológica +
# identifiability epistemológica, lo que NO es representable
# fielmente en un SCM iid fila-a-fila. Queda como red-team posterior.
DEFAULT_EXCLUDED = {"identifiability_pollution"}


def _resolve_insights_dir(arg: str | None) -> Path:
    if arg:
        d = Path(arg)
        if not d.is_absolute():
            d = ROOT / d
        return d
    candidates = sorted(DIGESTION_BASE.glob("*"))
    if not candidates:
        raise FileNotFoundError(
            f"No hay directorios en {DIGESTION_BASE}. Corré primero "
            f"`scripts/run_paper_digestion.py`."
        )
    return candidates[-1]


def _list_seeds(insights_dir: Path, requested: list[str] | None) -> list[Path]:
    available = sorted(insights_dir.glob("*.json"))
    if requested:
        wanted = set(requested)
        return [p for p in available if p.stem in wanted]
    return [p for p in available if p.stem not in DEFAULT_EXCLUDED]


def _summarize(world, df: pd.DataFrame, env, seed_id: str) -> str:
    lines: list[str] = []
    lines.append(f"WorldSpec: formalism={world.formalism}, "
                 f"{len(world.variables)} variables, {len(world.edges)} edges")
    lines.append("")
    lines.append("Variables:")
    for v in world.variables:
        latent = "" if v.is_observable else " [LATENT]"
        eq = textwrap.shorten(v.equation or "", width=80)
        lines.append(f"  - {v.name} ({v.kind}){latent}: {eq}")
    lines.append("")
    lines.append("Edges:")
    for parent, child in world.edges:
        lines.append(f"  - {parent} -> {child}")
    lines.append("")
    lines.append("Intended phenomena:")
    for ip in world.intended_phenomena:
        lines.append(f"  - [{ip.kind}] {ip.id}: "
                     f"{textwrap.shorten(ip.description, width=100)}")
        lines.append(f"    relevant_variables: {ip.relevant_variables}")
    lines.append("")

    # Diagnósticos específicos por seed conocido. Permite verificar que
    # la mecánica del fenómeno realmente se materializa numéricamente
    # (Codex 2026-05-06: describe() solo no alcanza para acceptance).
    diagnostics = _seed_specific_diagnostics(seed_id, env)
    if diagnostics:
        lines.append("Phenomenon diagnostics (seed-specific):")
        lines.extend(diagnostics)
        lines.append("")

    lines.append("Sample summary (n=1000):")
    lines.append(df.describe().to_string())
    return "\n".join(lines)


def _seed_specific_diagnostics(seed_id: str, env) -> list[str]:
    """Diagnósticos numéricos por seed conocido. Los desconocidos
    devuelven [] y solo se muestra el describe() general.

    Cada diagnóstico apunta al fenómeno central declarado por el seed
    para que un humano (o Codex) pueda verificar a ojo si se
    materializa (vs solo "compila").
    """
    if seed_id == "smoking_birthweight":
        return _diag_smoking_birthweight(env)
    if seed_id == "selection_bias_police":
        return _diag_selection_bias_police(env)
    if seed_id == "confounding_by_indication":
        return _diag_confounding_by_indication(env)
    return []


def _diag_smoking_birthweight(env) -> list[str]:
    """Smoking → Mortality paradox: ATE marginal positivo; estratificado
    por LowBW=1, el efecto se atenúa o invierte."""
    out: list[str] = []
    cols = set(env.variables)
    smoke_col = next(
        (c for c in ["Smoking", "smoking", "smoking_intensity"] if c in cols),
        None,
    )
    mort_col = next(
        (c for c in ["Mortality", "mortality", "infant_mortality"] if c in cols),
        None,
    )
    lbw_col = next(
        (c for c in ["LowBW", "low_birth_weight"] if c in cols),
        None,
    )
    if not (smoke_col and mort_col and lbw_col):
        out.append(
            f"  - Could not find required columns "
            f"(smoking={smoke_col}, mortality={mort_col}, lbw={lbw_col})"
        )
        return out

    df = env.observe(n=20000, columns=env.variables, seed=42)
    # ATE marginal observacional (no causal — smoking puede ser distribuido
    # de forma distinta entre subgrupos, pero útil como sanity).
    treated = df[df[smoke_col] >= 1]
    untreated = df[df[smoke_col] == 0]
    if len(treated) < 100 or len(untreated) < 100:
        out.append(
            f"  - Insufficient subgroup sizes "
            f"(treated={len(treated)}, untreated={len(untreated)})"
        )
        return out
    ate_marginal = float(treated[mort_col].mean() - untreated[mort_col].mean())
    out.append(
        f"  - Crude smoking->mortality difference: {ate_marginal:+.4f} "
        f"(expected POSITIVE for harmful effect)"
    )

    # Estratificado por LowBW=1 (el estrato de la paradoja).
    lbw1 = df[df[lbw_col] == 1]
    if len(lbw1) < 50:
        out.append(f"  - LowBW=1 stratum too small ({len(lbw1)}) — paradox not testable")
        return out
    lbw1_t = lbw1[lbw1[smoke_col] >= 1]
    lbw1_u = lbw1[lbw1[smoke_col] == 0]
    if len(lbw1_t) < 20 or len(lbw1_u) < 20:
        out.append(
            f"  - LowBW=1 subgroups too small (treated={len(lbw1_t)}, "
            f"untreated={len(lbw1_u)}) — paradox not testable"
        )
        return out
    diff_lbw1 = float(lbw1_t[mort_col].mean() - lbw1_u[mort_col].mean())
    out.append(
        f"  - Within LowBW=1, smoking->mortality difference: {diff_lbw1:+.4f} "
        f"(expected NEGATIVE or near-zero — paradox)"
    )

    # Estratificado por LowBW=0 (control).
    lbw0 = df[df[lbw_col] == 0]
    diff_lbw0 = float(
        lbw0[lbw0[smoke_col] >= 1][mort_col].mean()
        - lbw0[lbw0[smoke_col] == 0][mort_col].mean()
    )
    out.append(f"  - Within LowBW=0, smoking->mortality difference: {diff_lbw0:+.4f}")
    out.append(
        f"  - Paradox materializes if diff_lbw1 < diff_lbw0: "
        f"{diff_lbw1 < diff_lbw0}"
    )
    return out


def _diag_selection_bias_police(env) -> list[str]:
    """Camera_assigned vs use_of_force: crude vs adjusted by prior_complaints."""
    out: list[str] = []
    cols = set(env.variables)
    cam_col = next(
        (c for c in ["camera_assigned", "Camera", "BWC"] if c in cols), None
    )
    force_col = next(
        (c for c in ["use_of_force_incidents", "UseOfForce", "force"] if c in cols),
        None,
    )
    if not (cam_col and force_col):
        out.append(
            f"  - Could not find required columns "
            f"(camera={cam_col}, force={force_col})"
        )
        return out

    df = env.observe(n=20000, columns=env.variables, seed=42)
    treated = df[df[cam_col] == 1]
    untreated = df[df[cam_col] == 0]
    if len(treated) < 100 or len(untreated) < 100:
        out.append(
            f"  - Subgroup sizes insufficient "
            f"(camera=1: {len(treated)}, camera=0: {len(untreated)})"
        )
        return out
    crude = float(treated[force_col].mean() - untreated[force_col].mean())
    out.append(
        f"  - Crude camera->use_of_force difference: {crude:+.4f} "
        f"(expected POSITIVE due to selection — high-complaint officers "
        f"got cameras first)"
    )
    return out


def _diag_confounding_by_indication(env) -> list[str]:
    """Drug_prescription vs clinical_outcome: crude harmful, adjusted reverses."""
    out: list[str] = []
    cols = set(env.variables)
    rx_col = next(
        (c for c in ["drug_prescription", "treatment", "DrugX"] if c in cols),
        None,
    )
    outcome_col = next(
        (c for c in ["clinical_outcome", "outcome"] if c in cols), None
    )
    if not (rx_col and outcome_col):
        out.append(
            f"  - Could not find required columns (rx={rx_col}, outcome={outcome_col})"
        )
        return out

    df = env.observe(n=20000, columns=env.variables, seed=42)
    treated = df[df[rx_col] == 1]
    untreated = df[df[rx_col] == 0]
    if len(treated) < 100 or len(untreated) < 100:
        out.append(
            f"  - Subgroup sizes insufficient "
            f"(rx=1: {len(treated)}, rx=0: {len(untreated)})"
        )
        return out
    crude = float(treated[outcome_col].mean() - untreated[outcome_col].mean())
    out.append(
        f"  - Crude drug->outcome difference: {crude:+.4f} "
        f"(expected NEGATIVE in this domain since sicker patients "
        f"receive treatment more often, regardless of true effect)"
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--insights-dir",
        default=None,
        help="Directorio con PaperInsights JSON (default: último de paper_digestion)",
    )
    parser.add_argument(
        "--seeds",
        nargs="+",
        default=None,
        help="seed_ids a procesar (default: todos los del dir, menos identifiability_pollution)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override del modelo (default: AZURE_MODEL del .env)",
    )
    args = parser.parse_args()

    insights_dir = _resolve_insights_dir(args.insights_dir)
    seed_paths = _list_seeds(insights_dir, args.seeds)
    if not seed_paths:
        print(f"No hay seeds para procesar en {insights_dir}.", file=sys.stderr)
        return 1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT_BASE / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    client = OpenAIClient(model=args.model)
    agent = ArchitectAgent(client, model=args.model)

    print(f"Modelo: {client.default_model}")
    print(f"Insights dir: {insights_dir.relative_to(ROOT)}")
    print(f"Output dir: {out_dir.relative_to(ROOT)}")
    print(f"Seeds: {[p.stem for p in seed_paths]}\n")

    for seed_path in seed_paths:
        seed_id = seed_path.stem
        print(f"-> Architecting {seed_id} ...", end=" ", flush=True)

        try:
            insights = PaperInsights.model_validate_json(
                seed_path.read_text(encoding="utf-8")
            )
        except Exception as exc:
            print(f"BAD INSIGHTS JSON: {exc}", file=sys.stderr)
            (out_dir / f"{seed_id}.error.txt").write_text(
                f"Failed to load insights: {exc}", encoding="utf-8"
            )
            continue

        try:
            world = agent.design(insights=insights)
        except Exception as exc:
            print(f"FAIL: {type(exc).__name__}", file=sys.stderr)
            (out_dir / f"{seed_id}.error.txt").write_text(
                f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}",
                encoding="utf-8",
            )
            continue

        # Persistir WorldSpec.
        (out_dir / f"{seed_id}.world.json").write_text(
            world.model_dump_json(indent=2),
            encoding="utf-8",
        )

        # Compilar y samplear (sample completo, incluye latentes para inspección).
        try:
            scm = compile_scm(world)
            env = SCMEnvironmentAdapter(scm)
            df_full = env.observe(
                n=1000, columns=env.variables, seed=42
            )
        except Exception as exc:
            print(f"COMPILE/SAMPLE FAIL: {exc}", file=sys.stderr)
            (out_dir / f"{seed_id}.error.txt").write_text(
                f"compile/sample failed: {exc}", encoding="utf-8"
            )
            continue

        df_full.to_csv(out_dir / f"{seed_id}.sample.csv", index=False)
        (out_dir / f"{seed_id}.summary.txt").write_text(
            _summarize(world, df_full, env, seed_id), encoding="utf-8"
        )
        print(f"OK -> {seed_id}.world.json + .sample.csv + .summary.txt")

    print(f"\n{'=' * 70}")
    print(f"Listo. Artefactos en: {out_dir.relative_to(ROOT)}")
    print("Inspeccioná los .summary.txt para revisión humana de cada mundo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
