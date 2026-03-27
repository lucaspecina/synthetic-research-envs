# AUTORESEARCH: Open Investigation Design
# Fecha inicio: 2026-03-26
# Branch: autoresearch-open-investigation
# Modelo: Claude Opus 4.6 (1M context) + Codex gpt-5.4 (MCP)
# Codex thread: 019d2d62-d371-7072-8b4c-319eab3fe156 (anterior expirado: 019d2ae2)

> **ESTE ARCHIVO ES EL "SAVE FILE" DEL AUTORESEARCH.**
> Despues de cada compact, leer este archivo para recuperar contexto.
> Actualizarlo despues de cada milestone significativo.

---

## Principios inmutables — LEER SIEMPRE

### 0. LA PREGUNTA — el filtro de todo
> **Por que esto todavia no es una investigacion real? Que le falta?**

Cada decision de diseno, cada linea de codigo, cada debate con Codex pasa
por este filtro. Si algo no acerca OI a investigacion real, no vale la pena.

### 1. El solver INVESTIGA, no responde preguntas
OI existe porque "responder preguntas pre-hechas" no es investigar. Si el
diseno final se siente como un examen disfrazado de investigacion libre,
fallamos. El solver debe decidir QUE investigar, COMO, y QUE concluir.

### 2. Verificacion exacta contra el SCM — sin excepciones
El SCM es la verdad. No hay LLM judges en el nucleo de scoring. El compiler
TRADUCE, no JUZGA. Si algo no puede verificarse contra el SCM, no entra al
reward core. Esto NO es negociable.

### 3. La subjetividad esta encapsulada, no eliminada
La compilacion tiene subjetividad — lo admitimos honestamente. Pero esta
ACOTADA: claim cards la reducen, preview loop la audita, abstention la
controla. "Exact SCM-grounded verification" != "100% mecanico end-to-end".

### 4. No construir juguetes
Si el resultado final solo puede verificar 10 tipos de cosas, siempre sera
un juguete. La gramatica composable existe para que las verificaciones sean
ABIERTAS — combinar piezas, no enumerar casos. Cada decision debe preguntarse:
"Esto limita artificialmente lo que se puede descubrir?"

### 5. Un cientifico real haria esto?
Litmus test de PROJECT.md. Aplica a claim cards, scoring, gramatica, todo.
Si la respuesta es no, redisenar.

### 6. Debate ANTES de codigo
Investigar -> pensar -> debatir con Codex -> disenar -> implementar ->
cuestionar -> redisenar. NO saltar a implementar. El codigo viene despues
de que el diseno sobreviva al escrutinio.

### 7. Verificabilidad > realismo > elegancia
La jerarquia de PROJECT.md. Si algo mejora el realismo pero rompe la
verificacion, no sirve. Si algo es elegante pero artificial, tampoco.

### 8. Documentar es parte del trabajo, no overhead
Cada conclusion, cada debate, cada decision queda documentada donde
corresponde. Sin docs actualizados, el autoresearch pierde continuidad.

---

## Workflow del autoresearch

```
INVESTIGAR (que problema resolver?)
  -> PENSAR (cuales son las opciones?)
    -> DEBATIR CON CODEX (que se nos escapa?)
      -> DISENAR (decision con evidencia)
        -> IMPLEMENTAR (codigo + tests)
          -> CUESTIONAR (esto pasa LA PREGUNTA?)
            -> REDISENAR si no pasa
              -> DOCUMENTAR siempre
```

### Adaptacion para modo autonomo (usuario ausente)

- Paso 3 del commit workflow (presentar al usuario): **Codex actua como
  reviewer critico.** Si Codex aprueba, commitear. Si Codex tiene objeciones
  serias, documentar la discrepancia y NO commitear hasta resolverla.
- **NUNCA FRENAR.** Siempre hay algo que investigar, debatir, disenar o
  implementar. Si un camino se bloquea, ir al siguiente.
- Despues de cada commit: revisar TODO, elegir siguiente paso, seguir.
- Seguir el workflow normal de CLAUDE.md para todo lo demas (tests, docs,
  promotion rules, etc.)

---

## Build order de Open Investigation Alpha (A15)

1. [x] Formalizar gramatica composable como DSL ejecutable
2. [ ] Prototype salience map (enumerar verdades de un SCM real)
3. [x] Claim card contract (Pydantic models con slots minimos)
4. [ ] Compiler benchmark offline (200+ claims, >90% precision)
5. [x] Verifier scoring sin compiler (claims formales perfectos)
6. [ ] Piloto scaffolded (solver real + compiler + scoring)

**IMPORTANTE:** Pasos 1-3 son los mas concretos. Pasos 4-6 requieren LLM.
Pero el FOCO PRINCIPAL es investigacion y diseno — no saltar a codigo sin
que el diseno haya sobrevivido debate.

---

## Referencia rapida — donde esta todo

| Que buscar | Donde |
|------------|-------|
| Vision OI | `research/synthesis/open_investigation_vision.md` |
| Working doc (30 casos, debate) | `research/notes/open_investigation_case_analysis.md` |
| Todo list OI | `TODO.md` seccion A15 |
| Principios del proyecto | `PROJECT.md` |
| Arquitectura | `ARCHITECTURE.md` |
| Rubrica cualitativa | `research/synthesis/qualitative_eval_rubric.md` |
| Cobertura cientifica | `research/synthesis/sreg_scientific_coverage.md` |
| SCM migration | `research/synthesis/scm_migration_rationale.md` |

---

## Log de progreso (actualizar despues de cada milestone)

### Sesion 1 — 2026-03-26 noche
- **Inicio:** branch creada, principios documentados, crons configurados
- **Se corto:** la sesion se interrumpio antes de avanzar

### Sesion 2 — 2026-03-27
- **Continuacion:** retomado por usuario, crons reconfigurados
- **Fase 1 COMPLETA:** 5 preocupaciones criticas investigadas (sesgo
  interventional, Goodhart simplicidad, truth map explota, taxonomia
  es fundamental, compiler sin evidencia)
- **Fase 2 COMPLETA:** debate con Codex. 3 cirugias aceptadas. Spec
  corregida entregada con QueryContext, 15 macros, salience map, scoring.
  Thread Codex activo: 019d2d62-d371-7072-8b4c-319eab3fe156
- **Fase 3 COMPLETA:** DSL implementado como Pydantic models (42 tests)
- **Fase 4 EN CURSO:** verifier engine implementado (15 tests, 57 total)
  - verify_atom: arms -> measure -> compare -> assert, all 6 QueryKinds
  - score_claim_against_family: specificity bonus + overclaim penalty
  - score_episode: correctness(60%) + coverage(30%) + efficiency(10%)
  - Pendiente: salience map generator, macros, docs update
- **Docs actualizados:** case_analysis.md, session file

