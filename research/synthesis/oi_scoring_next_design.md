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

## Matching claims vs sub-preguntas — ABIERTO

**Opcion A (programatica)**: matching por firma canonica
(`pattern_class + focus_variables + tipo de asercion`). Deterministico.
Pro: exacto, reproducible. Contra: puede perder claims que expresan
lo mismo de forma estructuralmente distinta.

**Opcion B (LLM judge)**: un LLM evalua si el claim responde a la
sub-pregunta. Pro: flexible, captura parafraseo. Contra: no deterministico,
agrega subjetividad al scoring.

**Opcion C (hibrido)**: matching programatico primero, LLM judge como
fallback para claims que no matchean pero parecen relevantes.

**Decision**: empezar con A, evaluar con pilotos, escalar a C si A pierde
claims importantes. La verdad siempre es SCM (exacta), solo el matching
de relevancia podria tener LLM.

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

## Preguntas abiertas para resolver durante implementacion

1. Cuantas sub-preguntas por caso? (intuicion: 3-7, depende de complejidad)
2. Como pesar sub-preguntas entre si? (todas iguales? el orchestrator asigna peso?)
3. El bonus por novel discovery: cuanto vale? (10-20% del total?)
4. El brief visible: lo genera el orchestrator a partir de las sub-preguntas,
   o son independientes?
5. Como validamos que las sub-preguntas del orchestrator son buenas?
   (rubrica? checklist? piloto humano?)
6. Backwards compatibility: como convivir con el scoring actual mientras
   se transiciona?

## Proximos pasos

1. Diseñar el modelo de datos (SubQuestion, EvaluationContract)
2. Modificar el orchestrator para que emita sub-preguntas
3. Implementar matching programatico (firma canonica)
4. Pilotar con 3 mundos curados: comparar scoring v2 vs scoring con sub-preguntas
5. Iterar segun lo que revelen los pilotos
