# SCM Task Primitives: Architectural Decision

> Status: PARCIALMENTE IMPLEMENTADO (2026-03-21, Fase 6)
> Contexto: ate, mediation, interaction implementados. Resta: dose_response,
> threshold, instrument_validity, collider_bias, etc.

## El problema

Hoy SREG tiene 9 task types fijos (infer_target, causal_effect, should_condition,
etc.). Cada type bundlea tres cosas:
1. Que se pregunta (semantica)
2. Como se computa el ground truth desde el SCM/BN
3. Como se scorea la respuesta

Con el SCM engine continuo, los 9 types originales son insuficientes. Hay
preguntas cientificas reales que antes no se podian hacer:
- Dose-response, threshold detection, nonlinearity, mediation, interaction,
  instrument validity, selection bias, etc.

## Alternativas evaluadas

### A. Expandir a 15-20 types fijos
- Simple, seguro, reward exacto garantizado
- Pero monolitico: cada type es una unidad indivisible
- No escala bien a la variedad de preguntas cientificas reales

### B. Preguntas libres + validacion on the fly
- El LLM propone preguntas en lenguaje natural libremente
- El sistema intenta inferir como computar ground truth
- **RECHAZADA**: no se puede tener preguntas realmente libres Y reward exacto.
  Si el sistema no puede mapear la pregunta a un metodo de verificacion,
  cae en LLM-judge scoring — exactamente lo que SREG evita.

### C. Primitivas composicionales (PROPUESTA ELEGIDA)
- Un set de primitivas computacionales que sabemos evaluar exactamente
- El LLM propone la query formal (primitiva + parametros) Y el texto en NL
- El sistema VALIDA que la query compile y computa el ground truth
- "Free-form wording, closed-form semantics"

## Primitivas propuestas

Estas son las operaciones que podemos computar exactamente desde un SCM:

### Distribuciones
- `marginal(target)` — P(Y), distribucion marginal
- `conditional(target, evidence)` — P(Y|X=x)
- `interventional(target, do)` — P(Y|do(X=x))

### Efectos causales
- `ate(treatment, outcome)` — Average Treatment Effect
- `cate(treatment, outcome, subgroup)` — Conditional ATE
- `mediation(X, M, Y)` — efecto directo vs indirecto
- `interaction(X, Z, Y)` — effect modification

### Estructura causal
- `d_separation(X, Y, Z)` — independencia condicional
- `adjustment_set(treatment, outcome)` — set de ajuste valido
- `instrument_validity(Z, X, Y)` — es Z un instrumento valido?
- `collider_bias(X, Y, C)` — condicionar en C abre camino espureo?

### Relaciones funcionales (nuevas con SCM continuo)
- `nonlinearity(X, Y)` — la relacion es lineal o no?
- `threshold(X, Y)` — hay un punto de cambio?
- `dose_response(X, Y, levels)` — curva dosis-respuesta
- `saturation(X, Y)` — hay efecto techo/piso?

### Meta
- `compare_interventions(target, do_A, do_B)` — cual intervencion es mejor?
- `optimal_intervention(target, variables, goal)` — que intervenir para maximizar/minimizar?

## Composicion

Las primitivas se componen. Ejemplo:
- "Cual es el efecto causal de X sobre Y controlando por Z?"
  → `ate(X, Y)` con `adjustment_set(X, Y)` verificado
- "La relacion es no-lineal y tiene un threshold?"
  → `nonlinearity(X, Y)` + `threshold(X, Y)`

## Scoring

Cada primitiva define su scoring:
- Distribuciones: KL divergence
- Efectos numericos: error absoluto relativo
- Si/No: exact match
- Sets: Jaccard similarity o exact match

## Riesgo de mapping incorrecto

El LLM puede equivocarse mapeando pregunta NL → primitiva. Pero este riesgo
YA EXISTE con los 9 task types actuales — el LLM ya puede equivocarse
mapeando una pregunta a un task type. No es un problema nuevo.

La mitigacion es validacion: el sistema verifica que la primitiva es aplicable
al mundo (los nodos existen, las relaciones existen, el ground truth es computable).

## Restriccion sagrada

**El reward exacto es innegociable.** Si una pregunta no puede mapearse a una
primitiva con ground truth computable, se RECHAZA. Nunca LLM-judge.

## Estado de implementacion (Fase 6, 2026-03-21)

Implementadas como task types en SCMTaskGenTool + SCMSolver:
- `ate` (Average Treatment Effect) — numeric scoring
- `mediation` (NDE/NIE decomposition) — numeric scoring
- `interaction` (effect modification detection) — yes/no scoring

Pendientes (futuras fases):
- `dose_response`, `threshold`, `saturation` — curvas de efecto
- `instrument_validity`, `collider_bias` — estructura causal avanzada
- `cate` (Conditional ATE) — efecto heterogeneo cuantitativo
- Arquitectura composicional completa (primitiva + parametros como query formal)
