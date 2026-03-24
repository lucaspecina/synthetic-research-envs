# P2: Naturalizacion de preguntas — nombres semanticos y contrafactuales naturales

> **Motivacion:** La evaluacion cualitativa (2026-03-24) encontro que las preguntas
> visibles al investigador usan node_ids como codigo (`'training_load_7d'`) y
> framing de do-calculus ("setting 'recovery_quality' to 'low'"). Esto delata
> inmediatamente que el caso es sintetico. Ver hallazgos H1, H2, CF4 en
> `research/synthesis/qualitative_eval_2026_03_24.md`.

## Diagnostico

### El problema en el output actual (football)

```
Q1: "How does increasing recent 7-day training and match load affect
     late-match tactical decline?"                                    ← BIEN
Q2: "Which of these two changes would have a greater impact on
     'second_half_tactical_decline': setting 'recovery_quality' to
     'low', or setting 'training_load_7d' to 'high'?"                ← MAL
Q3: "Does the effect of 'training_load_7d' on
     'second_half_tactical_decline' depend on the level of
     'tactical_role_intensity'?"                                      ← MAL
Q4: "What fraction of the causal effect of 'training_load_7d' on
     'second_half_tactical_decline' is mediated through
     'second_half_physical_drop'?"                                    ← MAL
Q5: "What hidden factor best explains why some players remain
     resistant to late-match decline despite similar load and
     recovery profiles?"                                              ← BIEN
```

Q1 y Q5 estan bien porque el orchestrator escribio `question_text` natural y el
override funciono. Q2-Q4 tienen node_ids crudos y framing mecanico.

### Dos fuentes del problema

1. **Orchestrator (`prompts.py`)**: el prompt dice "you CAN reference variables
   since this is internal" para `question_text`. Pero `question_text` SÍ es
   visible al investigador — se renderiza en `briefing.md` via `export_briefing()`.

2. **Task generator (`scm_task_gen.py`)**: los templates auto-generados usan
   `f"'{node_id}'"` con comillas simples y framing "set X to Y". Estos son el
   fallback cuando el orchestrator's question es rechazada por entity matching.

### Pipeline de question rendering

```
orchestrator → CasePlan.questions[i].question_text
    ↓
scm_task_gen.generate_from_plan()
    ↓
    Decision: override con question_text?
      - Safe types: SI (si entities match)
      - Hints honored: SI
      - Else: usar template auto-generado
    ↓
Task.question → export_briefing() → briefing.md "Research Questions"
```

## Plan de fix — 3 piezas (diagnostico de Codex)

Codex (review 2026-03-24) identifico que son 3 piezas, no 2. Si no se actualiza
el entity matching, el sistema "pelea contra el fix" rechazando preguntas naturales
y cayendo al template feo.

### Pieza 1: Helper central de nombres semanticos

Nuevo metodo estatico en `SCMTaskGenTool`:

```python
@staticmethod
def _semantic_name(world: SCMWorld, node_id: str) -> str:
    """Nombre legible para el investigador.

    Prioridad:
    1. variable_meta[node].description (si es corta, <50 chars)
    2. node_id.replace('_', ' ')
    """
    meta = world.variable_meta.get(node_id)
    if meta and meta.description and len(meta.description) < 50:
        return meta.description
    return node_id.replace("_", " ")
```

Y un companion para matching:

```python
@staticmethod
def _semantic_aliases(world: SCMWorld, node_id: str) -> set[str]:
    """Todas las formas validas de referirse a una variable."""
    aliases = {node_id, node_id.replace("_", " ")}
    meta = world.variable_meta.get(node_id)
    if meta and meta.description:
        aliases.add(meta.description.lower())
    return {a.lower() for a in aliases}
```

### Pieza 2: Naturalizar templates de preguntas

Cambiar los 12 metodos `_*_task()` para usar `_semantic_name()` en vez de
`f"'{node_id}'"`. Ejemplos de transformacion:

| Antes | Despues |
|-------|---------|
| `"If '{intervention_node}' were set to {val}"` | `"If {semantic_name} were increased to {val}"` |
| `"setting '{node_a}' to '{label_a}'"` | `"increasing {name_a} to {label_a} levels"` |
| `"effect of '{treatment}' on '{target}'"` | `"effect of {treatment_name} on {target_name}"` |
| `"accounting for '{suggested}'"` | `"accounting for {suggested_name}"` |

Principios:
- Sin comillas simples alrededor de nombres
- Sin "set X to Y" — usar contrafactuales naturales ("increase", "shift", "change")
- Los internals (intervention dict, estimand, correct_answer) siguen con node_ids

### Pieza 3: Entity matching y consistency checks

- `_entities_match_question()`: agregar matching contra `_semantic_aliases()`
  ademas de los checks actuales (`node_id`, `node_id.replace('_', ' ')`)
- `_check_question_answer_consistency()`: misma logica para no tirar warnings
  con preguntas que usan nombres semanticos

### Pieza 4: Prompt del orchestrator

Cambiar `prompts.py`:
- Explicitar que `question_text` ES visible en `briefing.md`
- Prohibir snake_case, comillas simples, "set X to Y"
- Dar ejemplos buenos vs malos

## Riesgos identificados (Codex review)

1. **`VariableMeta.description` puede ser larga**: no usarla raw, limitar a <50 chars
2. **Entity matching demasiado estricto**: si la pregunta dice "recent workload"
   pero el nodo es `training_load_7d`, hoy falla → fix con aliases
3. **Falsos positivos en substring matching**: nombres cortos pueden matchear
   dentro de otros. Aceptable por ahora, monitorear.
4. **Inconsistencia entre `_entities_match_question` y `_check_question_answer_consistency`**:
   hoy no comparten logica. El fix los unifica via `_semantic_aliases()`.

## Orden de ejecucion

```
P2.1 Helper _semantic_name / _semantic_aliases
  ↓
P2.2 Templates ──┐
P2.3 Matching  ──┤  (pueden hacerse en paralelo)
  ↓               │
P2.4 Prompts  ←──┘
  ↓
P2.5 Tests
  ↓
P2.6 E2E con SRC real
```

## Scope explicitamente FUERA

- **P1 (H8, eval_ontology_leak)**: las preguntas siguen mapeando 1:1 a eval types.
  Eso se resuelve en I10 Fase 3, no aca.
- **P3 (H3, H5, H6)**: respuestas limpias, identificacion, provenance — requiere
  cambios en como el task generator construye respuestas, no solo texto.
- **P4 (H7, H4)**: indexing y metadata — cambios en data pipeline, no aca.

## Metricas de exito

Despues del fix, generar 3 SRCs y verificar:
1. Ninguna pregunta contiene `'snake_case'` con comillas
2. Ninguna pregunta usa "setting X to Y"
3. Un humano no deberia poder distinguir si las preguntas fueron auto-generadas
   o escritas por un investigador (por el framing — el contenido puede seguir
   siendo limitado por H8)
