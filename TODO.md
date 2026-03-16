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

### A5. Que tipo de research tasks pedir?

Inspirarse en Research Gym, Kimi, RL long-horizon. Las tasks actuales son
preguntas cerradas. Los papers piden cosas mas complejas: planificar,
disenar experimentos, integrar fuentes.

**Sub-preguntas:**
- [ ] Que hacen Research Gym, SciGym, DiscoveryBench como tasks?
- [ ] Subtasks? Planes de investigacion? Preguntas vagas?
- [ ] Que rol tiene el LLM en disenar las tasks vs elegir de un menu?

**Referencia:** NOTES.md seccion "Que tipo de preguntas / tasks".

### A6. Evaluaciones y validaciones sin uso

Se construyeron QualitySuite, DiagnosticRunner, baselines, pero parte
quedo desactualizada o sin uso real. Hay que repasar que sirve y que no.

- [ ] QualitySuite: solo 3/9 eval types. Actualizar o reemplazar?
- [ ] DiagnosticRunner: funciona pero los resultados no se usaron para
  iterar. Como cerrar el loop?
- [ ] Baselines: son los correctos para los eval types actuales?

### A7. Inspiration report: racionalizacion post-hoc

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
