# Scoring: Verdad y Relevancia — Decisiones de Diseno

> Fecha: 2026-03-31
> Status: DECIDIDO (verdad), EN DEBATE (relevancia)
> Contexto: Debate entre Claude, Codex y Cursor sobre como evaluar claims

## El problema

El solver produce claims. El sistema necesita responder dos preguntas:

1. **Verdad:** Esta claim es cierta en este mundo?
2. **Relevancia:** Esta claim responde a lo que el brief pedia?

## Verdad — RESUELTO

Claim texto -> compile a AtomicSpec -> verify contra SCM -> TRUE/FALSE.

Determinístico. No depende de LLM en scoring. Funciona hoy.
El SCM es la fuente de verdad absoluta. Si el SCM dice FALSE, la claim
vale 0. No negociable.

## Relevancia — Las opciones

### Opcion A: Spec vs Spec (matching estructural)

- SQ se compila a AtomicSpecs
- Claim se compila a AtomicSpecs
- Matching: comparacion estructural de specs (measurement.kind, variables,
  assertion, arms)
- **Pro:** Determinístico, RL-safe, no LLM en scoring loop
- **Con:** Fragil. Dos LLMs pueden formalizar la misma pregunta de formas
  distintas. Penaliza claims correctas pero formuladas distinto. Tipos como
  ranking, descriptivo, system mapping no compilan bien.
- **Calidad estimada:** ~60-70% de claims bien evaluadas

### Opcion B: Features determinísticas (Python puro)

- Del claim compilado extraer: focus_variables, intent_type (causal,
  confounding, mediation, ranking, descriptivo), tipo de measurement,
  obs vs interventional
- De la SQ: focus_variables, intent_type, tier
- Score = overlap_variables x compatibilidad_intent x tier
- **Pro:** Determinístico, rapido, RL-safe
- **Con:** Muchos casos borde. Mediacion indirecta, formulaciones
  distintas, etc. Requiere dias de reglas.
- **Calidad estimada:** ~70% sin mucho tuning

### Opcion C: LLM juez (comparar textos)

- Inputs al LLM: claim_text + sq_text + (opcionalmente specs como pistas)
- Pregunta: "Sabiendo que la claim es cierta, responde a esta SQ?"
- Output: relevance_score (0-1)
- **Pro:** Rapido de implementar (~horas). Maneja diversidad natural.
  ~90% calidad. Funciona para todos los tipos.
- **Con:** No determinístico. Problematico para RL (reward hacking,
  costo, lentitud). Gameable.
- **Calidad estimada:** ~90%

### Opcion D: Hibrido (la que elegimos para arrancar)

- **Verdad:** Spec vs SCM (formal, determinístico) — siempre
- **Relevancia:** LLM juez para arrancar (funciona hoy)
- **Specs disponibles** como pistas para el LLM y para matching futuro
- **Migracion a RL:** Reemplazar LLM por features determinísticas o
  clasificador destilado cuando tengamos datos de que funciona

No descartamos ninguna opcion. Los specs se generan igual (para verdad
y para tener disponibles). La capa de relevancia es intercambiable.

## Decision: Opcion D (hibrido)

- **Ahora:** LLM juez para relevancia. Simple, funciona, nos deja probar
  el E2E con las 7 seeds.
- **Despues:** Cuando vayamos a RL, reemplazar por algo determinístico
  (features, clasificador, o spec matching mejorado).
- **Los specs no se tiran.** Sirven para: verdad, pistas al LLM,
  forzar concrecion en las SQs, matching futuro.

## Answer Key: el compilador ejecuta contra el SCM

Descubrimiento clave del spike: el compilador de SQs DEBE poder ejecutar
los specs contra el SCM para obtener las respuestas reales.

### El problema (ejemplo ranking)

```
SQ: "Cuales son las causas mas importantes del sanding?"
Compiler genera: spec con assertion=rank_order (sin orden especifico)
SCM devuelve: ranking real = stress > fluid > pressure > spacing
Pero el spec no sabia el orden → FALSE
```

### La solucion

El teacher tiene acceso completo al SCM. Las SQs son la agenda oculta
del teacher. El teacher SABE las respuestas. Entonces:

```
1. Orchestrador genera SQ como texto
2. Compiler traduce a spec (assertion generico o vacio)
3. verify_atom ejecuta contra SCM → obtiene respuesta real
4. Se actualiza el spec con la respuesta (answer key)
5. Ahora tenemos SQ + answer key para comparar contra claims
```

Esto aplica a todos los tipos:
- **Ranking:** el SCM dice el orden real
- **Causal:** el SCM dice si el efecto existe y su signo/magnitud
- **Confounding:** el SCM dice si la asociacion desaparece al controlar
- **Identifiability:** el SCM dice si el efecto es identificable
- **Descriptivo:** el SCM dice las correlaciones reales

El verify_atom dry-run NO es opcional — es esencial para que las SQs
tengan answer key.

## Score final (formula)

```
claim_score = verdad(spec, SCM) x relevancia(claim, SQ) x tier_weight

donde:
  verdad     = 0 o 1 (SCM dice TRUE o FALSE, binario)
  relevancia = 0..1 (LLM juez ahora, determinístico despues)
  tier       = 1.0 (high), 0.6 (medium), 0.4 (low)
```

## Proximos pasos

1. Agregar verify_atom al compile step (answer key generation)
2. Implementar LLM juez de relevancia (simple prompt)
3. Probar E2E con 7 seeds diversas
4. Medir donde falla la relevancia
5. Decidir si features determinísticas alcanzan para RL
