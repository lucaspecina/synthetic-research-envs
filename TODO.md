# SREG — TODO

> Board operativo. Detalle de cada item en `issues/I-NNN-slug.md`.
> Lanes: scoring | eval | training | research | hygiene
> SREG v1 cerrado (tag `sreg-v1`). Trabajo actual es post-v1.
> Historico completo en `docs/archive/todo_v1_history.md`.

## NOW

- [ ] I-020: Skills stale update — fix BN/legacy refs (hygiene)

## NEXT

**Scoring**
- [ ] I-001: Verifier robustness — P1.5 deuda tecnica
- [ ] I-002: Credit-assignment unit-level truth (P2)
- [ ] I-003: Claim compiler grammar-direct (A23)
- [ ] I-026: Claim compiler recipe exemplars (Suite 2 baseline, recipe gap)

**Eval**
- [x] I-006: Eval suite — core correctness (2026-04-12, 52 tests)
- [ ] I-007: Eval suite — translation / compilation
- [ ] I-008: Eval suite — science coverage
- [x] I-009: Eval suite — E2E reward alignment blocks A+B (2026-04-12, 25 tests)
- [ ] I-009c: Eval suite — E2E reward alignment block C (gated on P2)

**Training**
- [ ] I-010: Qwen3-8B BEFORE benchmarks

**Hygiene**
- [ ] I-021: Docs consolidation post-v1

## LATER

**Scoring**
- [ ] I-004: Custom metrics prediccion/optimizacion (A25)
- [ ] I-005: Investigation gap gate (A20)

**Eval**
- [ ] I-023: Compiler benchmark offline (200+ claims)
- [ ] I-027: Suite 2 baseline — artifact inconsistencies + repro gap (items 1-6 done, item 7 open)
- [ ] I-028: Compiler emits sweep_values as list inside arm.values (schema violation)
- [ ] I-029: Compiler never abstains (0/4 abstain decisions) — Suite 2 diagnostics hint #1
- [ ] I-030: Compiler taxonomy spec alignment — baseline/observe aliased, condition.values ignored (prereq de I-026 Rama C)

**Training**
- [ ] I-011: CausalReasoningBenchmark integration (T2)
- [ ] I-012: SciGym integration (T3)
- [ ] I-013: QRData + DiscoveryBench harness decisions (T4/T5)
- [ ] I-014: Held-out SREG split (T6)
- [ ] I-015: SFT+RL vs RL-from-base decision (T7)

**Research**
- [ ] I-016: Sequential investigation / Sherlock (A3b)
- [ ] I-018: Semantic modes fictional/abstract (I2)
- [ ] I-019: Forcing real research / data-indexed (A1)
- [ ] I-024: SQ↔DAG coherence audit (D1-D3, Suite 2 baseline)
- [ ] I-025: Flow B LLM prompt — ¿DAG? (D4-D5, Suite 2 baseline)

## PARKED

- [ ] I-017: Invented theory / synthetic literature (A4/I7)
- [ ] I-022: World fingerprint instability (P06 debt)

## RECENTLY CLOSED

- [x] I-009 A+B: Eval suite — reward alignment blocks A+B (2026-04-12, 25/25 pass)
- [x] SREG v1 — 6 criterios de cierre (2026-04-09, tag `sreg-v1`)
- [x] Merge v1 a main + tags sreg-v0/sreg-v1 (2026-04-10)
- [x] Migracion a issue tracking local (2026-04-10)
- [x] I-006: Eval suite — core correctness (2026-04-12, 52/52 pass)

## Referencia rapida

- Config v1 congelada: `CURRENT_STATE.md` seccion "Config v1 congelada"
- Baseline canonico: `results/v1_canonical_batch/MANIFEST.md` (12 casos, avg 0.509)
- Escenarios de validacion: `research/synthesis/investigation_scenarios_rubric.md`
- Eval suites design: `research/synthesis/eval_suite_framework.md`
- TODO v1 historico: `docs/archive/todo_v1_history.md`
