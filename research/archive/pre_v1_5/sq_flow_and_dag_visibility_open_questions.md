# Flujo de SQs, visibilidad del DAG, y dudas sobre compilación — briefing

**Estado:** abierto. Esto NO es una propuesta de cambios. Es un mapa de preguntas
que abrimos durante el trabajo de Suite 2 (eval-suite worktree) y que conviene
que otra sesión retome con la cabeza fresca.

**Alcance crítico:** estamos construyendo la **suite de evaluación** (I-007, Suite 2
Translation). NO deberíamos implementar fixes al compiler ni rediseñar el flujo de
SQs desde acá. Lo que sigue son **insumos para TODO/issues**, no trabajo a ejecutar
en esta rama.

---

## 1. Contexto: qué estábamos haciendo

- Rama: `eval-suite` worktree, trabajando en Suite 2 (Translation).
- Tarea original: correr el compiler LLM contra los 55 gold targets de Suite 2 y
  sacar un baseline de cuánto falla.
- Scripts producidos (todos sin commitear todavía):
  - `scripts/analyze_compiler_results.py` — categoriza por tipo de falla.
  - `scripts/dump_compiler_output.py` — volcado detallado compiler vs gold.
  - `scripts/prompt_diagnostic.py` — test A/B/C para separar recipe gap de
    recognition gap de capability gap.
  - `tests/eval/suite2_translation/conftest.py` — pytest hooks para `--run-llm`.
- Outputs: `research/synthesis/compiler_baseline_failures.json` (21 verdict
  failures con specs completos).

## 2. Números duros del baseline

Sobre los 55 gold targets, ejecutando el compiler LLM real:

| Categoría | N | Lectura |
|---|---|---|
| Full pass (3/3 etapas) | 6 | 11% |
| Adjust-swap only (verdict correcto, structural mismatch benigno) | 11 | 20% |
| Real structural error (estructura rota, verdict por casualidad) | 11 | 20% |
| Verdict wrong (compiler llegó al resultado equivocado) | 22 | 40% |
| Stage 1 fail (decisión compile/abstain equivocada) | 5 | 9% |

**Effective pass rate real: 31%. Real error rate: 69%.**

Esto no es "el eval está midiendo mal". El eval está midiendo algo real: el compiler
actual de claims es débil.

## 3. El diagnóstico A/B/C

Para separar causa del fallo, corrimos `scripts/prompt_diagnostic.py` sobre 3 casos
representativos (mediación, confounding, heterogeneidad) con 3 condiciones:

- **A) Baseline** — prompt actual.
- **B) + Exemplar** — agregamos worked example abstracto del patrón en el system prompt.
- **C) + Hint solo** — le decimos "esto es un claim de mediación" sin receta.

Resultados:

| Caso | A) Baseline | B) + Exemplar | C) + Hint |
|---|---|---|---|
| Mediación (T→M→Y) | OK por razón equivocada (3 specs de asociación) | WRONG (receta bien, assert mal) | WRONG |
| Confounding (severity) | WRONG (partial_correlation) | **✅ OK** (observe vs intervene + contrast_diff) | WRONG (arms mal armados) |
| Heterogeneidad | timeout | WRONG (copió esqueleto sin condition_on) | WRONG |

**Lectura:**

1. **Confounding es recipe gap puro.** El LLM reconoce el pattern pero NO sabe que
   requiere comparar observe vs intervene. Exemplar lo arregla.
2. **Mediación baseline "pasa" por coincidencia** — las 3 asociaciones individuales
   tienen signo positivo en este mundo. El razonamiento es falso pero el verdict
   sale bien. Esto es peor que fallar: es correlación con la verdad por accidente.
3. **Heterogeneidad** — incluso con exemplar, el LLM no aplicó `condition_on`. Copió
   la forma sin internalizar la semántica del subgrouping. Puede ser capability
   limit, o que el exemplar actual no alcanza.

**Conclusión operativa (provisional):** el bottleneck es recipe knowledge, no
capability. Prompt engineering con exemplars abstractos mejora los casos más
frecuentes. DAG access a Flow A no resolvería esto (y rompería el principio
evolutivo — ver §5).

## 4. La pregunta que abrimos: ¿quién ve el DAG en cada paso?

Este fue el hilo que más cosas destapó. Hay **tres actores distintos** que el
usuario y yo estuvimos mezclando sin querer, y la diferencia importa:

### Actor 1: Orchestrator LLM (genera el caso y las SQs)
- Archivo: `src/sreg/orchestrator/orchestrator.py` + `prompts.py`
- Secuencia dentro de la sesión LLM: `scm_construct` (define variables+edges) →
  `apply_semantics` → `design_case` (acá escribe `sub_questions`) → `build_problem`.
- **¿Ve el DAG?** Sí, pero de manera indirecta: **él mismo lo construyó** unos turnos
  antes. El DAG está en su contexto de conversación.
- **¿El prompt le fuerza a chequear coherencia SQ↔DAG?** No. Confía en que el LLM
  mantenga consistencia entre lo que construyó y lo que pregunta.

### Actor 2: SQ compiler — Flow B (texto SQ → AtomicSpec)
- Archivo: `src/sreg/tools/oi_sq_compiler.py::compile_sq_to_specs`
- Llamada LLM **separada**, una por SQ. Contexto: texto de la SQ + variables con
  stats (nombre, mean, std, range). **NO recibe el DAG en el prompt.**
- Post-parse, el código downstream (verifier en `oi_verifier.py`) sí usa el DAG
  para cosas estructurales: `_find_backdoor_set` auto-computa cuando
  `arm.adjust_set` está vacío, marca `adjust_invalid` si no hay set válido, etc.
- Invariante de diseño: Flow B debe **derivar las decisiones estructurales del SCM
  deterministically**, no dejar que el LLM adivine. Razón: acá se está fabricando
  ground truth, y un LLM que adivina mal produce verdad silenciosamente rota.
- Bug histórico relacionado: Task #45 (P06 G.1 ground-sanity) — el LLM de Flow B
  proponía `adjust_set` en arms, y algunos no eran backdoor sets válidos. Fix
  propuesto: strippar `adjust_set` post-parse y dejar que el verifier lo compute.

### Actor 3: Claim compiler — Flow A (claim del solver → AtomicSpec)
- Archivo: `src/sreg/tools/oi_compiler.py::lower_intent` + el path grammar-direct
  en `oi_extraction.py::compile_claim_direct`.
- **NO recibe el DAG ni en el prompt ni en el código downstream.**
- Invariante de diseño: Flow A debe estar **ciego al SCM**. Razón: si el claim
  compiler "arreglara" silenciosamente un claim causalmente equivocado del solver,
  el solver no pagaría el costo de pensar mal. Eso rompe la presión evolutiva que
  es la base del sistema.
- Comportamiento correcto ante un claim malo: validar referencias a variables,
  abstenerse si es incompilable, nunca autorepair.

### Donde yo (Claude) me había equivocado
En la conversación con el usuario dije varias veces que "el compiler Flow B ve el
DAG en el prompt del LLM". Eso es **falso**. Ningún LLM recibe el DAG en su
prompt. La diferencia Flow A vs Flow B está en lo que hace el código **después**
del LLM: Flow B valida/corrige contra el DAG, Flow A no toca nada.

La memoria `project_flow_a_vs_flow_b.md` ya lo dice correctamente. El error fue
mío al resumir.

## 5. El punto que destapó el usuario — ¿deberíamos repensar todo este flujo?

El usuario fue quien preguntó: **"las SQ deberían definirse mirando el DAG, no?"**

La respuesta honesta es: **hoy el orchestrator LLM ve el DAG porque él lo construyó**,
pero **el prompt no le fuerza a chequear coherencia**. Esto abre preguntas serias que
no resolvimos:

### Dudas abiertas sobre Actor 1 (orchestrator / SQ generation)

- **D1.** Si el orchestrator LLM puede escribir SQs inconsistentes con el DAG que
  él mismo construyó (por drift o descuido), ¿eso ya pasó en casos observados?
  Nunca verificamos sistemáticamente. Hace falta un audit sobre SQs históricas.
- **D2.** ¿Debería haber un paso de **validación estructural explícita**
  post-generación de SQs? Por ejemplo: si la SQ dice "X media T→Y", chequear
  deterministicamente en el DAG que X esté en algún camino T→Y. Si no, rechazar o
  forzar a regenerar.
- **D3.** ¿Esa validación va en el orchestrator (mismo loop), en el SQ compiler
  (Flow B), o en una etapa nueva? Hoy hay algo tangencial en `oi_subquestions.py::validate_sub_questions`
  y `grounding` pero no queda claro si cubre esto.

### Dudas abiertas sobre Actor 2 (SQ compiler / Flow B)

- **D4.** ¿El SQ compiler (el LLM) debería recibir el DAG en el prompt? Argumentos:
  - Pro: traducir "X media T→Y" a 4 arms con mediator fijado es más fácil si el
    compiler sabe cuál es el mediator según el DAG.
  - Contra: abre puerta a que el compiler "arregle" una SQ mal escrita en vez de
    abstenerse. Pero — y esto es crítico — Flow B **fabrica ground truth, no evalúa
    al solver**. La presión evolutiva no aplica acá. Así que el riesgo es conceptual
    (queremos separación limpia LLM vs determinismo), no evolutivo.
- **D5.** ¿La política actual ("LLM sin DAG + código con DAG") está dando
  problemas medibles, o es teórica? Task #45 es evidencia de que sí: 3/5
  reroutes P06 G.1 fallaron por adjust_sets inválidos. Hay más casos similares
  escondidos?

### Dudas abiertas sobre Actor 3 (claim compiler / Flow A)

- **D6.** El argumento del usuario fue muy filoso: **"si el claim compiler viera el
  DAG, no tiene por qué corregir el claim — podría compararlo con el DAG y detectar
  que está mal"**. Son dos operaciones separables en teoría:
  - (A) usar DAG para **componer** el spec correcto para el claim tal como fue escrito;
  - (B) usar DAG para **corregir silenciosamente** claims mal escritos.
- **D7.** Codex opinó: en teoría separables, en la práctica NO safely separables en
  la arquitectura actual de un LLM call único (`compile_claim_direct` hace
  interpretación + composición + validación en un paso). Para separarlos haría
  falta un pipeline de dos pasos: paso 1 extracción text-only, paso 2 composición
  con DAG-access limitado a "dados estos roles declarados, arma el spec".
- **D8.** Incluso si la arquitectura fuera de dos pasos, **¿cuál es la ganancia
  esperada?** El diagnóstico A/B/C sugiere que el bottleneck es recipe knowledge,
  no structural knowledge. DAG access no enseña que confounding = observe vs
  intervene. Un exemplar sí. Entonces: abrir DAG access a Flow A tiene costo
  (complejidad + riesgo evolutivo) y ganancia incierta. **Aparente veredicto:
  mantener Flow A ciego, arreglar vía prompt.** Pero esto merece ser confirmado
  con un segundo experimento.

## 6. CURRENT_STATE.md está desactualizado respecto a esto

Lo que CURRENT_STATE.md **sí dice**:
- Sección "Flujo punta a punta" (línea 222+): orchestrator genera caso y SQs (vago).
- Sección "Cómo una claim termina convertida en verificación formal" (línea 329+):
  explica Flow A.
- Sección "Flow B: adjust_set derivado del SCM" (línea 862+): presente solo como
  changelog puntual del 2026-04-09, no como invariante arquitectónico.

Lo que CURRENT_STATE.md **NO dice con claridad**:
- Que el orchestrator LLM **tiene el DAG en su contexto** al escribir SQs (porque
  lo construyó turnos antes), aunque no hay chequeo de coherencia.
- Que los **compiladores de texto→spec** (tanto claims como SQs) están **ambos
  DAG-blind en el prompt del LLM**.
- La regla Flow A ≠ Flow B como **invariante de diseño** con razón (presión
  evolutiva vs protección del ground truth). Está en `PROJECT.md` invariante 8
  y en memoria, pero un lector nuevo de CURRENT_STATE no llega a eso.
- Cómo se relacionan los **tres actores** (orchestrator / SQ compiler / claim
  compiler) — qué ve cada uno, en qué paso, y por qué.

## 7. La tensión de alcance (importante para la próxima sesión)

Este análisis apareció como efecto secundario de Suite 2. Suite 2 mide compilación
de claims; el baseline sacó 31% pass y destapó todo lo de arriba.

**Suite 2 NO debería arreglar esto.** El rol de la suite de evaluación es
**medir**, no resolver. Si el compiler está roto, Suite 2 lo expone; eso es éxito
de la suite, no pretexto para refactor.

Entonces la próxima sesión NO debería:
- Tocar `oi_extraction.py` ni el prompt de Flow A.
- Refactorear el flujo de SQs.
- Cambiar la visibilidad del DAG.
- Implementar validación estructural de SQs.

Lo que sí debería hacer (en orden sugerido):

1. **Cerrar Suite 2 con el baseline actual.** Documentar los 31% effective pass
   como el número que Suite 2 produce hoy, con el compiler tal como está.
2. **Convertir los hallazgos de este doc en issues GitHub** — uno por cada duda
   (D1-D8) o agrupadas por actor. Marcar con el label correcto (research / design-question).
3. **Actualizar CURRENT_STATE.md** — sección nueva "Los tres actores y qué ve
   cada uno" + referencia al invariante Flow A vs Flow B. Esto es doc, no
   implementación, así que es safe hacerlo desde acá si el usuario aprueba.
4. **Commit del trabajo de diagnóstico** — los scripts de análisis + el JSON de
   baseline + este doc. Sin fix del compiler.

## 8. Scripts / archivos relevantes (no commiteados)

```
scripts/analyze_compiler_results.py
scripts/dump_compiler_output.py
scripts/prompt_diagnostic.py
tests/eval/suite2_translation/conftest.py           # pytest hooks for --run-llm
tests/eval/suite2_translation/test_compiler_llm.py  # hooks removed (now in conftest)
research/synthesis/compiler_baseline_failures.json  # 21 verdict failures dump
research/notes/sq_flow_and_dag_visibility_open_questions.md  # this doc
```

## 9. Referencias para retomar

- `project_flow_a_vs_flow_b.md` (memoria) — invariante Flow A vs Flow B, bien explicado.
- `PROJECT.md` invariante 8 — misma regla en la doc canónica.
- `src/sreg/orchestrator/prompts.py:805` — schema de `sub_questions` en `design_case`.
- `src/sreg/orchestrator/orchestrator.py:592` — `_compile_oi_subquestions` (Flow B).
- `src/sreg/tools/oi_sq_compiler.py` — compilador de SQs, GRAMMAR_REF y exemplars.
- `src/sreg/tools/oi_extraction.py::compile_claim_direct` (~línea 443) — grammar-direct
  claim compiler, system prompt con GRAMMAR_REF + 2 worked examples solo.
- `src/sreg/tools/oi_compiler.py::lower_intent` — path alternativo con ClaimIntent IR
  y lowering determinístico; tiene recetas correctas para patrones pero hoy está
  bypasseado en favor de grammar-direct.
- `src/sreg/tools/oi_verifier.py::_find_backdoor_set` — donde el código downstream
  de Flow B deriva structural choices del DAG.

## 10. Pregunta madre, sin resolver

> ¿El problema real es que el compiler es débil (recipe gap, arreglable con prompt),
> o que el flujo de SQs y claims está mal diseñado en términos de quién ve qué
> (arquitectónico, requiere rediseño)?

El diagnóstico A/B/C apunta a lo primero. La pregunta del usuario sobre DAG
visibility apunta a lo segundo. **No son incompatibles** — puede ser que ambos
sean ciertos y que arreglarlos sea trabajo independiente. Pero conviene no
resolverlos en el mismo commit ni en el mismo debate.
