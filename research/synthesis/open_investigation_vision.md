# Open Investigation: investigacion libre con verificacion SCM exacta

> **Status:** VISION EN DESARROLLO. Debate activo, no implementar todavia.
> **Fecha:** 2026-03-25 (actualizado 2026-03-26 con debate extendido)
> **Participantes:** Usuario, Claude, Codex (gpt-5.4), ChatGPT (sesion paralela)
> **Working doc:** `notes/open_investigation_case_analysis.md` (30 casos, debate)

## Explicacion simple (empieza por aca)

### Hoy: examen con preguntas

Hoy SREG es como un profesor que le da un examen al alumno con preguntas
especificas:

> "Pregunta 1: cual es el efecto de la presion sobre el arenamiento?"
> "Pregunta 2: que importa mas, la presion o la viscosidad?"

El alumno responde cada pregunta, y nosotros tenemos la respuesta exacta
(el SCM). Facil de corregir, pero **no es investigacion** — es un examen.

### Lo que queremos: investigacion libre

Queremos darle al solver lo que le darian a un investigador real:

> "Tenes datos de pozos en Vaca Muerta. Algunos se arenan, otros no.
> Averigua por que y que se puede hacer."

El solver investiga, analiza los datos, y al final entrega un reporte:

> "La presion es el factor principal. Opera a traves del colapso de
> fracturas. La viscosidad modera el efecto."

**El problema: como le ponemos nota a eso?**

### El truco: traducir y verificar

Nosotros tenemos la verdad completa (el SCM). El solver no lo sabe, pero
nosotros si. Entonces:

1. **El solver** investiga libre y escribe su reporte
2. **Un traductor** (otro LLM) lee el reporte y lo convierte a preguntas
   formales:
   - "La presion es el factor principal" -> verificar efecto causal de presion
   - "Opera a traves de fracturas" -> verificar mediacion
   - "La viscosidad modera" -> verificar interaccion
3. **El SCM** responde cada pregunta con la verdad exacta

Es como tener un profesor que lee la tesis del alumno, la descompone en
afirmaciones verificables, y las checkea contra la realidad.

### Preguntas clave resueltas

**"Una nota final o varias?"** — Varias. El solver entrega hasta K=5
claim cards semi-estructuradas. Cada una se verifica por separado.
Un claim complejo se descompone en N atomos verificables.

**"Y si hace mil afirmaciones a ver si alguna pega?"** — Cap de K=5
claims. Precision gate: si precision < umbral, coverage no paga.
Novel claims = bucket de auditoria en Alpha, no reward online.

**"Y si llega al resultado correcto pero sin investigar?"** — Warrant
via log check: observo las variables relevantes antes de afirmar?
Sin LLM judge, suficiente para Alpha.

**"Y el traductor? Si traduce mal?"** — Compile-preview loop: el
compilador muestra una parafrasis canonica ("entendi que X causa Y en
contexto Z, es asi?"). El solver corrige en lenguaje natural, NUNCA
edita specs formales. Maximo 2 rondas. Si no se aclara → unscorable.

**"Solo podemos verificar un catalogo fijo?"** — NO. Gramatica
composable de 4 piezas: Simulacion + Medicion + Comparacion + Asercion.
Cualquier combinacion valida es verificable. Los "operadores" son macros
(shortcuts frecuentes), no limites. Ver detalle abajo.

### Honestidad sobre "exact reward"

El reward NO es exact end-to-end en modo Open. Lo honesto:
- **Modo Guided:** reward exacto (como hoy, sin cambio)
- **Modo Open:** verificacion SCM exacta DESPUES de compilacion.
  La compilacion tiene subjetividad encapsulada (claim cards la reducen,
  preview loop la audita, abstention la acota)
- **Lo que decimos:** "exact SCM-grounded verification core"
- **Lo que NO decimos:** "exact reward" sin calificar

### Orden de construccion

1. **Gramatica de verificacion**: definir las 4 piezas composables +
   macros frecuentes como DSL ejecutable
2. **Truth map algoritmico**: dado un SCM, enumerar verdades canonicas
   agrupadas en familias. Sin LLM.
3. **Claim card contract**: Pydantic models para ClaimCard, AtomicSpec,
   CoverageFamily
4. **Verifier scoring**: dado un set de claims formales perfectos,
   computar correctness + coverage. Sin traductor, sin LLM.
5. **Compiler benchmark offline**: 200+ claims, 15+ mundos, >90%
   precision, >95% harmful-error control
6. **Piloto scaffolded**: solver real + compiler + scoring

### Criterios de exito del Alpha

- El no-data baseline puntua claramente peor que un solver que investiga
- El shotgun (tirar muchos claims) no puede explotar el coverage
- El compilador tiene >90% precision en benchmark offline
- El score es estable ante variaciones del compilador
- Un solver mejor realmente supera a uno peor por margen interpretable

---

## El problema (version tecnica)

Hoy SREG le dice al solver QUE preguntar y COMO responder:

> "Cual es el efecto causal promedio de X en Y? Submitea un numero."

Esto es verificable pero artificial. Un investigador real no recibe preguntas
pre-armadas — recibe un problema abierto y tiene que descubrir que investigar.

El resultado: SREG mide si el solver RESPONDE bien, pero no si INVESTIGA bien.
La estrategia investigativa (que preguntar, por que, en que orden) no se evalua.

## La vision

El solver recibe un encargo de investigacion abierto y reporta hallazgos
libremente. Un pipeline de verificacion traduce esos hallazgos a queries
formales y los chequea contra el SCM. El reward es exacto.

### El patron universal

Toda investigacion real tiene esta estructura:

1. **Pregunta primaria** (vaga, motivada por el dominio): "Que causa el
   arenamiento en pozos de shale?"
2. **Sub-preguntas instrumentales** (que el investigador genera mientras
   explora): cuales son los factores, por que mecanismo operan, hay
   interacciones, hay confounders, cuanto impacta cada uno.
3. **La calidad de la investigacion** = calidad de sub-preguntas generadas
   + calidad de respuestas.

Este patron aplica a investigacion empirica explicativa en general: clinica,
social, experimental, field science, ingenieria causal, operations.

### Arquitectura de 3 capas

```
Solver                     LLM Translator              SCM Verifier
  |                            |                           |
  |  Investiga libre.          |                           |
  |  Reporta hallazgos    --> |  Traduce hallazgos a  --> |  Computa verdad
  |  en lenguaje natural.      |  queries formales.        |  exacta contra SCM.
  |                            |  (NO juzga, traduce)      |  Score determinista.
  |                            |                           |
```

**Solver**: investiga libre, reporta como investigador. No necesita saber que
es un ATE o una mediacion. Solo describe lo que encontro.

**LLM Translator**: traduce los hallazgos del solver a queries formales contra
el SCM. Rol analogo al orchestrator (que traduce papers a SCM specs). No es
juez — es compilador. Si un hallazgo es ambiguo, lo marca como "unscorable"
en vez de adivinar.

**SCM Verifier**: ejecuta cada query formal contra el SCM y computa la verdad
exacta. Determinista, sin LLM, sin heuristica. Este es el nucleo del reward.

### La analogia clave

El orchestrator ya hace exactamente este patron en la direccion opuesta:

```
Paper (libre) --> LLM traduce --> SCM specs (formal) --> tools construyen (exacto)
```

La verificacion es el mismo patron invertido:

```
Hallazgos (libre) --> LLM traduce --> queries formales --> SCM verifica (exacto)
```

## Dimensiones de scoring

### 1. Correctness (precision)
Cada hallazgo traducido se verifica contra el SCM. Es correcto o no.

### 2. Relevance (conducencia)
El hallazgo es conducente a la pregunta primaria? Verificable via el grafo
causal: si las variables del claim estan en la vecindad causal del target
de la pregunta primaria, es relevante. Si no, es irrelevante. Exacto.

### 3. Coverage (salient coverage)
Encontro los hallazgos importantes? Se compara contra claims verdaderos
significativos del SCM. No contra un answer key escrito a mano — contra
TODOS los claims verdaderos auto-generados del SCM (enumerar primitivas
sobre variables visibles).

Esto resuelve el "problema del camino diferente": si el solver descubre
A->D->C en vez de A->B->C (ambos reales en el SCM), recibe credito.

### 4. Calibration
La confianza que reporto matchea la realidad? Claims mas especificos
(cuantitativos) ganan mas reward si aciertan, mas penalidad si erran.

### 5. Efficiency
No gasto budget en exploracion irrelevante? No hizo "shotgun" de claims
esperando que algunos peguen?

### Pesos tentativos (de Codex)
- Precision/accuracy: 50% (con gate: coverage solo paga si false-positive rate es bajo)
- Salient coverage: 25%
- Efficiency: 15%
- Calibration: 10%

## Desafio central de diseno

> **Cual es el minimo de estructura que necesitamos pedirle al solver para
> poder verificar sus hallazgos, sin sesgarlo hacia los hallazgos que
> nosotros esperamos?**

### La respuesta: convenciones de reporte, no formato de respuesta

Como un paper cientifico: el journal no dice QUE descubrir, pero si dice
COMO reportar resultados. Convenciones minimas que habilitan verificacion
sin sesgar la investigacion.

### El LLM translator como puente

La decision de diseno clave: NO pedirle al solver que use primitivas
formales (eso lo sesga). En vez, dejar que reporte libre y usar un LLM
translator para compilar hallazgos a queries. Esto elimina el sesgo:
el solver no necesita saber que tipos de evaluacion existen.

El riesgo (mistranslation) se mitiga con:
- Claims ambiguos marcados como "unscorable"
- El solver puede ver la compilacion y corregir
- Medicion empirica de la reliability del translator

## Auto-generacion de la agenda oculta

En vez de escribir un answer key a mano, auto-generar TODOS los claims
verdaderos significativos del SCM:

1. Enumerar primitivas (effect, mediation, interaction, confounding, etc.)
   sobre pares/tripletas de variables observables
2. Computar ground truth para cada una
3. Filtrar por significancia (effect size > threshold)
4. Clusterar en "familias de hallazgos" equivalentes
5. Dar credito a cualquier claim del solver que matchee una familia

Esto es generativo, no manual. Escala con el tamano del SCM.

**Correccion importante (Codex):** coverage debe ser contra claims
DESCUBRIBLES dado el budget y la evidencia visible del episodio, no contra
todos los verdaderos del SCM. No premiar descubrimientos imposibles.

## Dimensiones de scoring — version refinada (con feedback Codex)

### 1. Correctness (precision) — ~40%
Cada hallazgo traducido se verifica contra el SCM.

### 2. Warrant (justificacion evidencial) — ~20%
**Dimension critica agregada por Codex.** Un claim puede ser verdadero en
el SCM pero mal fundamentado. Mide:
- Era identificable desde la evidencia visible?
- El solver junto la evidencia necesaria antes de afirmarlo?
- La fuerza del claim es proporcional al soporte?

Esto separa "investigar bien" de "acertar por priors" — es exactamente
lo que LA PREGUNTA del proyecto pide. Sin esta dimension, un solver que
responde desde pretraining sin mirar datos podria sacar buen score.

### 3. Relevance (conducencia) — ~15%
Tres sub-tipos (no solo causal):
- **Causal**: el claim involucra ancestros, mediadores, confounders o
  descendientes del target de la pregunta primaria
- **Epistemica**: el claim ayuda a distinguir mecanismos rivales
- **Operacional**: el claim afecta que medir o en que confiar

Para data quality y metodologia: si el hidden truth incluye un modelo de
observacion (missingness, measurement error, etc.), se puede verificar.
Si no, esos claims quedan sin puntuar.

### 4. Coverage (salient coverage) — ~15%
Encontro los hallazgos descubribles y significativos? Contra claims
auto-generados del SCM, filtrados por descubribilidad.

### 5. Calibration — ~5%
La confianza reportada matchea la realidad?

### 6. Efficiency — ~5%
No gasto budget en exploracion irrelevante?

**Nota:** los pesos son tentativos. Precision + warrant dominan (~60%)
porque sin ellos se premia al solver que hace shotgun o aciertan por suerte.

## Convenciones minimas de reporte

En vez de pedir primitivas formales (que sesgan), pedir convenciones de
escritura que hagan la compilacion tractable sin limitar la investigacion:

- Un hallazgo principal por parrafo o bullet
- Nombres explicitos de variables/entidades (no pronombres vagos)
- Separar hallazgos de caveats/limitaciones
- Separar descripciones de los datos de conclusiones causales

Estas son convenciones de estilo cientifico, no formatos de respuesta.
Cualquier paper real las cumple.

## El translator: sound but incomplete

Principio de diseno clave (Codex): el translator debe ser **correcto pero
incompleto** — abstener seguido, adivinar nunca. Mejor dejar un claim sin
puntuar que traducirlo mal.

Modos de fallo a trackear por separado:
- Wording ambiguo (culpa del solver)
- Tipo de claim no soportado (limitacion del sistema)
- Error del translator (bug a corregir)

El solver puede ver la compilacion y corregir antes del submit final.
Esto crea un "compile-preview loop" que mejora reliability sin limitar
libertad.

**Precision sobre exactitud:** el verifier es exacto (SCM). El pipeline
end-to-end es "exacto despues de compilacion". La compilacion introduce
un margen de error controlable pero real. No overstatar la exactitud del
sistema completo.

## Modos de evaluacion

### Guided (evolucion del modo actual)
- El solver recibe: brief + preguntas instrumentales explicitas
- Scoring: per-question exact (como hoy)
- Util para: training inicial, warm-up, evaluacion dirigida
- Ensenia: inferencia local, uso de herramientas, formato

### Scaffolded (intermedio)
- El solver recibe: brief + deliverables vagos ("identifica los drivers
  principales", "evalua mecanismos") sin preguntas formales
- Scoring: como Open pero con hints de direccion
- Util para: donde empieza el skill real de investigacion
- Ensenia: decidir que investigar, cuando la evidencia es suficiente

### Open (completo)
- El solver recibe: solo el brief con la pregunta primaria
- Scoring: correctness + warrant + relevance + coverage + calibration +
  efficiency
- Util para: medir calidad de estrategia investigativa completa

### Curriculum: mixto, no secuencial
**Codex advierte:** Guided-only no transfiere bien a Open. El skill real
(decidir que investigar, cuando parar, que reportar) se entrena en
Scaffolded, no en Guided. Usar curriculum mixto con weight shifting,
no fases limpias secuenciales.

## Que NO es esta vision

- **No es "free-form NL scoring".** El LLM traduce, no juzga. El scoring
  siempre es contra el SCM (despues de compilacion).
- **No es "eliminar preguntas tipadas".** Las preguntas siguen existiendo
  como agenda oculta y como modo Guided.
- **No es implementable manana.** Requiere: translator pipeline, auto-claim
  generation, scoring framework nuevo, y mucho testing.

## Conexion con el proyecto

- Responde a la tension "Apertura del problema vs verificabilidad exacta"
  de PROJECT.md — esta es la solucion.
- Extiende el trabajo de brief_vs_eval_separation (las 3 capas que ahi se
  identificaron: brief visible, eval agenda, query formal).
- Complementa scm_task_primitives (las primitivas son el vocabulario
  del translator y del claim generator).
- Es la siguiente evolucion natural despues de completar el pipeline
  orchestrator -> SCM.

## Diseno del Alpha (evolucionado con debate extendido 2026-03-26)

### Modo: Scaffolded Open

- Brief abierto con pregunta primaria y target claro
- Solver investiga libre con python_exec + think + submit
  (budget y observe NO corren hoy, son mejora futura)
- Entrega: hasta K=5 claim cards semi-estructuradas
- Compiler traduce cada card a 1..N atomic specs verificables
- Verifier scorea contra el SCM

### Gramatica composable de verificacion (reemplaza primitivas fijas)

**ANTES:** 4 primitivas fijas (ate, mediation, interaction, rank_effect).
**AHORA:** gramatica de 4 piezas composables.

Toda verificacion = Simulacion + Medicion + Comparacion + Asercion.

**Simulacion** (que experimento correr):
- `do(X=valor)`, `do(X=valor) | Z=estrato`, `sweep(X, rango)`,
  `do(X=a, Y=b)` (bundle), `baseline`

**Medicion** (que medir):
- `mean(Y)`, `variance(Y)`, `quantile(Y, q)`, `P(Y > umbral)`,
  `correlation(A, B)`, `distribution_shape(Y)`

**Comparacion** (como comparar):
- `difference`, `ratio`, `ranking`, `piecewise_fit`, `gap`, `proportion`

**Asercion** (que debe ser verdad):
- `positive`, `negative`, `near_zero`, `A > B`, `changepoint_exists`,
  `sign_changes_by_stratum`, `gap_material`

Operadores nombrados = macros (shortcuts frecuentes):
- `mean_contrast` = do(X=a) vs do(X=b) + mean(Y) + difference + sign
- `tail_risk_contrast` = do vs baseline + P(Y>p90) + difference + positive
- `regime_change_scan` = sweep(X) + mean(Y)/level + piecewise_fit + exists
- `policy_rank` = do(A) vs do(B) + mean(Y) + ranking + A>B
- `mediation_decomp` = do(X) directo vs via M + mean(Y) + proportion + >0
- `interaction_contrast` = do(X)|Z=hi vs Z=lo + mean(Y) + difference + sign
- `measurement_gap` = baseline + obs vs latente + gap + material

Agregar tipo de verificacion nuevo = combinar piezas o agregar pieza
atomica nueva. NO requiere cambiar la arquitectura.

### Claim card del solver

El solver no escribe prosa libre ni specs formales. Escribe claim cards:

```yaml
claim_text: >
  La puntualidad del pago importa mas que el monto para reducir
  inseguridad alimentaria.
focus_variables: ["puntualidad", "monto", "inseguridad_alimentaria"]
outcome_aspect: "media de inseguridad alimentaria"
comparison_text: "puntualidad vs monto"
scope_text: "global"
pattern_tags: ["ranking", "effect_comparison"]
confidence: 0.8
evidence_basis:
  - artifact_id: transfer_panel
    rationale: "Regresion muestra coef de puntualidad 3x mayor que monto"
```

Slots minimos: claim_text, focus_variables, confidence, evidence_basis.
Los demas son opcionales pero mejoran la compilacion.

### Compile-preview loop

1. Solver entrega claim cards
2. Compiler genera parafrasis canonica: "Entendi que la puntualidad tiene
   mayor efecto que el monto sobre inseguridad alimentaria. Confirmas?"
3. Solver corrige en lenguaje natural si hace falta (max 2 rondas)
4. Compiler genera atomic specs ejecutables
5. Verifier ejecuta contra SCM

**Regla dura:** el solver NUNCA edita specs formales, solo claim cards.
El preview es clarificacion semantica, no formulario tecnico.

Para eval formal: loop completo. Para RL training: claim cards explicitas
+ compilador local, sin preview (costo).

### Truth map algoritmico

Antes del solver, enumerar verdades canonicas del SCM sin LLM:
1. Todos los ATEs pairwise
2. Todas las mediaciones por path
3. Todas las interacciones por par × target
4. Heterogeneidad por estrato
5. Quantile effects
6. Regime changes / thresholds
7. D-separations no obvias
8. Policy comparisons simples

Filtrar por effect size > threshold. Clusterar en familias.
Family key = (brief_target, focus_signature, pattern_class, scope_class).

Para relevance/salience: necesita "intent metadata" del generador del caso
(target primario, variables manipulables, tipo de investigacion).

### Scoring Alpha

| Dimension | Peso | Que mide |
|-----------|------|----------|
| Correctness | 60% | Cada atomo verificado contra SCM |
| Coverage | 30% | Familias canonicas descubiertas (con precision gate) |
| Efficiency | 10% | No shotguneo, claims relevantes al brief |

**Simplificaciones vs diseño original:**
- Sin calibration en Alpha (muy pocos claims por episodio)
- Sin warrant formal (solo log check basico como proxy)
- Sin relevance contract rico (solo proximity al target)
- Novel claims = bucket de auditoria, no reward

**Gates:**
- K <= 5 claims
- Precision gate sobre coverage (si precision < umbral, coverage = 0)
- Deduplicacion por familia

### Stress test: 30 casos evaluados

De 30 respuestas diversas en 10 dominios:
- 12 FUNCIONA (40%): efectos causales, mediacion, heterogeneidad, policies
- 13 PARCIAL (43%): rescatables con operadores o metadata extra
- 5 NO FUNCIONA (17%): taxonomias, subidentificacion, evidencia comparada

Los que rompen son claims EPISTEMICOS, no causales complejos.
Ver `notes/open_investigation_case_analysis.md` para detalle completo.

## Proximos pasos de investigacion (actualizado 2026-03-26)

1. **Formalizar la gramatica composable** como DSL ejecutable con las 4
   piezas + macros nombradas.

2. **Prototype truth map**: dado un SCM real, enumerar verdades canonicas
   agrupadas en familias. Verificar que el volumen es manejable.

3. **Disenar claim card contract**: Pydantic models con slots minimos.
   Probar si el formato es natural para un solver.

4. **Compiler benchmark offline**: 200+ claims, 15+ mundos, multiples
   estilos. Target: >90% precision, >95% harmful-error control.

5. **Verifier scoring sin compiler**: probar scoring con claims formales
   perfectos. Validar que correctness + coverage separan buenos de malos.

6. **Piloto scaffolded**: solver real + compiler + scoring.

### Lineas de exploracion abiertas

- Identifiability check como operador nuevo (rescata 2/5 NO FUNCIONA)
- Multi-outcome trade-offs (rescata 1/5 si SCM tiene ambos outcomes)
- Coherence-lite via support graph (bonus 5-10%)
- Intent metadata del generador para relevance algoritmico
- Compilador fino-tuneado local para reducir costo en RL

## Origen de esta idea

Sesion 2026-03-25. El usuario observo que las preguntas seguian sonando a
ejercicio de libro de texto y pregunto: "no deberiamos tener una pregunta
principal y secundarias que aporten a la principal? y que lo que testeemos
sea que el solver genere tambien esas mismas sub-preguntas?"

Eso llevo a la discusion sobre libertad investigativa, el rol del LLM
translator (analogo al orchestrator pero en la direccion inversa), y como
mantener reward exacto sin sesgar al solver.
