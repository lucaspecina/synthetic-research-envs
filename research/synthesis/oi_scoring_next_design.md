# OI Scoring: Next Design

> **Status: DESIGN EN PROGRESO.** Las decisiones marcadas DECIDIDO son firmes.
> Las marcadas ABIERTO pueden cambiar durante implementacion.
> Actualizar este doc a medida que se avanza.

## El problema

El scoring actual ancla todo a UNA variable target: relevancia = distancia
en el DAG al target, coverage = familias alrededor del target, salience map
= patrones del target. Esto solo funciona para ~3/23 escenarios de
investigacion reales (ver `investigation_scenarios_rubric.md`).

## La idea central — DECIDIDO

**El orchestrator genera sub-preguntas ocultas como criterio de evaluacion.**

Las sub-preguntas:
- Vienen del paper seed (que tiene preguntas reales de investigacion)
- Son adaptadas al mundo sintetico por el orchestrator
- Son la RAZON por la que el mundo fue construido asi
- Son verificables contra el SCM porque el orchestrator diseño el mundo para eso
- Son invisibles al solver

El brief visible al solver es una version vaga/general de las sub-preguntas.

### Ejemplo

**Seed** (paper): "Coffee reduces cardiovascular mortality — confounded by lifestyle?"

**Sub-preguntas ocultas** (orchestrator las genera al diseñar el caso):
1. El efecto de X en Y es causal o confundido por Z?
2. Hay relacion dosis-respuesta?
3. El efecto varia por subgrupo W?

**Mundo**: SCM construido para que (1) Z confunda X→Y, (2) haya dosis-respuesta
no lineal, (3) W module el efecto.

**Brief visible**: "Investigue la relacion entre consumo de X y el outcome Y."

**El solver no ve las sub-preguntas.** Investiga libremente y submitea claims.

## Pipeline unificado — DECIDIDO

Sub-preguntas y claims del solver pasan por el **mismo pipeline**:

```
Sub-pregunta (orchestrator)          Claim del solver
         |                                |
  [IR estructurado]                  [Compiler]
         |                                |
    AtomicSpecs                      AtomicSpecs
         |                                |
    [SCM verifica]                   [SCM verifica]
         |                                |
    Respuesta pre-computada          Respuesta del solver
         |                                |
         +------- MATCH formal ----------+
```

**Principio clave**: ambos lados producen specs formales comparables.
La verificacion es exacta (SCM). El matching es formal (specs vs specs),
no texto vs texto.

## Scoring — DECIDIDO (formula general)

```
score_claim = truth_score(SCM)
score_total = f(truth, coverage_sub_preguntas, no_redundancia, bonus_novel)
```

Donde:
- **truth_score**: SCM verifica el claim. Exacto, deterministico. No cambia.
- **coverage**: fraccion de sub-preguntas que tienen al menos un claim
  verdadero con specs que matchean.
- **no_redundancia**: claims que repiten lo que otro ya dijo no suman.
- **bonus_novel**: claims verdaderos que no matchean ninguna sub-pregunta
  pero son verdaderos y no triviales reciben credito parcial.

## Sub-preguntas como piso, no techo — DECIDIDO

Las sub-preguntas son lo MINIMO que se esperaba. Si el solver descubre
algo verdadero e importante que el orchestrator no anticipo, recibe
credito (bonus). Si las sub-preguntas fueran el techo, OI seria un examen
disfrazado.

## Generacion de sub-preguntas — DECIDIDO (principio), ABIERTO (mecanica)

**Principio**: el orchestrator genera las sub-preguntas AL MISMO TIEMPO
que diseña el mundo. No son un paso separado post-hoc. Son el design intent.

**De donde vienen**: del paper seed. El paper tiene preguntas reales.
El orchestrator las adapta al mundo sintetico.

**Formato de emision**: ABIERTO. Opciones:
- IR estructurado (ClaimIntent) emitido directamente por el orchestrator
  → lowering deterministico a specs (preferido por Codex)
- Texto natural → compiler LLM → ClaimIntent → specs
  (mas flexible pero agrega punto de fallo LLM)

**Validacion**: las sub-preguntas deben pasar checks deterministicos:
- Compilan a specs validos
- No son triviales (effect size minimo)
- Son diversas (no todas sobre lo mismo)
- Son respondibles con datos observacionales
- Son alcanzables con K claims (no pedir 20 cosas si el solver tiene 5 claims)

## Matching claims vs sub-preguntas — IMPLEMENTADO

**Implementado: Opcion A (programatica)** con subsumption table.

Matching por `pattern_class + role_signature` (treatment/outcome/mediator/etc).
Subsumption table permite credito parcial cross-pattern (e.g., mediation claim
da 0.6 credito a causal_effect SQ). Answer compatibility chequea que la
direccion del claim sea consistente con la respuesta resuelta.

Multi-component SQs (mediation, confounding) usan `ALL_OF` acceptance:
cada componente toma su mejor claim, ponderado por contribucion.

**Implementacion:** `src/sreg/tools/oi_subquestions.py` (7 Codex bugs fixed).
**Tests:** `tests/tools/test_oi_subquestions.py` (23 tests).
**Prototype:** `research/notes/oi_subquestion_prototype.md` (3 mundos).

## Que reemplaza del sistema actual

| Concepto actual | Se convierte en |
|---|---|
| `target_node: str` | No existe. Las sub-preguntas definen los focos (pueden ser multiples variables, o el sistema entero) |
| Salience map (mecanica) | Sub-preguntas del orchestrator compiladas a specs |
| Coverage (% familias) | % sub-preguntas respondidas |
| Relevancia (distancia DAG) | Match formal claim-specs vs sub-pregunta-specs |
| `investigation_type` | No existe. Las sub-preguntas se adaptan al tipo de caso |

## Que NO cambia

- **SCM como verdad**: no cambia. El SCM genera, verifica, es la fuente de verdad.
- **Compiler pipeline**: ClaimCard → ClaimIntent → AtomicSpecs. No cambia.
- **SCM verification**: specs → SCM → truth_score. No cambia.
- **Anti-shotgun basico**: max K claims, precision gate, redundancia.
- **Principio: verificabilidad > realismo > elegancia**.

## Brief y objetivos — DECIDIDO (principio), ABIERTO (formato)

**Principio**: el brief es libre. Puede tener:
- Un objetivo vago ("investigue que afecta X")
- Varios objetivos especificos ("investigue: 1) si... 2) que... 3) como...")
- Un objetivo amplio ("investigue este sistema")
- Cualquier combinacion

**El scoring se adapta al brief**, no al reves. Si el caso tiene un solo
foco, las sub-preguntas giran alrededor de ese foco. Si tiene multiples
focos, las sub-preguntas cubren todos. No hay tipos hardcodeados.

## Relacion con los 23 escenarios

Las sub-preguntas se adaptan naturalmente a cada tipo:

| Tipo | Ejemplo de sub-preguntas |
|---|---|
| Causal simple | "X causa Y?", "magnitud del efecto?" |
| Multi-outcome | "X mejora Y1?", "X empeora Y2?", "trade-off?" |
| System mapping | "A→B existe?", "C es bottleneck?", "que es critico?" |
| Confounding | "Z confunde X→Y?", "efecto crudo vs ajustado?" |
| Heterogeneidad | "efecto varia por W?", "que subgrupo se beneficia?" |
| Descriptivo | "que clusters hay?", "que distribucion tiene X?" |
| Predictivo | "X es predictor fuerte de Y?", "hay interaccion?" |
| Epistemologico | "el efecto es identificable?", "que falta medir?" |

## Riesgos y mitigaciones

| Riesgo | Mitigacion |
|---|---|
| Sub-preguntas malas → scoring malo | Validacion deterministica post-generacion |
| Matching programatico pierde claims | Empezar programatico, escalar a LLM si necesario |
| "Examen disfrazado" (sub-preguntas = techo) | Bonus para discoveries fuera de sub-preguntas |
| Orchestrator no puede generar sub-preguntas | Fallback: sub-preguntas genericas del SCM (como salience map actual) |
| Doble compilacion (sub-preguntas + claims) | Orchestrator emite IR directo, no texto |

## Preguntas resueltas durante implementacion

1. **Cuantas sub-preguntas?** 4-5 por mundo curado. Escala con complejidad.
2. **Como pesar?** Tiers: HIGH=1.0, MEDIUM=0.6, LOW=0.4. No continuos. [DECIDIDO]
3. **Novel bonus?** Cap al 20%. Formula: sum(truth)/n_claims * 0.5. [DECIDIDO]
4. **Brief visible?** Independiente de SQs. Viene del paper/orchestrator. [DECIDIDO]
5. **Validacion de SQs?** Resolucion deterministica post-world. Si no compila = invalida. [DECIDIDO]
6. **Backwards compat?** Dual scoring: v2 + SQ corren juntos, no se reemplaza todavia. [DECIDIDO]

## Preguntas aun abiertas

1. **Materiality threshold:** que valor por patron? Necesita calibracion empirica.
2. **Orchestrator genera SQs:** como? Template? Free-form? Que constraints?
3. **Total formula:** weighted_coverage*0.70 + correctness*0.20 + novel_bonus + coverage*0.10.
   Necesita validacion con pilotos reales.
4. **SQ independence:** SQ1 y SQ2 overlap (mediation implies causal effect).
   Subsumption maneja parcialmente, pero depende-on rules no implementadas.
5. **Compound claims:** "X and Y both affect Z" — split before matching?

## Proximos pasos (actualizado 2026-03-28)

1. [x] Diseñar modelo de datos (SubQuestionIntent, ResolvedSubQuestion)
2. [x] Implementar resolucion + matching + scoring (oi_subquestions.py)
3. [x] Pilotar con 3 mundos curados (manual SQs)
4. [x] Wiring dual scoring al runner
5. [ ] Validar con pilotos reales (E2E con LLM, dual scoring) — EN CURSO
6. [ ] Analizar: donde mejora el SQ score vs v2? Donde no?
7. [ ] Orchestrator genera SubQuestionIntents
8. [ ] Comparativo: manual SQs vs orchestrator SQs
9. [ ] Decidir si reemplazar v2 o mantener dual
