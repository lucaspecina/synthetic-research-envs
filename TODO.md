# SREG — TODO

> Brecha activa entre `ARCHITECTURE.md` y `CURRENT_STATE.md`.
> Statuses: `[ ]` pending | `[~]` in progress | `[x]` done | `[-]` cancelled
> Mantener este documento operativo: tareas abiertas, problemas vigentes y
> backlog seleccionado. Historia detallada -> `CHANGELOG.md`. Research abierto
> -> `research/`.

---

## En foco ahora

### 1. Hacer que los casos fuercen investigacion real

- [ ] Redisenar eval types causales para que requieran evidencia del episodio y
  no puedan resolverse mayormente desde priors del dominio.
- [ ] Revisar prompts y scoring para que las respuestas sin soporte visible sean
  penalizadas cuando corresponda.
- [ ] Re-evaluar `infer_target`, `causal_effect`, `adjustment_set`,
  `should_condition` y `compare_interventions` en un diagnostico comparativo.

Done when:

- existe un criterio claro de "data-indexed" para preguntas nuevas,
- las tasks structural-causal ya no se responden mayormente desde priors en la
  evaluacion diagnostica,
- y el diagnostico puede distinguir mejor entre investigar y responder por
  atajo.

### 2. Fortalecer el diseno del case

- [ ] Alinear la primary question con el objetivo real de investigacion del
  caso.
- [ ] Unificar `scenario_title` y `case_plan.title`.
- [ ] Evolucionar el case desde `(titulo, historia, tareas)` hacia una
  estructura mas investigativa: objetivo, hipotesis rivales, evidencia,
  incertidumbres y decisiones.
- [ ] Agregar validacion de calidad para `CasePlan`: preguntas no redundantes,
  NBO no trivial, hipotesis distinguibles y buena mezcla de preguntas por caso.

Done when:

- el framing del caso y sus preguntas se perciben alineados en inspeccion E2E,
- el orchestrator puede justificar por que esas preguntas pertenecen a ese
  caso,
- y los casos dejan de sentirse como "wrapper narrativo + tasks sueltas".

### 3. Hacer creibles las research actions

- [ ] Introducir `ActionPlan` o equivalente para que el orchestrator disene
  acciones tipadas como parte del caso.
- [ ] Reemplazar heuristicas de costos y agrupaciones del `ProblemBuilder` por
  diseno guiado por el research case.
- [ ] Validar que cada accion ayude al menos a una pregunta sin regalar la
  respuesta.
- [ ] Reintroducir uso de `research_actions` en el solver diagnostico solo
  cuando se sientan como investigacion real y no como desbloqueo artificial.

Done when:

- el solver usa research actions en evaluaciones E2E por razones
  investigativas creibles,
- acciones, costos y outputs pueden explicarse dentro del caso,
- y el budget vuelve a ser una parte util del entorno en vez de una mecanica de
  juego.

### 4. Validar y estabilizar calidad de SRCs

- [ ] Actualizar `QualitySuite` y quality checks para cubrir 9 eval types y
  casos reales, no solo el motor formal de 3 tipos.
- [ ] Validar paper-seeded SRCs con 3-5 papers de dominios distintos.
- [ ] Construir una taxonomia util de failure modes para diagnostico.
- [ ] Avanzar en reproducibilidad: generacion reproducible y dataset congelado
  para evaluacion.

Done when:

- hay un quality gate claro para aceptar o rechazar SRCs,
- existe evidencia multi-dominio de que los casos funcionan como investigacion,
- y los resultados importantes pueden reproducirse de forma controlada.

### 5. Consolidar la documentacion canonica

- [ ] Terminar de alinear `README.md`, `PROJECT.md`, `ARCHITECTURE.md`,
  `CURRENT_STATE.md` y `TODO.md` sin solapamientos.
- [ ] Reorganizar `research/` en una estructura clara para notas, sintesis y
  archivo.
- [ ] Eliminar referencias stale a documentos que dejen de ser canonicos.

Done when:

- cada documento responde una pregunta distinta y no compite con los otros,
- las fuentes de verdad del proyecto quedan explicitas,
- y los docs viejos dejan de actuar como referencia principal por accidente.

---

## Problemas abiertos

- [ ] Las preguntas causales no son suficientemente data-indexed y permiten
  respuestas desde priors del dominio.
- [ ] El solver diagnostico actual no usa `research_actions` de forma creible.
- [ ] `QualitySuite` y parte del diagnostico no cubren la superficie real del
  sistema.
- [ ] El orchestrator no controla bien la dificultad pedida.
- [ ] Algunos eval types siguen siendo triviales o poco discriminativos,
  especialmente `next_best_observation`, `hypothesis_selection` e
  `infer_latent_cause`.
- [ ] El solver se degrada en mundos mas complejos y la seleccion de variables
  sigue siendo suboptima frente al teacher.
- [ ] La reproducibilidad todavia no es suficiente para evaluacion seria y
  training.

---

## Backlog

### Cases, datos y acciones

- [ ] Verificar E2E con LLM agent que razona correctamente sobre datos ricos.
- [ ] Extender `DataAsset` con metadata util (fecha, instrumento, temporalidad,
  contradicciones entre fuentes) cuando el caso lo justifique.
- [ ] Agregar acciones de consulta o revelacion parcial de estructura cuando
  tengan sentido investigativo.
- [ ] Enriquecer la capa semantica con contexto teorico mas rico y narrativa mas
  elaborada.

### Orchestrator y case planning

- [ ] Agregar tests con combinaciones variadas de preguntas por caso.
- [ ] Hacer que el budget sea realmente compartido entre preguntas del mismo
  caso.
- [ ] Mejorar extraccion de estructura desde papers hacia `dag_construct`.
- [ ] Unificar `generate()` y `generate_custom()` en una sola API de
  `WorldGenTool`.

### Mundo formal y evaluacion

- [ ] Validar CPDs generadas automaticamente con checks mas fuertes.
- [ ] Construir motif composer y analisis de expressive range para DAGs.
- [ ] Mantener actualizada la superficie de eval types de este horizonte.

### Producto y DX

- [ ] Actualizar demo script y notebook.
- [ ] Implementar timeout real para `python_exec` via process boundary.
- [ ] Agregar `verifiers` como dependencia opcional en `pyproject.toml`.
- [ ] Crear una coleccion mantenible de paper seeds.

---

## Futuro

### Horizonte siguiente del core

- [ ] `MechanismSpec`, mechanism library y composicion mechanism-first.
- [ ] Rival mechanisms como hipotesis competidoras de primer nivel.
- [ ] Variables continuas y mundos mixtos.
- [ ] Synthetic document artifacts: papers, reports, notes y otros artefactos
  visibles.
- [ ] Approximate inference teacher para mundos mas grandes.
- [ ] Curriculum sobre complejidad del mundo y del caso.
- [ ] Semantic mode configurable (`full`, `abstract`, `fictional`) y
  experimentos de comparacion.

### Integraciones no-core

- [ ] Agent harness mas rico para policies fuera de SREG core.
- [ ] Reward design extendido para training real.
- [ ] Training pipeline completo sobre `SregEnv`.
- [ ] Transfer experiment falsificable con controles negativos y quality gate de
  dataset.

---

## Hitos completados

- [x] v0+v1: contratos base, world generation, teacher solver, orchestrator,
  semantic layer y pipeline E2E.
- [x] Superficie v2 base: `DAGSpec`, mundos custom, 9 eval types y rich action
  infrastructure.
- [x] Solver diagnostico con `python_exec`, `think`, `submit` y reportes
  completos por caso.
- [x] Paper-seeded SRCs + Inspiration Report.
- [x] Benchmarks externos integrados y backend de inferencia unificado para el
  solver.

Detalle historico en `CHANGELOG.md`.
