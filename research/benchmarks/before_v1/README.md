# BEFORE v1 — Official Benchmark Summaries

Benchmark summaries (`benchmark.json`) for the BEFORE condition of the thesis.
These are committed for reproducibility. Raw results (`.jsonl`) live in
`experiments/benchmarks/before_v1/` (gitignored).

## Harness

All runs use identical harness parameters (see `research/synthesis/harness_decisions_v1.md`):
- `--with-tools` (python_exec + think, max_iterations=20)
- `temperature=0.0`
- `seed=42`

## Models

- **Reference:** gpt-5.4 (Azure AI Foundry)
- **Target:** Qwen3-8B (vLLM on H100 Azure ML) — pending

## Benchmarks

| Benchmark | Subset | N | Scoring |
|---|---|---|---|
| CLadder | dev | 100 | Exact match (yes/no) |
| QRData | dev | 50 | Numeric tolerance 3% |
| DiscoveryBench | all | 25 | HMS (3 judge seeds, median) |
| CRB | all | 173 | Deterministic (identification + estimation) |
| SciGym | TBD | TBD | Deterministic (NTS, RMS, STE) — requires H100 |

## Results — gpt-5.4 (reference model)

Run date: 2026-04-12. Code version: `2ad7013`.

| Benchmark | Score | Metric | N | Errors | File |
|---|---|---|---|---|---|
| CLadder | **65.0%** | accuracy | 100 | 8 | `cladder_gpt-5.4.json` |
| QRData | **52.0%** | accuracy | 50 | 2 | `qrdata_gpt-5.4.json` |
| DiscoveryBench | **0.360** | HMS median | 25 | 0 | `discoverybench_gpt-5.4.json` |
| CRB | **43.5%** | full_id_acc | 173 | 19 | `crb_gpt-5.4.json` |

### Sanity check vs published baselines

| Benchmark | Published baseline | Our gpt-5.4 | Notes |
|---|---|---|---|
| CLadder | GPT-4 zero-shot: 62%, +CoT: 70.4% | 65.0% | In range. Rung pattern (1>2>3) matches literature. |
| QRData | GPT-4 + Code Interpreter: 57.9% | 52.0% | Slightly below. Our python_exec lacks file access (data truncated in prompt). |
| DiscoveryBench | GPT-4o Reflexion+Oracle: 24.5% | 36.0% | Higher — expected from generational model improvement. |
| CRB | SOTA full_id: 30.1% | 43.5% | +13pp. Consistent with gpt-5.4 being stronger at identification. |

### Notes

- Errors are Azure content-policy false positives (sensitive topics in CRB papers, some CLadder scenarios).
  Counted as incorrect, not retried — consistent across all models.
- Tools (python_exec) are offered but adapters don't inject file paths into the namespace.
  The model sees truncated data previews only. This is by design for BEFORE — harness is identical across conditions.
