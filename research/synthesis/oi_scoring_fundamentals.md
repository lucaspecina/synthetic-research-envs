# Open Investigation: fundamentos del scoring

> **Status:** Framework mental consensuado. Guia decisiones de diseno del scoring.
> **Fecha:** 2026-03-27
> **Participantes:** Usuario, Claude, Codex, ChatGPT (sesion paralela)

## Pregunta precisa vs pregunta vaga

### Cuando la pregunta es precisa

Suele haber una verdad principal.

Ejemplos:
- "Cual es el ATE de Treatment sobre Recovery?"
- "Hay mediacion o no?"
- "Esta politica mejora el outcome o no?"

Ahi si: una respuesta principal. El modo examen (guided) funciona bien.

### Cuando la pregunta es vaga

Suele haber varias respuestas validas. Pero NO varias "verdades
incompatibles". Mas bien, varias formas legitimas de hacer avanzar
la investigacion:

- describir mejor
- separar subtipos
- proponer una explicacion causal
- reconocer que no se puede identificar
- disenar la siguiente medicion
- construir una capacidad util
- reformular la pregunta

**Pregunta vaga != multiples verdades arbitrarias.**
**Pregunta vaga = multiples outputs valiosos posibles.**

Este matiz es central. Open Investigation existe porque las preguntas de
investigacion real son vagas, y el valor esta en que el solver descubra
outputs valiosos — no en que adivine los outputs que nosotros esperabamos.

## Consecuencias para el scoring

### El salience map no puede ser el arbitro

El SCM tiene infinitas verdades (infinitas asociaciones, contrastes,
estratificaciones). El salience map es una proyeccion finita — enumera
algunas verdades que un algoritmo sabe buscar. Si esa proyeccion determina
el score, convertiste investigacion abierta en examen: "adivina lo que
yo ya se".

### Tres dimensiones separadas

| Dimension | Que evalua | Como | Subjetivo? |
|-----------|-----------|------|------------|
| **Verdad** | El claim es correcto? | Compilar → ejecutar contra SCM | NO — exacto |
| **Relevancia** | Importa para el brief? | Grafo causal + intent del caso | PARCIALMENTE |
| **Cobertura** | Encontro lo canonico? | Comparar con salience map | NO — pero es piso, no techo |

### Correctness = verificacion directa contra el SCM

No depende del salience map. Cada claim del solver se compila a una query
ejecutable y se verifica contra el SCM. Si es verdad, es verdad — este o
no en la lista precomputada.

### Relevancia != estar en el salience map

Un claim verdadero puede ser irrelevante ("Age tiene efecto -0.01 en
Recovery" — verdad pero trivial para el brief). Un claim fuera del salience
map puede ser muy relevante ("Severity confunde Treatment-Recovery" — no
estaba en la lista pero es central para la investigacion).

La relevancia depende de `claim + brief + objetivo`, no solo del claim.
Se evalua por:

- **Relevancia estructural** (grafo): el claim toca variables en el camino
  causal del target? Computable, sin LLM.
- **Relevancia decisional** (brief): el claim cambia que concluiria un
  investigador sobre la pregunta? Requiere interpretar el brief.

Para que la relevancia sea evaluable, el brief necesita un "intent
contract": target principal, decision central, tipos de contribucion
validos. Sin eso, la relevancia esta subespecificada.

### Salience map = piso de cobertura, no techo del score

Uso correcto:
- "Al menos deberia haber encontrado parte de lo canonico"
- Diagnosticar misses sistematicos
- Benchmark de cobertura minima (bonus 15-20%)

Uso incorrecto:
- Decidir si un claim verdadero vale
- Colapsar creatividad a familias pre-enumeradas
- Actuar como techo de lo que se puede descubrir

### Novel claims necesitan upside, no solo no-penalty

Si un claim es verdadero Y relevante Y no esta en el salience map, eso
deberia ser un BONUS — el solver descubrio algo que el sistema no
anticipaba. "Sin reward pero sin penalty" sigue siendo castigo por costo
de oportunidad (el solver gasto un slot de claim en algo que no puntua).

### Anti-shotgun sin answer key cerrado

El shotgun se controla con estructura del objetivo, no con un hidden map:
- Presupuesto estricto de claims (K <= 5)
- Penalty fuerte por false claims
- Marginal gain: claims redundantes valen ~0
- Score set-level por precision y densidad informativa

## Formula tentativa

```
claim_utility = truth_score(SCM) * relevance(brief, grafo) * marginal_gain(vs otros claims)
episode_score = mean(claim_utilities) + salience_floor_bonus - false_discovery_penalty
```

Donde:
- `truth_score`: exacto, verificado contra SCM (0 o valor continuo)
- `relevance`: computable del grafo + intent del brief (0 a 1)
- `marginal_gain`: cuanto agrega vs claims ya submitidos (0 a 1)
- `salience_floor_bonus`: bonus minoritario por cubrir lo canonico (15-20%)
- `false_discovery_penalty`: penaliza claims falsos fuerte

## Propuesta concreta: sub-preguntas pesadas

### El problema de relevancia

Dada una pregunta vaga, no todo claim verdadero vale lo mismo. La pregunta
"por que el treatment tuvo resultados mixtos?" hace que confounding y
heterogeneidad sean MAS importantes que mecanismo o tail risk. Si la
pregunta fuera "como funciona el treatment?", las importancias se invierten.

La importancia viene de la pregunta, no solo del mundo.

### La solucion mas simple

Cuando el orchestrator genera el caso, ademas del brief genera
**sub-preguntas concretas con pesos** derivadas de la pregunta vaga:

```
brief: "Por que el treatment tuvo resultados mixtos?"

sub-preguntas:
  - "Hay confounding que explique la variabilidad?" peso: 0.3 (ALTA)
  - "El efecto varia por subgrupo?"                 peso: 0.3 (ALTA)
  - "Treatment tiene efecto en Recovery?"            peso: 0.2 (MEDIA)
  - "Por que mecanismo opera?"                       peso: 0.1 (MEDIA)
  - "Hay riesgo en extremos?"                        peso: 0.1 (BAJA)
```

El solver no ve esto. El scoring si. Un claim que toca sub-preguntas de
peso alto vale mas que uno que toca sub-preguntas perifericas.

### Matching claim → sub-pregunta

El compiler traduce el claim a un spec verificable (como hoy). Despues un
matcher (puede ser LLM, no es judge — es comprension de lenguaje) mapea
el spec a las sub-preguntas del caso. No le pedis que juzgue verdad ni
relevancia — solo que diga "este claim habla de lo mismo que esta
sub-pregunta".

### Claims fuera de la lista

Si el solver encuentra algo verdadero que no matchea ninguna sub-pregunta:
- Se verifica contra el SCM igual (verdad = exacta)
- Recibe credito base por relevancia estructural (toca el camino causal
  del target?)
- No se penaliza, pero no recibe el bonus de peso alto

### Criticas conocidas (de Codex, ChatGPT, Claude paralelo)

1. **"Es un question key, sigue siendo examen disfrazado"** (Codex).
   Parcialmente cierto — las sub-preguntas pesadas imponen un framing.
   Mitigacion: el solver no las ve, el matching es flexible, y claims
   novel reciben credito real.

2. **"Las sub-preguntas no son independientes"** (Codex, ChatGPT). Si hay
   heterogeneidad fuerte con ATE~0, "hay efecto?" es mala pregunta.
   Para Alpha: aceptable. Para v2: modelar dependencia entre slots.

3. **"Quien genera los pesos?"** (Claude paralelo). Para Alpha:
   semi-manual o el orchestrator los propone. Despues: automatizar
   basado en patrones observados.

4. **"Confounding, measurement error, no-identificabilidad no entran
   en el grafo causal"** (ChatGPT). Parcialmente cierto. Para Alpha:
   solo cubrir lo que el SCM puede verificar. Futuro: expandir.

### Nota importante

Esta propuesta NO necesita implementarse completa para Alpha. Lo minimo
funcional es:
1. Verificar claims directamente contra SCM (ya existe)
2. Que claims verdaderos reciban score de correctness aunque no matcheen
   una familia del salience map (cambio chico)
3. El salience map como piso de coverage (ya existe, solo cambiar el rol)

Las sub-preguntas pesadas son la SIGUIENTE iteracion, despues de tener
evidencia empirica de 5-10 pilotos reales.

## Plan concreto (Alpha)

1. [x] Documentar principios de scoring (este doc)
2. [ ] Arreglar bugs del piloto (partial_correlation, confounding en
   compiler/verifier)
3. [ ] Correr 3 mundos curados con pipeline actual y LLM compiler
4. [ ] Leer resultados cualitativamente — identificar problemas reales
5. [ ] Decidir mecanismo de relevancia basado en evidencia empirica
6. [ ] Implementar scoring v2

**Regla:** no disenar scoring sin datos de pilotos reales. Cada iteracion
de scoring debe estar motivada por un problema observado, no teorico.

## Que NO esta resuelto todavia

- Como computar relevancia para claims que tocan el grafo pero de formas
  inesperadas (ej: "la relacion es no identificable dado estos datos")
- Si el LLM judge/matcher para relevancia es necesario o si el grafo +
  sub-preguntas pesadas alcanzan para Alpha
- Como ponderar los componentes (pesos tentativos, hay que calibrar)
- Como manejar claims epistemicos ("no se puede saber X con estos datos")
  que son valiosos pero no verificables en el sentido clasico
- Como generar sub-preguntas pesadas automaticamente (para Alpha: manual
  o semi-manual)

## Origen

Sesion 2026-03-27. El usuario cuestiono el rol del salience map como
determinante del score. Cuatro AIs (Claude, Codex, ChatGPT, Claude
paralelo) participaron en el debate. Esta sintesis consolida los insights
y documenta la propuesta concreta de sub-preguntas pesadas como mecanismo
de relevancia.
