---
id: 27
title: Suite 2 baseline — artifact inconsistencies + reproducibility gap
status: partial
type: bug
lane: eval
priority: later
created: 2026-04-15
updated: 2026-04-15
related: [I-007, I-026, I-028]
origin: suite2_compiler_baseline.md close-out review (Codex)
---

# I-027: Suite 2 baseline — artifact inconsistencies + reproducibility gap

## Status
- **Estado (2026-04-15 update):** items 1-6 **cerrados** por el v2
  re-baseline. Item 7 (nuevo) **abierto** — `stage1_fail` ahora mezcla
  dos modos de falla distintos y requiere split o anotación.
- **Resultado del trabajo de hoy:**
  - Verifier DIFFERENCE+DISTINGUISHABLE arreglado + 4 unit tests
    (`TestAssertDistinguishable`).
  - Round-trip de `AtomicSpec` garantizado por 6 unit tests
    (`TestAtomicSpecRoundTrip`).
  - Dump expandido a 55 targets con 5 buckets
    (`compiler_baseline_full_dump_v2.json`).
  - Nomenclatura métrica frozen (item 6).
  - `suite2_compiler_baseline.md` §9 documenta el delta v1→v2.
  - `suite2_pattern_breakdown.md` re-escrito con actuals en vez de
    upper-bound.
- **Proximo paso:** decidir si el bucket `stage1_fail` se splittea
  (`stage1_decision_fail` vs `stage1_crash`) o se anota en el dumper.

## Items

### ✅ DONE (items 1-6 resueltos por v2 re-baseline 2026-04-15)

Los items 1-6 están preservados abajo por trazabilidad. Resumen del
estado actual:

| Item | Status | Resuelto por |
|---|---|---|
| 1. `22` vs `21` verdict_wrong | ✅ | Obsoleto — v2 tiene `verdict_wrong=19`, re-conteo limpio contra dump completo. |
| 2. `adjust_swap` semantic drift | ✅ | Nomenclatura frozen (item 6); `effective_pass_rate` y `strict_full_pass_rate` usados en todos los docs. |
| 3. `6 full pass` vs `17/55` headline | ✅ | §9 del baseline doc re-frameó headline. Ahora: strict 13% + effective 31%, sin ambigüedad. |
| 4. Reproducibility gap — artefactos faltantes | ✅ | `compiler_baseline_full_dump_v2.json` cubre los 55 targets con 5 buckets, round-trip-safe. |
| 5. Verifier DIFFERENCE+DISTINGUISHABLE bug | ✅ | Fix aplicado + 4 unit tests; Suite 1 52/52 sin regresión; v2 re-baseline confirmó hipótesis SQ-A1. |
| 6. Nomenclatura métrica | ✅ | `strict_full_pass_rate`, `effective_pass_rate`, `real_error_rate`, `verdict_fail_rate` usados consistentemente. |

### 🟡 OPEN (item 7 — nuevo, detectado por v2)

### 7. `stage1_fail` bucket mezcla dos modos de falla distintos

Detectado durante análisis del v2 dump (2026-04-15). Ver
`suite2_compiler_baseline.md` §9.7.

El bucket `stage1_fail` en `compiler_baseline_full_dump_v2.json` (6
entries) ahora conflate:

- **(a) Decision errors** (4 entries): el compiler compiló cuando gold
  dijo abstain. Modo de falla original del bucket.
  - `SQ_F07_s1, W3_F11_s0, W3_F12_s0, W3_F12_s1`
- **(b) Runtime/schema crashes** (2 entries): el compiler no produjo
  specs en un target que debía compilar. Bug, no decisión.
  - `W3_F03_s0, W3_F03_s2` — ver I-028 (sweep_values como lista
    inside `arm.values`).

**Impacto:** downstream analyses (audit #11b, ablation, reporte final)
necesitan distinguir "el compiler decidió mal" de "el compiler se
rompió". Actualmente se cuentan juntos.

**Propuesta de fix:**
- **Opción A:** splittear en dos buckets en `scripts/suite2_full_dump_v2.py`:
  `stage1_decision_fail` + `stage1_crash`.
- **Opción B:** mantener `stage1_fail` como super-bucket pero anotar
  cada entry con un sub-campo `stage1_fail_mode: "decision" | "crash"`.

**Preferencia tentativa:** A — los buckets ya son la unidad de análisis,
introducir un sub-campo complica los downstream scripts.

**Scope:** re-bucketizar offline sobre el dump v2 (zero LLM calls) +
actualizar `suite2_compiler_baseline.md` §9 con el split + actualizar
`suite2_pattern_breakdown.md`. No requiere nueva corrida LLM.

### 📎 Preservado por trazabilidad (redacción original 2026-04-15 AM)

### 1. `22` verdict wrong en doc vs `21` entries en JSON
- `research/synthesis/suite2_compiler_baseline.md` §2 tabla reporta
  **22 "Verdict wrong"**.
- `research/synthesis/compiler_baseline_failures.json` tiene **21
  entries**.
- Una fila está perdida entre la categorización y la persistencia.
- **Investigar:** ¿fue skip silencioso en `scripts/dump_compiler_output.py`
  (e.g. target con `status=abstain` tratado como fail sin ser dumpeado)?
  ¿Error de conteo al escribir el doc? ¿Timeout / error no guardado?

### 2. `adjust_swap` tratado como dos cosas distintas
- `suite2_compiler_baseline.md` reporta **effective pass = 17/55 (31%)**
  con la aritmética `full_pass (6) + adjust_swap (11) = 17`. Adjust-swap
  cuenta como benign pass.
- `scripts/suite2_pattern_breakdown.py` cuenta SOLO `full_pass` como
  pass (adjust_swap explícitamente tratado como fail).
- Son dos métricas distintas circulando sin nombres explícitos.
- **Fix:** fijar nombres métricos de una vez, nunca más "pass rate"
  sin prefijo (ver item 4).

### 3. `6 full pass (11%)` vs `17/55 effective pass (31%)` headline
- El doc es claro si lo leés entero, pero la primera línea del §1
  ("the LLM correctly compiles 31% of them (17/55)") se puede leer
  como "31% full pass". Alguien que solo lea el headline va a
  sobre-estimar calidad real.
- **Fix:** re-framear el headline para dejar explícito que 31% es
  la métrica permisiva (effective) y 11% la estricta (strict full pass).

### 4. Reproducibility gap — artefactos que faltan
- Dump persistido = `compiler_baseline_failures.json` (solo
  verdict-fails, 21 entries).
- **Faltan artefactos para:**
  - `full_pass` (6 entries) — bloquea Task #11 "audit manual de los
    6 full passes".
  - `real_struct_err` (11 entries) — bloquea el audit de "verdict
    correcto por accidente" (pass-by-accident pathology).
  - `stage1_fail` (5 entries) — bloquea auditar qué claims
    abstienen mal.
  - `adjust_swap` (11 entries) — bloquea verificar empíricamente
    que efectivamente son benignos.
- **Fix:** expandir el dumper a dump TODO (no solo fails). Mismo
  formato, cada target con su `category`. Eso habilita Task #11b
  (audit pass-by-accident) y reproducibilidad de los headlines.
- **Impacto:** 55 LLM calls adicionales. Bajo costo, alto valor.

### 5. Verifier contract mismatch — `difference` + `distinguishable`
- Detectado por Codex durante review del audit #11a (2026-04-15).
- `src/sreg/tools/oi_verifier.py:622` — la rama `comparison=difference`
  produce un dict con keys `{difference, ref, other}`.
- `src/sreg/tools/oi_verifier.py:800` — la aserción `DISTINGUISHABLE`
  lee `comparison_result["value"]`, que NO existe en el dict de
  `difference`.
- **Efecto:** `distinguishable` retorna `holds=false` incluso cuando
  la diferencia es claramente no-cero. Esto infla artificialmente el
  bucket `verdict_fail`.
- **Impacto observado:** las 3 entries de SQ-A1 en
  `compiler_baseline_failures.json` (ATE positivo de 0.68) están
  marcadas como verdict-fail cuando el compiler emitió
  `difference + distinguishable` — la aserción debería retornar
  `holds=true` pero retorna `holds=false` por el key ausente.
- **Scope del fix:** (a) verificador lee la key correcta de un dict
  de `difference`, (b) test unitario que construye el dict de
  difference y asegura que todas las assertions genéricas lo consumen
  correctamente, (c) re-correr el baseline con el verificador
  arreglado y comparar headlines.
- **Relación con Suite 2:** este bug afecta el conteo de
  `verdict_fail` vs `full_pass` de la baseline. Puede haber targets
  que hoy figuran como verdict-fail que en realidad son
  adjust-swap-benign cuando el verifier funciona bien. El re-run es
  la forma limpia de separar artefacto de recipe gap real.
- **Prioridad:** alta. Este bug es a nivel del verificador (ground
  truth), no del compiler. Puede estar también afectando suites
  futuras y entrenamientos.

### 6. Nomenclatura métrica fija

Proponemos los siguientes nombres, usados en TODO doc/script/issue a
partir de acá:

| Nombre | Fórmula | Semántica |
|---|---|---|
| `strict_full_pass_rate` | `full_pass / N` | Métrica estricta. Todas las stages (compile decision, structure, verdict) aciertan. |
| `effective_pass_rate` | `(full_pass + adjust_swap) / N` | Métrica operativa. El compiler no corrompe el score aunque use `adjust` por `intervene`. |
| `verdict_fail_rate` | `verdict_wrong / N` | Verdict discrepancy directa. |
| `real_error_rate` | `1 - effective_pass_rate` | Complemento — errores que sí corromperían scoring real. |

**Regla dura:** **nunca** escribir "pass rate" sin prefijo. Si el
lector tiene que inferir cuál es, la métrica está mal reportada.

## Alcance

- **Fuera de scope ahora:** re-correr el baseline entero. No vamos a
  cambiar los números, solo a etiquetarlos bien y a cerrar el gap de
  artefactos.
- **In-scope:**
  - Ajustar los 3 puntos de redacción del baseline doc.
  - Re-ejecutar el dumper expandido para persistir los 5 buckets.
  - Adoptar la nomenclatura métrica fija en todos los docs/scripts.

## Links
- `research/synthesis/suite2_compiler_baseline.md`
- `research/synthesis/suite2_pattern_breakdown.md`
- `scripts/dump_compiler_output.py`
- `scripts/suite2_pattern_breakdown.py`
- Detectado durante review con Codex — thread
  `019d8d5e-6d29-77c1-94a0-63604f4df009`.
