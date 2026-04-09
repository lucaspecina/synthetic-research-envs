# P06 Cap Decision: Resultado (2026-04-09)

## Pregunta

> Bajo el prompt atomico actual y el codigo post-fixes (2026-04-09),
> conviene cap=5 o cap=15 para SREG v1?

## Decision

**Congelar cap=15 para SREG v1.**

Cap=15 como techo alto para evitar artifacts de bundling bajo la
semantica actual de claim-truth. No demostrado como "optimo" ni
"uniformemente superior" — demostrado como mejor instrumento de medicion
que cap=5.

## Resultados crudos (24 runs, 0 errores)

| Caso | corr_5 | corr_15 | delta_corr | total_5 | total_15 | delta_total | n_5 | n_15 |
|------|--------|---------|------------|---------|----------|-------------|-----|------|
| chemical | 0.636 | 0.621 | -0.015 | 0.454 | 0.446 | -0.008 | 5 | 7 |
| competing_mech | 0.792 | 0.783 | -0.009 | 0.682 | 0.580 | -0.102 | 4 | 5 |
| confounding | 0.850 | 0.653 | -0.197 | 0.524 | 0.408 | -0.116 | 5 | 6 |
| coral_bleach | 0.667 | 0.625 | -0.042 | 0.423 | 0.393 | -0.030 | 5 | 8 |
| heterogeneity | 0.725 | 0.812 | +0.087 | 0.356 | 0.417 | +0.061 | 5 | 8 |
| identifiability | 0.500 | 0.400 | -0.100 | 0.287 | 0.218 | -0.069 | 4 | 5 |
| immunotherapy | 0.700 | 0.571 | -0.129 | 0.577 | 0.500 | -0.077 | 5 | 7 |
| microbiome | 0.667 | 0.750 | +0.083 | 0.377 | 0.462 | +0.085 | 5 | 9 |
| missing_data | 0.500 | 0.861 | +0.361 | 0.402 | 0.736 | +0.334 | 4 | 6 |
| policy_equity | 0.550 | 0.944 | +0.394 | 0.245 | 0.645 | +0.400 | 4 | 6 |
| poverty | 0.500 | 0.694 | +0.194 | 0.297 | 0.542 | +0.245 | 4 | 6 |
| selection_bias | 0.817 | 0.857 | +0.040 | 0.639 | 0.762 | +0.123 | 5 | 7 |

Medias: corr_5=0.659, corr_15=0.714 (delta +0.056). total_5=0.439,
total_15=0.509 (delta +0.071). n_claims_5=4.58, n_claims_15=6.75.

## Criterios pre-registrados

| Criterio | Umbral | Resultado | Veredicto |
|----------|--------|-----------|-----------|
| P1a: delta mean(corr) | >= +0.03 | +0.056 | PASS |
| P1b: >= 8/12 casos positivos | >= 8/12 | 6/12 | FAIL |
| C1: solver usa espacio extra | delta n_claims > 1.0 | +2.17 | PASS |
| C2: delta mean(wcov) | >= +0.02 | +0.047 | PASS |
| C3: delta mean(total) | >= +0.02 | +0.071 | PASS |

**P1 es mixto.** El delta de medias pasa pero la condicion de amplitud
no. La distribucion esta polarizada: 6 casos mejoran mucho, 6 empeoran
poco.

## Monitoreo

- **M1 Force-submit:** 0 en ambas condiciones. 24/24 submitted.
- **M2 Evidence rejection:** 0 eventos de rechazo en 24 runs.
- **M3 Abstention rate:** similar entre condiciones (1-2 abstentions
  por caso max).
- **M4 Cap saturation:** cap=5: 8/12 saturan. Cap=15: 0/12 saturan
  (max observado: 9 claims).

## Analisis cualitativo

### Mecanismo de ganancia (6 casos cap15 mejor)

Cap=5 fuerza **bundling**: claims con 6-10 specs que mezclan multiples
hallazgos. Esto tiene dos consecuencias:
1. El scoring pierde granularidad (no puede distinguir "acerto A pero
   erro B" dentro de la misma claim).
2. El solver comprime argumentos complejos en una claim y pierde
   precision (ej: policy_equity afirmo "substitution does NOT occur"
   con truth=0.2; con cap=15 descompuso en "substitution exists" +
   "doesn't nullify effect" con truth=1.0 cada una).

Casos emblematicos: missing_data (+0.334), policy_equity (+0.400),
poverty (+0.245).

### Mecanismo de perdida (6 casos cap15 peor)

El solver **rellena slots** con claims especulativas no verificadas.
Ejemplos:
- immunotherapy C6: truth=0.0, relevancia=0.98 — falsa y devastadora
- confounding c5/c6: truth=0.25 y 0.0 — especulacion sin respaldo
- competing_mech C3: truth=0.25 — correlacion inventada

Esto es informativo, no problematico: un agente con buen juicio
cientifico no rellena slots vacios con claims no verificadas. Cap=15
amplifica la senal de calidad de juicio en ambas direcciones.

### Patrones transversales

1. **Coverage binaria siempre 1.0** en los 24 runs. El cuello de
   botella es correctness y weighted_coverage, nunca raw coverage.
2. **"Adjusted effect" claims** consistentemente reciben truth parcial
   (0.33-0.50). Es feature de la semantica atomica: el compiler
   descompone en multiple specs (crude sign, adjusted sign, null test)
   y solo algunos pasan.
3. **Compiler funciona bien:** grammar_direct ~85%, v1_fallback
   esporadico, abstentions apropiadas.
4. **Cero evidence rejections** (#25 no se disparo en ningun caso).

## Argumento de instrumento (por que cap=15)

La decision no es "cual cap hace al solver sacar mejor nota" sino
"cual cap hace a SREG un mejor instrumento de medicion":

1. **Mayor resolucion:** cap=5 fuerza bundling que colapsa multiples
   hallazgos en un veredicto. El scoring pierde granularidad.
2. **Mejor presion evolutiva:** cap=15 penaliza especulacion (los
   losers pierden por rellenar con claims falsas) y premia decomposicion
   atomica (los winners ganan por separar argumentos complejos).
3. **Sin saturacion:** 8/12 casos saturan cap=5. El instrumento no
   puede distinguir entre solvers que harian 5, 8, o 12 claims.

## Calificaciones (Codex review)

- El experimento demuestra "not 5" mas que "15 es optimo". El solver
  nunca uso mas de 9 claims.
- Los losers argumentan a favor de cap=15 *si* se acepta que premiar
  contencion bajo slack es deseable. Es decision de diseno, no free win.
- Coverage binaria es no-informativa (siempre 1.0). Solo
  weighted_coverage discrimina. Esto es deuda conocida, no bloqueante.
- Relevancia es permisiva: claims falsas pueden tener relevancia alta.
  Es consecuencia de truth x relevance design, no un bug.

## Fuera de inferencia

- Calidad del prompt atomico (identica en ambas condiciones)
- Efecto de bugfixes #10, #24, #25 (identicos en ambas condiciones)
- Si cap=10 seria mejor que cap=15 (no testeado)
- Discriminacion entre solvers distintos (solo se testo un solver)
- Comparacion con resultados historicos de P06 original

## Archivos

- Protocolo: `research/notes/p06_addendum_cap_decision.md`
- Harness: `scripts/p06_cap_decision.py`
- Resultados: `results/p06_cap_decision/`
- Summary: `results/p06_cap_decision/_summary.json`
