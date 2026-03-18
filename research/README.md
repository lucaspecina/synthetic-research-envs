# research/ — Analisis, hallazgos y sintesis del proyecto

> Este directorio contiene el trabajo de investigacion que alimenta las
> decisiones del proyecto. No es canonico — las decisiones viven en
> `PROJECT.md` y `ARCHITECTURE.md`. Research las informa.

## Estructura

### notes/
Material crudo o semi-crudo: debates, exploraciones, analisis largos,
hallazgos empiricos, working docs. No es canonico.

Pregunta que responde: **"Que estamos explorando o analizando?"**

### synthesis/
Conclusiones consolidadas con evidencia. Resumenes de lo que aprendimos
sobre un tema, listos para informar decisiones.

Pregunta que responde: **"Que concluimos hasta ahora?"**

Documentos de sintesis activos:

- `synthesis/research_case_design.md`
- `synthesis/real_papers_patterns.md`
- `synthesis/eval_types_analysis.md`
- `synthesis/eval_strategy.md`
- `synthesis/benchmark_analysis.md`
- `synthesis/sreg_scientific_coverage.md`

### archive/
Documentos viejos, superseded o referencias heredadas. Read-only.
Se guardan por si hacen falta, no como referencia activa.

## Regla de promocion

1. Idea nueva, debate, exploracion → `notes/`
2. Se investiga y consolida → `synthesis/`
3. Si se vuelve decision del proyecto → se promueve a `PROJECT.md` o
   `ARCHITECTURE.md`
4. Si implica trabajo pendiente → `TODO.md`
5. Si se implementa → `CURRENT_STATE.md` + `CHANGELOG.md`

El archivo de research queda como registro historico — no se borra,
pero deja de ser la fuente de verdad para esa decision.

## Nota sobre docs heredados

Algunos archivos en `notes/` siguen siendo megadocs heredados o notas de
sesion. Se conservan como insumo, pero la referencia activa deberia ir
desplazandose hacia `synthesis/`.

## Lineas de investigacion activas

### Research case design
- **Pregunta:** como diseniar SRCs que se sientan como investigacion real sin
  perder evaluabilidad fuerte.
- **Empezar por:** `synthesis/research_case_design.md`
- **Notas de apoyo:** `notes/world_design_legacy.md`,
  `notes/sreg_v2_design_findings.md`

### Patrones de papers reales
- **Pregunta:** que rasgos aparecen de forma consistente en investigaciones
  reales y que implican para SREG.
- **Empezar por:** `synthesis/real_papers_patterns.md`
- **Notas de apoyo:** `notes/real_investigations_analysis.md`

### Eval types y taxonomia cientifica
- **Pregunta:** que tipos de preguntas fuerzan investigacion real y cuales se
  pueden resolver por shortcut, prior o estructura generica.
- **Empezar por:** `synthesis/eval_types_analysis.md`
- **Notas de apoyo:** `notes/scientific_taxonomy.md`,
  `notes/scientific_taxonomy_deep_research.md` (deep research: como se hace
  ciencia hoy, taxonomy explicita/implicita, curriculum RL propuesto),
  `synthesis/scientific_research_taxonomy.md` (framework completo de
  clasificacion con objectives, axes, workflows, scoring, ejemplos),
  `notes/solver_trajectory_findings.md`,
  `notes/sreg_v2_design_findings.md`

### Estrategia de evaluacion
- **Pregunta:** como evaluar SREG sin reducirlo a un benchmark disfrazado.
- **Empezar por:** `synthesis/eval_strategy.md`
- **Notas de apoyo:** `notes/eval_design_notes.md`

### Benchmarks externos
- **Pregunta:** con que benchmarks conviene medir alineacion y transferencia
  fuera de SREG.
- **Empezar por:** `synthesis/benchmark_analysis.md`
- **Notas de apoyo:** `notes/benchmark_results.md`

### Modos semanticos (realistic vs fictional vs abstract)
- **Pregunta:** que modo semantico fuerza mas investigacion genuina y minimiza
  contaminacion por priors de pretraining.
- **Empezar por:** `notes/semantic_modes_experiment_2026_03_17.md`
- **Conecta con:** A3 y I2 en `TODO.md`
- **Status:** dos experimentos (Vaca Muerta + Football). Ver notas para
  hallazgos consolidados.

### Cobertura cientifica de SREG
- **Pregunta:** que tipos de ciencia puede representar SREG y cuales no.
- **Empezar por:** `synthesis/sreg_scientific_coverage.md`
- **Framework de referencia:** `synthesis/scientific_research_taxonomy.md`
- **Conecta con:** A2, A4, A5, A8 en `TODO.md`

### Por que SREG todavia no es investigacion real (debate)
- **Pregunta:** que brechas fundamentales separan a SREG de la investigacion real,
  mas alla de las conocidas (variables continuas, teoria inventada).
- **Empezar por:** `notes/why_not_real_research_debate.md`
- **Participantes:** Claude, Codex (gpt-5.2), usuario
- **Hallazgos clave:** el solver no sabe que es una BN, pero los templates de
  preguntas filtran el framework (do-operation, backdoor paths). Fix aplicado:
  preguntas naturalizadas.
- **Conecta con:** A1, A3 en `TODO.md`

### Variables continuas — Linear Gaussian BN
- **Pregunta:** se puede migrar de CPD tables discretas a Gaussian para tener
  variables continuas, escalar con padres, y mantener reward exacto?
- **Empezar por:** `notes/gaussian_bn_prototype_findings.md`
- **Hallazgo:** pgmpy soporta modelo + sampling pero NO inferencia continua.
  La inferencia es analitica trivial (algebra lineal). do-calculus y KL son
  closed-form. Prototipo de 3 nodos funciona end-to-end.
- **Conecta con:** A8 en `TODO.md`
