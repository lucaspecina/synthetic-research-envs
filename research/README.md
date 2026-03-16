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
