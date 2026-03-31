# S05 — SQ diversity bottleneck: diagnosis + direction

**Date:** 2026-03-30
**Type:** Analisis / decision de direccion
**Branch:** autoresearch-open-investigation
**Status:** SUPERSEDED por `synthesis/sq_v2_matching_spec.md`. Diagnostico y evidencia siguen siendo validos.
**Prerequisitos:** S04, A23, A24

## El hallazgo

Despues de generar 14 experimentos E2E con seeds intencionalmente diversas
(causal, predictivo, epistemologico, system mapping, selection bias, competing
mechanisms, policy equity, value of information, methodology, descriptivo,
tradeoff, deep heterogeneity), auditamos los SQs reales generados por el
orchestrador.

**Resultado: TODOS los experimentos generan los mismos tipos de SQ.**

| Pattern | Aparece en N/10 experimentos auditados |
|---|---|
| causal_effect | 10/10 |
| confounding | 8/10 |
| effect_ranking | 6/10 |
| mediation | 6/10 |
| observational_association | 4/10 |
| heterogeneity | 4/10 |

Un estudio descriptivo/segmentacion (e2e_12) tiene SQs de `causal_effect` y
`mediation`. Un estudio de value-of-information (e2e_10) tiene SQs de
`mediation` y `confounding`. La diversidad del seed se pierde completamente
en el generador de SQs.

**Pero los claims del solver SI son mas diversos.** e2e_07 tiene claims sobre
sign reversal por seleccion, e2e_11 sobre sensibilidad a attrition, e2e_12
sobre composicion vs tiempo total. El solver investiga mejor de lo que las
SQs lo evaluan.

## La causa raiz

`SubQuestionIntent` esta atado a `PatternClass` — un enum de 8 patterns fijos.
El orchestrador no puede generar un SQ que diga:

- "que perfiles de uso existen" (descriptivo)
- "que medicion reduce mas la incertidumbre" (value of information)
- "cual estimador es mas robusto a missing data" (metodologico)
- "maximizar AUC en un holdout set" (predictivo puro)

Porque esos conceptos no caben en `causal_effect`, `mediation`, `confounding`,
`heterogeneity`, `observational_association`, `effect_ranking`, `tail_risk`,
o `variance_effect`.

El bottleneck no es solo el compiler (S04 ya mostro eso). Es toda la cadena:

```
seed → orchestrador → SQ (atado a catalogo) → claim matching → compiler → scoring
                       ^^^^^^^^^^^^^^^^^^^
                       la diversidad muere aca
```

## La decision — QUE ES Y QUE NO ES una SQ

### Las SQ SON necesarias

Sin SQs, un solver podria tirar claims triviales verdaderos ("X tiene media
positiva") y recibir score perfecto. Las SQ definen **que deberia cubrir la
investigacion** — son el mecanismo de relevancia.

### Las SQ NO deben estar atadas a un catalogo

El seed define el tipo de investigacion. Las SQs se construyen a partir del
seed y de lo que va armando el orchestrador. No pasan por un filtro de
"patterns conocidos".

### Los briefs pueden ser cualquier cosa

No hay que forzar un formato. Un brief puede ser:

- Preguntas vagas / deliverables abiertos: "investiga por que..."
- Preguntas concretas: "X causa Y? con que magnitud?"
- Metricas de evaluacion concretas: "maximiza AUC en holdout"
- Mix de todo lo anterior

El sistema debe tener la flexibilidad para manejar cualquiera de estos.

### Los tipos de investigacion se derivan del seed, no se clasifican

NO necesitamos una taxonomia operativa que el sistema consulte. La diversidad
viene del seed. El sistema se adapta al seed, no al reves.

La taxonomia (`Doc1_Taxonomia_El_Mapa.md`, `investigation_scenarios_rubric.md`)
sirve para:

- coverage audit: "estamos probando tipos suficientemente diversos?"
- seed design: "que seeds nos faltan?"
- failure mode analysis: "donde falla el sistema?"

Pero NO para: routing de scoring, seleccion de SQ patterns, bifurcacion de
metodos.

## La direccion concreta

### SQs atomicas, compiladas directamente

Las SQs deben construirse de la forma mas atomica posible, sin miedo, porque
se elaboran a partir del seed y del contexto que va armando el orchestrador.

El flujo correcto:

```
seed + orchestrador context
    → SQs libres (text_gloss + hidden verification)
    → compiladas directo a bundles de AtomicSpec
    → sin PatternClass intermedio
```

Esto es A23 aplicado a SQs: el mismo principio que ya validamos para claims
(S04), pero upstream.

### El compiler de claims tambien se libera

Como en S04, la compilacion de claims pasa directo a AtomicSpec:

```
solver claim → LLM + grammar → AtomicSpec(s) → verifier → verdict
```

Sin `ClaimIntent`, sin `PatternClass`, sin catalogo.

### El matching SQ-claim cambia

Hoy: `structural_compatibility()` compara `ClaimRepr` vs SQ `ClaimRepr` usando
`family_compat x operator_compat x role_compat`. Todo pasa por PatternClass.

Nuevo: matching sobre los AtomicSpecs mismos. Si una claim genera specs que
cubren las variables y mediciones de una SQ, esa claim satisface esa SQ.

## Que NO hacer

1. **No clasificar casos para bifurcar scoring.** UN solo metodo.
2. **No agregar patterns al catalogo.** El catalogo es el problema, no la solucion.
3. **No hacer mas audits.** Ya tenemos la evidencia: 10/10 experimentos
   causualizados. Siguiente paso es implementar, no diagnosticar mas.
4. **No disenar la arquitectura final todavia.** A24 es horizonte de mediano
   plazo. Lo siguiente es liberar SQs del catalogo (A23 scope).

## Secuencia de trabajo

1. **Liberar SQs del catalogo** — cambiar como el orchestrador genera SQs.
   No mas `pattern + roles`. SQs como text libre → compiladas a AtomicSpecs.
2. **Compilacion directa de claims** — ya prototipado en S04. Integrar al
   pipeline.
3. **Matching SQ-claim sobre specs** — reemplazar `structural_compatibility()`
   por matching sobre AtomicSpecs.
4. **Benchmark comparativo** — RECIEN ACA, con SQs diversas, comparar si el
   sistema evalua mejor investigaciones diversas.

## Conexiones

- **S04** — evidencia de que compilacion directa recupera semantica de claims
- **A23** — propuesta original de grammar-first. Este doc la extiende a SQs
- **A24** — horizonte de mediano plazo. AtomicSpec como subconjunto de runtime
- **CLAUDE.md** — "UN solo metodo", "el sistema se adapta", "brief libre"
- **PROJECT.md** — invariantes que este diseno respeta
