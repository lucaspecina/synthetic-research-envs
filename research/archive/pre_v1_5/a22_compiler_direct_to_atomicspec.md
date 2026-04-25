# A22 — Compiler: de 8 patterns fijos a compilacion directa a AtomicSpec

**Date:** 2026-03-29
**Type:** Autoresearch — hallazgo de E2E + propuesta arquitectonica
**Branch:** autoresearch-open-investigation
**Status:** PROPUESTA. Pendiente debate con Codex + diseno detallado.
**Prerequisito:** A21 (compatibilidad algebra) resuelto y validado E2E.

> **LA PREGUNTA filter**: El compiler rechaza claims correctos porque no
> entran en 8 patterns fijos. El solver escribe como investigador real
> (cadenas, claims compuestos, residuales) y el sistema no puede evaluarlos.
> Esto significa que RL no entrenaria buen juicio porque no puede dar
> credito a hallazgos legitimos pero complejos.

## Problema descubierto en E2E (2026-03-29)

### Evidencia: Soil case

De 4 claims que el solver submitio, **3 fueron ABSTENTION**:

| Claim | Que dijo el solver | Compiler | Por que fallo |
|-------|-------------------|----------|---------------|
| C1 | mining → metals → stress → vigor (cadena) | ABSTENTION | "multiple associations without single treatment-outcome" |
| C2 | stress symptoms = strongest correlates | effect_ranking | Compilo, pero no matcheo SQs (vars diferentes) |
| C3 | soil acidity → metals AND vigor | ABSTENTION | "multiple claims present" |
| C4 | residual site differences | ABSTENTION | "not testable effect among listed variables" |

### Contraste: Coral case

De 5 claims, 4 compilaron (pattern=observational_association). La algebra A21
les dio 0.65 credito parcial contra SQs causales. Score total: 0.552.

### Diagnostico

El solver escribe como investigador real. El compiler tiene un formulario
con UN treatment y UN outcome. Claims compuestos no entran → ABSTENTION → 0.00.

## Por que tenemos solo 8 patterns fijos

Los 8 patterns (`PatternClass` en `oi_compiler.py`) fueron disenados como
atajos de compilacion: cada pattern tiene un `lower_intent()` hardcodeado
que produce AtomicSpecs especificos. Son "recetas" para los tipos mas comunes.

```
causal_effect, mediation, heterogeneity, tail_risk,
variance_effect, observational_association, effect_ranking, confounding
```

**El problema:** esto es un cuello de botella innecesario. La gramatica
composable de verificacion (`open_investigation.py`) es MUCHO mas expresiva:

- 5 tipos de simulacion (QueryKind: intervene, observe, condition, adjust, sweep)
- 10 tipos de medicion (MeasurementKind: mean, variance, quantile, tail_prob,
  correlation, partial_correlation, distribution, identifiability_check, prob)
- 8 tipos de comparacion (ComparisonKind: identity, difference, ratio, ranking,
  gap, proportion, piecewise_fit, contrast_diff)
- 12+ tipos de asercion (AssertionKind: positive, negative, near_zero,
  greater_than, rank_order, changepoint_exists, sign_flip, gap_material,
  identifiable, not_identifiable, distinguishable, not_distinguishable)

El AtomicSpec ya dice en su docstring:
> "Any claim can be decomposed into 1..N AtomicSpecs."

Y el verifier ya sabe ejecutar todo esto contra el SCM. Deterministico, exacto.

## Propuesta: patterns como fast-path + compilacion directa como fallback

### Insight del usuario (2026-03-29)

Los 8 patterns no estan mal — son recetas utiles para los casos comunes.
El problema es que cuando un claim NO encaja en ninguna receta, el sistema
abstiene en vez de intentar construir la verificacion directamente.

### Arquitectura propuesta (hibrida)

```
ClaimCard
  → LLM intenta matchear con 1..N patterns conocidos (fast-path)
  → Si algun fragmento no matchea ningun pattern:
    → LLM construye AtomicSpec(s) directamente usando la gramatica composable
    → (fallback path)
  → Opcionalmente: guardar nuevas "recetas" que emergen del fallback
    para que se vuelvan fast-path en el futuro
```

**Tres cambios concretos:**

1. **Multi-intent:** Un claim puede producir N intents (para claims
   compuestos que SÍ encajan en patterns conocidos). Ej: "mining →
   metals → vigor" = 2 intents obs_association.

2. **Fallback a gramatica composable:** Cuando un fragmento del claim
   no encaja en ningun pattern, el compiler construye el AtomicSpec
   directamente usando QueryArm + Measurement + Comparison + Assertion.
   Ej: "residual site differences after controlling" → OBSERVE arms +
   MEAN measurement + DIFFERENCE comparison + GAP_MATERIAL assertion.

3. **Guardar recetas nuevas (opcional):** Si el fallback produce un
   AtomicSpec que se repite (ej: residual analysis), se puede cristalizar
   como un nuevo pattern para el fast-path. Los patterns crecen
   organicamente en vez de ser fijos.

### Que resuelve

| Claim problemático | Fast-path | Fallback |
|-------------------|-----------|----------|
| C1: mining → metals → stress → vigor | 2-3 intents obs_association | — |
| C3: soil acidity → metals AND vigor | 2 intents obs_association | — |
| C4: residual site differences | — | AtomicSpec directo (group comparison) |
| Futuro: dose-response, threshold | — | AtomicSpec directo (sweep + piecewise) |

### Por que es mejor que los otros caminos

- **vs solo multi-intent:** Multi-intent solo resuelve claims compuestos
  de tipos conocidos. No resuelve tipos nuevos (residuales, dose-response).
- **vs eliminar patterns:** Los patterns son utiles como atajos. No hay
  razon para eliminarlos. Solo falta el fallback.
- **vs no hacer nada:** El solver escribe como investigador real. Si el
  sistema no puede evaluarlo, RL no aprende. Es critico.

## Recomendacion

1. **Inmediato:** Multi-intent (claims compuestos → N patterns conocidos).
   Cambio minimo, desbloquea C1 y C3.
2. **Siguiente paso:** Fallback a gramatica composable para claims que
   no encajan en ningun pattern. Desbloquea C4 y tipos futuros.
3. **Largo plazo:** Guardar recetas nuevas que emergen del fallback.

## Preguntas abiertas (para debatir con Codex)

1. Si el compiler genera AtomicSpecs directamente, como se hace el
   matching con sub-questions? Hoy usa pattern + roles. Con AtomicSpecs
   libres, el matching necesita ser semantico.
2. Como evitar que el LLM genere AtomicSpecs invalidos? La gramatica
   tiene combinaciones que no tienen sentido (ej: sweep + tail_prob).
3. El scoring de sub-questions necesita una nocion de "que pregunta
   responde este spec". Hoy eso viene del pattern. Sin patterns, de
   donde viene?
4. Multi-intent: cuando un claim tiene 3 pares, como se distribuye el
   credito? Cada par da credito independiente? Hay descuento?

## Conexiones

- **A21** — la algebra de compatibilidad sigue siendo necesaria para
  el matching, independientemente de A vs B.
- **Investigacion previa:** `research/notes/scm_task_primitives.md` —
  propuesta de primitivas composicionales. Mismo espiritu que Camino B.
- **Vision OI:** `research/synthesis/open_investigation_vision.md` —
  la gramatica composable fue disenada exactamente para esto.
- **23 escenarios:** `research/synthesis/investigation_scenarios_rubric.md` —
  validar que cualquier cambio siga cubriendo estos escenarios.
