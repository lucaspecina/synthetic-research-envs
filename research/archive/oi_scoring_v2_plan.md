# OI Scoring v2 — Plan de implementacion

> **Status:** Plan aprobado, pre-implementacion
> **Fecha:** 2026-03-27
> **Branch:** autoresearch-open-investigation
> **Motivado por:** 6 pilotos reales (batch1), Codex review, scoring_fundamentals.md

## El problema

El solver investiga de verdad (confounding, mediacion, null findings, estratificacion)
pero el scoring no captura lo que descubre. Cita de Codex: *"The solver is better than
the scorer. Family match gates correctness."*

**Datos concretos (6 pilotos, 3 mundos):**
- avg correctness=0.772, avg coverage=0.197, avg total=0.622
- Confounding descubierto en 4/6 runs → score 0 (no existe como patron)
- Null findings correctos → score 0 (NEAR_ZERO no se compila en practica)
- Claims verdaderos fuera del salience map → score 0 (contradice principio documentado)

## Principio rector

De `research/synthesis/oi_scoring_fundamentals.md`:

> **Correctness = verificacion directa contra el SCM. No depende del salience map.**
> **Salience map = piso de cobertura, no techo del score.**

Hoy el codigo viola este principio: claims que no matchean una familia reciben
`("__unmatched__", 0.0)` en `score_compiled_episode()`.

## Plan en 3 fases

### Fase 1: Desacoplar correctness de family match

**El cambio mas importante.** Un claim verdadero verificado contra el SCM debe recibir
credito de correctness SIEMPRE, este o no en el salience map.

**Diseño propuesto:**

```
ANTES (score_compiled_episode):
  claim → compile → specs → verify each → match to family → score
  Si no matchea familia: score = 0 (incluso si verificacion = verdadero)

DESPUES:
  claim → compile → specs → verify each → truth_score (del SCM, independiente)
  ADEMAS: match to family → coverage_hit (separado)

  correctness = mean(truth_scores)           # solo depende del SCM
  coverage = families_hit / total_families   # solo depende del salience map
```

**Cambios concretos en codigo:**

1. `score_compiled_episode()` en `oi_compiler.py`:
   - Separar verificacion (truth) de matching (coverage)
   - `claim_matches` pasa a tener dos campos: `truth_score` (del verify_atom) y
     `family_id` (del matching, puede ser None)
   - Correctness usa solo `truth_score`
   - Coverage usa solo `family_id`

2. `score_episode()` en `oi_verifier.py`:
   - Recibir `truth_scores` y `family_hits` por separado
   - Correctness = mean(truth_scores) sin filtrar por family
   - Coverage = count(family_hits where score >= threshold) / total_families

3. `ClaimVerdict` en `open_investigation.py`:
   - Agregar campo `truth_score: float` (verificacion pura contra SCM)
   - `matched_family_id` puede ser None (claim novel)
   - `score` = truth_score (antes dependia de family match)

**Implicaciones:**
- Claims verdaderos fuera del salience map reciben credito real
- El salience map solo afecta coverage (15-30% del score total)
- Anti-shotgun sigue funcionando: claims FALSOS = truth_score 0, precision gate

**Riesgos:**
- Sin family match como filtro, claims triviales pero verdaderos ("X tiene media 5.2")
  reciben credito. Mitigacion: relevancia estructural (Fase futura) o marginal gain.
- Para Alpha: aceptable. El solver no hace shotgun de claims triviales.

### Fase 2: Confounding como patron compilable

**Motivado por P1:** confounding descubierto en 4/6 runs, score 0.

**Diseño propuesto:**

```python
class PatternClass(StrEnum):
    ...
    CONFOUNDING = "confounding"  # NUEVO
```

**Semantica:** "X confunde la relacion Y→Z" significa:
1. X esta asociado con Y (observacional)
2. X esta asociado con Z (observacional)
3. La relacion Y→Z CAMBIA al controlar por X

**Lowering a AtomicSpecs:**
```
_lower_confounding(intent) → 2 specs:
  Spec 1: ATE(Y→Z) sin controlar = valor crudo
  Spec 2: ATE(Y→Z) controlando X = valor ajustado
  Assertion: DIFFERENCE entre spec1 y spec2 es POSITIVE o NEGATIVE
  (el efecto cambia al ajustar)
```

Alternativa mas simple: verificar que X es un confounder real en el DAG
(X es ancestor de Y AND ancestor de Z, o X tiene backdoor path).
Esto es computable sin Monte Carlo.

**Cambios en salience map:**
- Agregar generacion de familias de confounding en `oi_salience.py`
- Para cada par (cause, target): buscar confounders en el DAG
- Solo incluir confounders con efecto material (cambio > threshold)

**Riesgos:**
- Confounding es un concepto de grafo, no solo estadistico. El solver puede
  decir "X confunde Y→Z" cuando X es mediador, no confounder. Mitigacion:
  verificar contra el DAG real.

### Fase 3: Null findings + prompt improvements

**P2: Null findings (NEAR_ZERO)**

El DSL ya soporta `NEAR_ZERO` assertions. El compiler (`lower_intent`) ya lo
mapea correctamente. El problema es que el LLM compiler no produce
`direction: "near_zero"` cuando el solver dice "no hay efecto significativo".

**Fix:**
- Agregar ejemplares de NEAR_ZERO al exemplar bank (`oi_exemplars.py`)
- Agregar instruccion explicita en el extraction prompt: "If the solver
  concludes there is NO significant effect, set direction to near_zero"
- Test: compilar "Depth x Algae interaction is weak/absent" → NEAR_ZERO

**P6: Import errors**

El solver pierde 1-2 steps por run intentando imports invalidos.

**Fix:**
- En `oi_prompts.py`, agregar seccion explicita: "Available in your namespace:
  load_artifact, oi (with .corr, .regress, .stratify, .test_independence,
  .groupby_mean), pd, np. Do NOT import statsmodels, scipy, or other packages."

## Orden de ejecucion

```
1. [x] Investigar + debatir scoring v2 con Codex (thread 019d31e7)
2. [x] Implementar Fase 1 (scoring v2) + tests (15 tests, 130 existing pass)
3. [x] Debatir confounding pattern con Codex
4. [x] Implementar Fase 2 (confounding) + tests (3 E2E tests)
5. [x] Implementar Fase 3 (null findings + prompt)
6. [ ] Re-pilotar 3 mundos con scoring v2    ← NEXT
7. [ ] Comparar antes/despues, documentar
```

## Codex review findings (thread 019d31e7)

### Scoring v2 review
- CRITICO: reward hacking con verdades irrelevantes → added structural relevance
- ALTO: precision gate bypassable → preserved via relevance weighting
- ALTO: multi-spec bias → changed to per-claim scoring with min()
- MEDIA: coverage depends on effective (not truth) → FIXED: uses truth_score
- BAJA: verdict description inconsistente → FIXED

### Confounding review
- ALTA: verificacion no prueba gap raw-partial → KNOWN ISSUE, aceptable para Alpha
- ALTA: falta validacion confounder → FIXED
- MEDIA: sign flips ignorados → FIXED (signed gap)
- MEDIA: direction ambigua → KNOWN, acceptable for Alpha

## Que NO hacemos (y por que)

- **Sub-preguntas pesadas**: scoring_fundamentals dice "no disenar scoring sin
  datos de pilotos reales". Necesitamos mas evidencia primero.
- **Conectar OI al orchestrator**: cambio grande, ortogonal. Los fixes de scoring
  tienen mas impacto inmediato.
- **Compiler benchmark (200+ claims)**: trabajo de data, no de diseño.
- **Relevancia computada (grafo + brief)**: es la iteracion SIGUIENTE despues
  de tener scoring v2 funcionando y validado con pilotos.

## Metricas de exito

Despues de implementar las 3 fases y re-pilotar:
1. Claims de confounding (hoy 0) deben recibir credito > 0.5
2. Claims verdaderos fuera del map (hoy 0) deben recibir credito > 0
3. Null findings correctos deben recibir credito > 0
4. Correctness promedio debe subir (de 0.772 a ~0.85+)
5. El ranking relativo entre mundos debe mantenerse (treatment > ecosystem > education)
