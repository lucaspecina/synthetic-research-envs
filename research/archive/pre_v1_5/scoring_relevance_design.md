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

## Answer Key: el SCM como fuente de verdad RICA

Descubrimiento clave: el teacher ejecuta los specs contra el SCM para
obtener las respuestas reales. Pero la respuesta NO es una Assertion
simplificada — es el resultado completo del SCM.

### El problema original (ranking)

```
SQ: "Cuales son las causas mas importantes del sanding?"
Compiler genera: spec con assertion=rank_order (sin orden especifico)
SCM devuelve: ranking real = stress > fluid > pressure > spacing
Pero el spec no sabia el orden → FALSE
```

### Primer intento (INCORRECTO): derivar Assertion del resultado

Intentamos: ejecutar verify_atom → leer comparison_result → derivar una
Assertion que describa la realidad (positive, negative, rank_order, etc).

**Por que fallo:**
- Fuerza verdades ricas a un vocabulario de ~13 etiquetas
- `ratio=0.7` → "positive" (INCORRECTO: significa 30% menos que referencia)
- `no changepoint` → "near_zero" (INCORRECTO: puede haber efecto fuerte sin quiebre)
- Rankings de arms vs rankings de variables (el verifier rankea labels)
- Introduce arbitrariedades: distintas ramas para cada tipo de resultado
- Viola principios: "un solo metodo para todo", "no construir un juego"

### BUG downstream — fix parcial

`oi_sq_matching.py` descartaba SQ specs donde
`sq_verdict.solver_assertion_holds == False`. Con el nuevo diseno, eso
descartaba answer keys validos. **Fix aplicado:** se elimino el gate.

**Dependencia parcial que queda:** `assertion_compat()` todavia compara
la Assertion de la SQ (hipotesis del compiler) con la del claim. Es decir,
el matching ya no DESCARTA por holds=False, pero todavia USA la Assertion
del teacher como senal de compatibilidad. Esto debe migrar a comparar
claim result vs answer key rico / features derivadas del resultado SCM.

### La solucion correcta: answer key = resultado rico del SCM

```
1. Orchestrador genera SQ como texto
2. Compiler traduce a spec (arms + measurement + comparison)
3. verify_atom ejecuta contra SCM → obtiene RESULTADO COMPLETO:
   - comparison_result: {difference: -15.43, ranking: (...), value: True, ...}
   - measurements: {arm1: 42.3, arm2: 27.8, ...}
   - ground_truth: el valor resuelto
4. Se guarda el RESULTADO COMPLETO como answer key (no una Assertion)
5. La Assertion es una VISTA del answer key, no la verdad misma
```

### Que cambia

**Answer key tipo** — no es un `AssertionKind` sino una estructura rica:
- Para causal: {effect_size: -15.43, direction: negative, magnitude: large}
- Para ranking: {order: [stress, fluid, pressure, spacing], gaps: [...]}
- Para correlacion: {raw: 0.72, partial: 0.31, conditioned_on: [Z]}
- Para identifiability: {identifiable: True, valid_adjustment_sets: [...]}

**Comparacion claim vs answer key** — dos caminos posibles:
- **LLM juez** (ahora): claim_text + sq_text + answer_key_rico → relevance
- **Determinístico** (para RL): comparar claim compilada contra answer key
  usando la estructura rica, no etiquetas simplificadas

**Ventaja:** nunca se pierde informacion. El answer key siempre tiene la
verdad completa. El scoring puede ser tan fino o tan grueso como necesite.

## Score final (formula — SIN CAMBIOS de concepto)

```
claim_score = verdad(claim, SCM) x relevancia(claim, SQ) x tier_weight

donde:
  verdad     = 0 o 1 (claim compilada → verify contra SCM, binario)
  relevancia = 0..1 (LLM juez ahora, puede usar answer key como contexto)
  tier       = 1.0 (high), 0.6 (medium), 0.4 (low)
```

## Insights arquitectonicos (2026-03-31)

### verify_atom mezcla resolve + assert — separar en el futuro

`verify_atom()` hoy hace DOS cosas en una sola llamada:
1. **Resolver** la query contra el SCM (measurements, comparison_result)
2. **Evaluar** si la Assertion del caller matchea el resultado

Para el teacher, solo nos importa (1) — el resultado rico. La Assertion es
la hipotesis del compiler, no la verdad. Para el solver, nos importan ambas
— la Assertion ES la claim.

**Hoy funciona** porque `ground_sq_answer_key()` simplemente ignora
`solver_assertion_holds` y toma `verdict.detail` como answer key.

**Pero la mezcla conceptual queda en la infraestructura.** En el futuro
conviene separar explicitamente:
```
resolution = resolve(spec, world, solver)   # solo SCM query
verdict    = assert_(resolution, assertion) # evaluar claim
```

Esto haria explicita la asimetria teacher/solver y eliminaria la confusion
de que `holds=False` en teacher side "invalide" el answer key.

**No hacerlo ahora** — el workaround actual (ignorar holds en teacher) es
limpio y suficiente. La separacion es para cuando toquemos verify_atom.

### Rankings complejos: composicion, no specs monoliticos

Preguntas como "cuales variables tienen mayor ATE sobre Y?" no se resuelven
con un unico spec de 8 arms + ranking. Se resuelven por **composicion**:

```
spec_1: ATE de X1 sobre Y → answer_key = {ate: 15.3}
spec_2: ATE de X2 sobre Y → answer_key = {ate: -8.7}
spec_3: ATE de X3 sobre Y → answer_key = {ate: 22.1}
...
answer key rico agrega: ranking = [X3, X1, X2] por |ATE|
```

**Por que:** un spec atomico con N arms intenta meter demasiada semantica
en una sola unidad. El verifier termina rankeando arm labels (escenarios),
no entidades cientificas (variables). La composicion mantiene los specs
simples y deja que la agregacion del answer key produzca la respuesta rica.

**Implicacion para el compiler:** cuando el LLM ve una SQ de ranking,
deberia generar N specs (uno por variable/entidad) en lugar de intentar
un solo spec monolitico. El answer key rico del SQ (no del spec individual)
hace la agregacion.

## Proximos pasos

1. **Disenar answer key rico** — que estructura necesita cada tipo de
   comparison result para ser un answer key completo (A27)
2. Implementar LLM juez de relevancia (simple prompt, puede usar answer key)
3. Probar E2E con 7 seeds diversas
4. Medir donde falla la relevancia
5. Decidir si features determinísticas alcanzan para RL
6. Separar resolve/assert en verify_atom (cuando se toque el verifier)
7. Ranking por composicion en el compiler (cuando se toque el compiler)
