# SREG — TODO

> Brecha activa entre `ARCHITECTURE.md` y `CURRENT_STATE.md`.
> Statuses: `[ ]` pending | `[~]` in progress | `[x]` done | `[-]` cancelled
>
> **Estructura:** este documento separa analisis (cosas que hay que pensar
> o investigar) de implementacion (cosas que sabemos que queremos hacer o
> probar). Cada item de implementacion referencia el problema que lo motiva.
> Las ideas crudas nacen en `NOTES.md`, se investigan en `research/`, y
> cuando se vuelven trabajo concreto llegan aca.

---

## Analisis y problemas abiertos

Cosas que hay que pensar, entender o decidir antes de implementar.

### A1. Los SRCs no fuerzan investigacion real

Las preguntas causales se responden desde priors del dominio sin mirar los
datos. Las descriptivas (infer_target, causal_effect) si fuerzan analisis.

**Sub-preguntas:**
- [ ] Que hace que una pregunta sea "data-indexed"? Definir criterio claro.
- [ ] La ambiguedad mecanistica es la solucion? (ver NOTES.md)
- [ ] Cuanto de esto se resuelve con mejores preguntas vs cuanto necesita
  cambios estructurales (datos mas complejos, teoria inventada, etc)?

**Evidencia:** 7-SRC eval (2026-03-16), inspiration reports v2.

### A2. Faltan tipos de preguntas cientificas

Los papers reales preguntan cosas que nuestros 9 eval types no pueden
representar. El orchestrator las fuerza en los tipos existentes y pierde
lo mas interesante.

**Tipos que faltan:**
- [ ] **Mediacion** — "por que camino llega el efecto?"
- [ ] **Modificacion de efecto** — "para quien es diferente?"
- [ ] **Sesgo de seleccion** — "es real o es un espejismo?"
- [ ] **Atribucion de fuente** — "de donde viene?"
- [ ] **Efectos heterogeneos** — "funciona igual para todos?"

**Pregunta abierta:** para cada tipo, se puede evaluar con rigor contra la
BN? Si no, no pertenece al nucleo de SREG.

**Evidencia:** inspiration reports v2, NOTES.md seccion "Tipos de preguntas".

### A3. Semantica realista vs generica

Si usamos cosas basadas en la realidad, el modelo entrenado puede confundir
mecanismos inventados con conocimiento real. Quizas conviene des-realizar
la semantica para que aprenda el core de investigacion.

**Modos propuestos:** realistic (actual), fictional (nombres inventados),
abstract (X1/X2/Y), theory_rich (fictional + literatura inventada, futuro).

**Sub-preguntas:**
- [ ] Des-realizar mejora o empeora el razonamiento del solver?
- [ ] Hay evidencia de que los priors contaminan las respuestas?
- [ ] Que implicaciones tiene para el entrenamiento RL futuro?

**Referencia:** NOTES.md, PROJECT.md (tension estrategica). **Implementar:** I2.

### A4. Solo data-driven u otros tipos de investigacion?

SREG hoy es puro "descubrimiento desde datasets". La investigacion real
incluye teoria previa, papers, hipotesis existentes, resultados
contradictorios.

**Sub-preguntas:**
- [ ] Se puede agregar "literatura inventada" como capa visible?
- [ ] Teoria derivada parcialmente del mundo verdadero — viable?
- [ ] Esto cambia la direccion del proyecto (PROJECT.md)?

**Referencia:** NOTES.md seccion "Teoria inventada", "Solo data-driven".
**Implementar:** I7 (teoria inventada), y modo `theory_rich` en I2.

### A5. Taxonomia de investigaciones y research tasks

No tenemos claro los TIPOS de investigacion que existen, que dimensiones
tienen, y que tasks/preguntas se derivan de cada uno. Sin eso, no podemos
disenar bien las research tasks ni ampliar lo que el sistema puede hacer.

Hay un primer borrador en `research/notes/scientific_taxonomy.md` con 10
tipos + proceso en fases (framing, propose, plan, execute, analyze). Pero
falta profundizar con ejemplos reales de distintos dominios.

**Ejemplo real (surfactantes/petroleo):** seleccion basada en teoria y
tablas → prueba rapida de efectividad → 200-500 ensayos iterativos de
fine-tuning de estabilidad con ajustes finos. Esto es un patron de
investigacion industrial que combina knowledge retrieval, validacion
rapida, y optimizacion iterativa. Nuestros eval types no cubren nada
de esto.

**Sub-preguntas:**
- [ ] Que tipos de investigacion existen? (observacional, experimental,
  de campo, clinica, ingenieria, optimizacion iterativa, etc)
- [ ] Que dimensiones tienen? (fases, tipos de preguntas, tipos de datos,
  tipos de acciones, restricciones)
- [ ] Que hacen Research Gym, SciGym, DiscoveryBench, SciDesignBench como
  tasks? Que podemos aprender?
- [ ] Como se traduce cada tipo a tasks verificables en SREG?

**Referencia:** `research/notes/scientific_taxonomy.md`, inbox de TODO.

### A6. Estudiar como otros sistemas evaluan y entrenan

Estudiar Research Gym, SciGym, Kimi, SciDesignBench y otros proyectos
de RL agentico y long-horizon para entender como EVALUAN y ENTRENAN.
Esto no es para copiar sus tasks, sino para aprender:

- [ ] Que metricas usan para evaluar si un agente "investiga bien"?
- [ ] Como estructuran el RL loop (reward, episodes, curriculum)?
- [ ] Como miden agentic behavior (no solo respuestas correctas)?
- [ ] Que benchmarks usan para medir transferencia?
- [ ] Como hacen el training — que framework, que escala, que datos?
- [ ] Que podemos aprender para disenar nuestro propio eval y training?

Referencia: https://x.com/askalphaxiv/status/2030765298723283424
SciDesignBench: arxiv 2603.12724

**Esto es diferente de A5:** A5 es sobre taxonomia de investigaciones
reales (para disenar SRCs mas diversos). A6 es sobre como otros sistemas
miden y entrenan razonamiento cientifico (para evaluar SREG mejor).

### A7. Evaluaciones y validaciones existentes sin uso

Se construyeron QualitySuite, DiagnosticRunner, baselines, pero parte
quedo desactualizada o sin uso real. Hay que repasar que sirve y que no.

- [ ] QualitySuite: solo 3/9 eval types. Actualizar o reemplazar?
- [ ] DiagnosticRunner: funciona pero los resultados no se usaron para
  iterar. Como cerrar el loop?
- [ ] Baselines: son los correctos para los eval types actuales?

### A8. Variables numericas y mundos mixtos

Hoy la BN solo soporta variables discretas. Los papers reales tienen
variables continuas (presion, temperatura, concentracion, scores). Esto
limita el realismo de los datos y las preguntas que podemos hacer.

**Sub-preguntas:**
- [ ] Se puede extender pgmpy a variables continuas o mixtas?
- [ ] Alternativa: discretizar pero con mas granularidad (10-20 estados)?
- [ ] Que cambia en el teacher, scoring y CPD generation?
- [ ] Que eval types nuevos habilita (regresion, correlacion, etc)?

### A9. Inspiration report: racionalizacion post-hoc

El report narrativo se genera DESPUES del SRC, por un LLM diferente al
orchestrator. Eso significa que "explica" las decisiones reconstruyendo
razones, no capturando las reales. Solo el manifest tiene la intencion
real del orchestrator (y el manifest solo se usa como input del report).

**Solucion propuesta:** reemplazar emit_inspiration_manifest por un paso
donde el orchestrator escriba el report directamente durante la creacion.
El orchestrator tiene todo fresco: que leyo del seed, por que eligio cada
variable, como mapeo las preguntas, que no pudo representar.

Partes que el orchestrator puede escribir: decisiones de variables,
estructura causal, mapeo de preguntas, que se perdio. Partes que necesitan
post-hoc: verificacion contra el SRC final, evaluacion de datos generados,
limitaciones desde perspectiva de SREG developer.

- [ ] Reemplazar manifest por report escrito durante la creacion.
- [ ] Paso post-hoc liviano solo para verificacion y limitaciones.

---

## Implementacion y experimentos

Cosas que sabemos que queremos hacer o probar. Cada una referencia el
analisis que la motiva.

### I1. Nuevos eval types — motivado por A2

- [ ] Disenar `mediation_query`: "que parte del efecto de X sobre Y pasa
  por M?". Verificar si es computable desde la BN.
- [ ] Disenar `effect_modification`: "el efecto de X sobre Y cambia segun
  el valor de Z?". Verificar computabilidad.
- [ ] Disenar `subgroup_effect` o `selection_bias_assessment`.
- [ ] Disenar `inverse_design`: "que combinacion de intervenciones produce
  este resultado?" Verificable con do-calculus multi-intervencion.
  Potencialmente iterativo (proponer → feedback → refinar).
  Referencia: SciDesignBench (arxiv 2603.12724).
- [ ] Para cada tipo nuevo: definir scoring, correcta ground truth, y
  agregar al teacher.

### I2. Modos semanticos — motivado por A3

Cuatro modos, opcionales, sobre el mismo SRC (misma BN, mismas preguntas):

- **`realistic`** (actual): nombres cientificos reales, dominio reconocible.
  "maternal_algae_smoke_exposure", "hatchling_mass", "Miralune tern colonies"
- **`fictional`**: nombres inventados con estructura semantica. El solver no
  puede usar priors pero la narrativa suena a ciencia.
  "trelline_exposure", "maturation_index", "Region Veldara"
- **`abstract`**: nombres genericos sin contexto. Puro ejercicio formal.
  "X1", "X3", "Y"
- **`theory_rich`** (FUTURO): fictional + literatura inventada. Papers
  ficticios con hallazgos parciales, contradictorios o sesgados. El solver
  tiene que integrar teoria previa con datos. → Ver A4.

Implementacion:
- [ ] Disenar como transformar la capa semantica post-generacion (renombrar
  variables, reescribir narrativa, ajustar preguntas).
- [ ] Implementar modos `fictional` y `abstract` como post-proceso del SRC.
- [ ] Experimento: tomar 3 SRCs, generar las 3 versiones, correr solver en
  cada una, comparar scores.
- [ ] Medir si el solver usa priors del dominio o investiga los datos.

### I3. Mejorar fidelidad de preguntas al paper — motivado por A1, A2

- [x] Prompt reescrito: preguntas causales como primarias, infer_target
  complementario, seed-first question design.
- [x] Default task_type: causal_effect en vez de infer_target.
- [ ] Re-evaluar los 7 SRCs con prompt nuevo (v2 generados, pendiente
  revisar reports en detalle).
- [ ] Comparar preguntas v1 vs v2 para cada seed.

### I4. Fortalecer el diseno del case — motivado por A1, A5

- [ ] Unificar `scenario_title` y `case_plan.title`.
- [ ] Evolucionar el case hacia estructura investigativa: objetivo,
  hipotesis rivales, evidencia, incertidumbres.
- [ ] Agregar validacion de calidad para CasePlan.

### I5. Validar calidad multi-dominio — motivado por A6

- [ ] Actualizar QualitySuite para 9 eval types.
- [ ] Validar paper-seeded SRCs con 3-5 papers de dominios distintos.
- [ ] Construir taxonomia de failure modes.
- [ ] Avanzar en reproducibilidad.

### I6. Consolidar documentacion

- [ ] Alinear README, PROJECT, ARCHITECTURE, CURRENT_STATE, TODO sin
  solapamientos.
- [ ] Reorganizar research/ (notas, sintesis, archivo).
- [ ] Eliminar referencias stale.

### I7. Teoria inventada y literatura sintetica — motivado por A4

- [ ] Disenar como generar "papers ficticios" derivados parcialmente del
  mundo verdadero (incompletos, sesgados, contradictorios).
- [ ] Implementar como DataAsset o nuevo tipo de artefacto visible.
- [ ] Probar si el solver usa la teoria inventada para investigar.

### I8. Datasets mas realistas — motivado por A1

Hoy los datasets tienen 5% noise y 5% missingness, pero eso es ruido
estadistico, no complejidad de evidencia. Los papers reales tienen
multiples fuentes que no coinciden, proxies imperfectos, datos de
distintas epocas, variables medidas con distintos instrumentos.

- [ ] Agregar datasets con estructura temporal (antes/despues).
- [ ] Multiples fuentes con discrepancias reales.
- [ ] Variables que son proxies imperfectos de lo que realmente importa.
- [ ] Metadata de calidad por columna (instrumento, precision, fecha).

### I9. Mejorar prompt del orchestrator para eval types — motivado por A2

El orchestrator a veces elige mal entre los eval types existentes.
Necesita mejores descripciones y ejemplos de cuando usar cada uno.

- [ ] Agregar ejemplos concretos de papers para cada eval type.
- [ ] Instruir que si no hay tipo adecuado, lo diga en vez de forzar.
- [ ] Cuando se agreguen nuevos eval types, actualizar el prompt.

---

## Backlog

### Infraestructura

- [ ] Timeout real para python_exec via process boundary.
- [ ] Agregar verifiers como dependencia opcional.
- [ ] Coleccion mantenible de paper seeds.
- [ ] Unificar generate() y generate_custom() en WorldGenTool.

### Mundo formal

- [ ] Validar CPDs con checks mas fuertes.
- [ ] Motif composer y expressive range para DAGs.
- [ ] Variables continuas y mundos mixtos.

### Producto

- [ ] Actualizar demo script y notebook.
- [ ] Budget compartido entre preguntas del mismo caso.

---

## Futuro

### Horizonte siguiente del core

- [ ] MechanismSpec, mechanism library, composicion mechanism-first.
- [ ] Rival mechanisms como hipotesis competidoras.
- [ ] Approximate inference teacher para mundos grandes.
- [ ] Curriculum sobre complejidad.
- [ ] Semantic mode configurable (full/abstract/fictional).
- [ ] **Research actions rediseniadas desde cero.** Las viejas (observe X
  cuesta 2, intervene Y cuesta 3) estan muertas — eran un juego artificial.
  Las nuevas deben ser interacciones ricas con el entorno: disenar
  experimentos, pedir campanas de datos, proponer intervenciones y ver
  resultados, consultar expertos simulados. Son la interfaz del entorno
  (como step() en Gym), NO herramientas internas del solver.
  IMPORTANTE: el solver ya investiga con python_exec (analisis, subgrupos,
  sensibilidad, etc). Eso es asunto del solver, no del entorno.

### Integraciones no-core

- [ ] Agent harness mas rico para policies externas.
- [ ] Reward design extendido para training real.
- [ ] Training pipeline completo sobre SregEnv.
- [ ] Transfer experiment falsificable.

---

## Hitos completados

- [x] v0+v1: contratos base, world generation, teacher solver, orchestrator,
  semantic layer y pipeline E2E.
- [x] Superficie v2 base: DAGSpec, mundos custom, 9 eval types y rich action
  infrastructure.
- [x] Solver diagnostico con python_exec, think, submit y reportes completos.
- [x] Paper-seeded SRCs + Inspiration Report v1.
- [x] Benchmarks externos integrados y backend de inferencia unificado.
- [x] Prompt reescrito: preguntas causales primarias, infer_target
  complementario, seed-first design. Inspiration Report v2.

Detalle historico en `CHANGELOG.md`.

---

## Inbox — ideas sueltas

> Espacio libre para anotar cosas que se me ocurren. Se procesan en sesion
> y se mueven a la seccion que corresponda (analisis, implementacion, etc).

- Repasar evaluaciones y validaciones que se hicieron y quedaron sin uso
  (QualitySuite, diagnostics, baselines). → ver A6
- Teoria inventada como literatura visible (papers ficticios derivados
  parcialmente del mundo verdadero). → ver A4, I7
- Investigar Research Gym, SciGym, Kimi como referencia para tasks. → ver A5
- Preguntas vagas → entrenar plan de investigacion. → ver A5
- Critica: SREG solo data-driven? Necesita data + theory + literature. → ver A4
- SciDesignBench (arxiv 2603.12724): inverse design con simuladores.
  Nuestra BN puede hacer lo mismo. → ver I1 (inverse_design)
- DISTINCION CRITICA: research actions (FUTURO) = interacciones con el
  ENTORNO. Analisis del solver (AHORA) = python_exec, asunto del solver.
- Ejemplo real (surfactantes/petroleo): seleccion basada en teoria +
  tablas, prueba rapida de efectividad, despues 200-500 ensayos iterativos
  de estabilidad con ajustes finos. → esto es un patron de investigacion
  industrial que SREG deberia poder representar. Conecta con A5 (taxonomia
  de investigaciones) e inverse_design iterativo.
- Taxonomia de investigaciones: no tenemos claro los TIPOS de investigacion
  que existen y que dimensiones tienen. Necesitamos eso para disenar las
  research tasks. → ver A5, research/
