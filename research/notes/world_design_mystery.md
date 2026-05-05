# World design — Vertical 2: Mystery & Discovery game design

> Reporte de investigación generado por agente Explore (2026-05-05). Parte del
> survey en `research/synthesis/world_design_techniques_survey.md`.
>
> Foco: cómo diseñadores humanos (videojuegos, TTRPGs, board games, escape rooms)
> han resuelto el problema de "construir investigaciones que el jugador resuelve",
> con principios transferibles a SREG.

---

## 1. Por qué los videojuegos / TTRPGs son maestros en esto

Durante décadas, diseñadores de videojuegos, TTRPGs y juegos de mesa han iterado con jugadores humanos en el loop, refinando heurísticas para que la experiencia de "descubrir la verdad oculta a partir de observaciones" sea gratificante. A diferencia de los benchmarks científicos que optimizan para velocidad o precisión, estos diseñadores optimizan para el *viaje epistémico*: cómo mantener al jugador curioso, evitando frustración paralizante, asegurando que las pistas se cruzan de forma no trivial, permitiendo múltiples vías hacia la comprensión sin romper la lógica interna del mundo.

SREG enfrenta un problema isomorfo: un LLM Investigator debe deducir un SCM/ODE oculto a partir de un dataset. El desafío no es solo que la verdad sea recuperable — es que el *proceso de descubrimiento* sea estructurado de modo que el investigador pueda aprender de fallos, convergir desde múltiples ángulos, y nunca quede permanentemente atrapado.

## 2. Casos de estudio por medio

### Videojuegos: deducción pura

#### 2.1 Return of the Obra Dinn (Lucas Pope, 2018)

**Estructura del mundo**: Un barco fantasma con 60 pasajeros y marineros, cada uno con un rol, una nacionalidad, una causa de muerte, y una posición en el espacio-tiempo. La verdad se "encierra" en la observación visual: el jugador es testigo pasivo de tableaus congelados que muestran momentos de muerte, conversaciones, y eventos.

**Estructura de pistas**: Tres tipos de información: identidad (nombre/rol), causa de muerte, y culpabilidad. Las pistas se cruzan de forma modular: el uniforme de una persona aparece en un cadáver, su voz coincide con un testimonio grabado, el arma en una escena apunta a un sospechoso específico. Lucas Pope utilizó spreadsheets internos para garantizar que cada conclusión fuera alcanzable lógicamente desde múltiples ángulos.

**Loop de investigación**: observa → forma hipótesis → intenta llenar el logbook (matriz 60×3) → el sistema solo acepta tres identificaciones completas y correctas antes de dar feedback. Esto fuerza validación cruzada.

**Principio extraíble**: *redundancia visual sin redundancia textual*. La misma información aparece codificada en múltiples canales (uniforme, voz, ubicación, contexto), pero nunca se dice explícitamente.

**Referencia**: [Lucas Pope on Obra Dinn design (Game Developer)](https://www.gamedeveloper.com/design/for-lucas-pope-i-return-of-the-obra-dinn-i-was-a-bunch-of-appealing-design-problems).

#### 2.2 Outer Wilds (Mobius Digital, 2019)

**Estructura del mundo**: Un sistema solar en colapso (loop de 20 minutos). El progreso no es mediante items sino mediante *conocimiento*: descubrir que el Núcleo Blanco está desestabilizado, que una civilización antigua lo ignoró, que hay un instrumento capaz de predecir su comportamiento.

**Estructura de pistas**: Las pistas no son objetos: son patrones observables. La torre del Acantilado Ígneo revela la física de los agujeros de gusano. Los textos antiguos de Nomai se descifran gradualmente. El conocimiento adquirido en una región *unlockea* la capacidad de comprender (no acceder) otra región.

**Loop de investigación**: viaja → observa → forma hipótesis sobre la física del mundo → prueba en otro loop → refina. No hay guía. La UI es apenas un mapa. El conocimiento acumulado es el avatar del progreso.

**Principio extraíble**: "Knowledgevania" — las observaciones son la moneda. Cada hecho nuevo abre literalmente nuevas direcciones de exploración. No hay bloqueos mecánicos; hay bloqueos epistémicos.

**Referencia**: [Mobius Digital interview on Outer Wilds design](https://www.pointnthink.fr/en/loan-verneau-creative-lead-at-mobius-digital-on-outer-wilds/).

#### 2.3 The Case of the Golden Idol (Color Gray Games, 2022)

**Estructura del mundo**: 40 años de historia siglo XVIII, 9 escenas modular-independientes, cada una con un crimen. Los personajes tienen motivaciones ocultas, secretos compartidos que reaparecen en casos posteriores.

**Estructura de pistas**: Sistema de "Thinking Mode": el jugador recopila palabras (nombres, acciones, objetos) y luego los arrastra a oraciones incompletas (Mad Libs): "_X_ mató a _Y_ porque _Z_". El sistema solo acepta la combinación correcta. Las pistas vienen de diálogos sobreoídos, objetos examinados, documentos.

**Principio extraíble**: *modularidad narrativa con validación fuerte*. Cada escena es independiente, pero las palabras y personajes se reutilizan, creando una ilusión de universo conectado sin fuerza bruta de diseño.

**Referencia**: [Game Developer on Golden Idol design](https://www.gamedeveloper.com/design/case-of-the-golden-idol).

#### 2.4 Tunic (Andrew Shouldice, 2022)

**Estructura del mundo**: Un mundo de fantasía retro, descubierto a través de un manual del juego que está fragmentado, manchado, parcialmente en idioma extranjero (diegético y no descifrable sin contexto).

**Estructura de pistas**: Las páginas del manual están distribuidas en el mundo. Cada página contiene instrucciones, diagramas, o historias de trasfondo. Las páginas están dañadas de formas que enseñan: una página quemada muestra solo la silueta de un símbolo, obligando al jugador a inferir.

**Principio extraíble**: *meta-mystery del sistema mismo*. El acto de aprender las reglas del juego es indistinguible de descubrir la verdad del mundo.

**Referencia**: [80.lv on Tunic manual design](https://80.lv/articles/tunic-s-developer-on-creating-the-in-game-manual-full-of-mysteries).

#### 2.5 Heaven's Vault (inkle, 2019)

**Estructura del mundo**: Arqueología espacial. Un lenguaje muerto (Ancient) con jeroglíficos pictóricos. La verdad oculta: una civilización antigua y su fin. Se descubre mediante la traducción progresiva de inscripciones.

**Estructura de pistas**: Más de 1,000 palabras en Ancient se pueden encontrar. Los símbolos tienen conexiones semánticas: si aprendes que "flujo" = agua, puedes inferir qué significa un símbolo de "corriente". Los contextos narrativos dan pistas. El juego *nunca* dice si estás en lo correcto.

**Principio extraíble**: *validación semántica sin retroalimentación explícita*. La coherencia narrativa es el único validador.

**Referencia**: [Game Developer on Heaven's Vault language design](https://www.gamedeveloper.com/design/how-inkle-developed-its-own-ancient-language-for-i-heaven-s-vault-i-).

#### 2.6 Disco Elysium (ZA/UM, 2019)

**Estructura del mundo**: Un mundo de rolero en crisis política. Un detective amnésico con 24 habilidades que literalmente discuten con él. El crimen es un misterio, pero el *verdadero misterio es el detective mismo*.

**Estructura de pistas**: Las habilidades generan chistes, monólogos internos, y perspectivas. El jugador puede investigar de forma no-lineal. Los diálogos con NPCs tienen skill checks: puedes fallar en extraer información, pero hay siempre otra ruta.

**Principio extraíble**: *la investigación es roleplay, no puzzle*. El verdadero descubrimiento es autorreflexivo.

#### 2.7 Paradise Killer (Kaizen Game Works, 2020)

**Estructura del mundo**: Una isla paradisíaca con un concilio asesinado. Mundo explorable libremente. Cada personaje tiene un horario, una historia, conexiones ocultas. La "verdad" del crimen es indeterminada hasta el juicio final.

**Estructura de pistas**: El jugador puede acusar a *cualquiera*. La calidad de la acusación depende de si puede construir una cadena lógica coherente con la evidencia. Diferentes acusados requieren diferentes conjuntos de evidencia. El sistema recompensa trabajo riguroso y penaliza especulación vacía.

**Principio extraíble**: *libertad investigativa con validación posterior*. No hay puntos de bloqueo; hay calibración de dificultad.

**Referencia**: [Game Developer on Paradise Killer mystery design](https://www.gamedeveloper.com/design/inside-the-fantastic-murder-mystery-design-of-i-paradise-killer-i-).

### TTRPG: diseño flexible para misterios humanos

#### 2.8 El Gumshoe System (Robin D. Laws, 2007)

No es un caso de estudio en el sentido de un juego específico, sino un *protocolo de diseño* de misterios que ha revolucionado TTRPGs.

**Estructura de pistas**: Distingue entre *core clues* (información crítica que el jugador DEBE descubrir para progreso) y *additional clues* (color, consecuencias). Las core clues se entregan *automáticamente* si el jugador tiene la habilidad relevante. **No hay dado; no hay fracaso**.

**Filosofía**: "El juego de investigación no es sobre encontrar pistas; es sobre *interpretar* las pistas encontradas." El Gumshoe resuelve el problema de D&D-style donde un detective fallaba su tirada de Percepción y el juego se atascaba.

**Principio extraíble**: *clues are not the puzzle; interpretation is*. El diseñador no gatea los clues; los hace inevitables y calibra la dificultad en la inferencia.

**Referencia**: [Pelgrane Press on GUMSHOE](https://pelgranepress.com/2018/02/14/gumshoe/).

#### 2.9 Three-Clue Rule + Node-Based Scenario Design (Justin Alexander)

**Estructura**: Los misterios se diseñan como redes de nodos. Cada nodo es un lugar, evento, o información. Las conexiones son causalidad o correlación.

**Three Clue Rule**: "Los PCs probablemente pierdan la primera pista, ignoren la segunda, e interpreten mal la tercera." Para cualquier conclusión importante, *siempre hay al menos tres rutas de pistas que convergen en una conclusión*. El diseño asume *fracaso cognitivo del jugador* como condición de base y diseña redundancia en consecuencia.

**Inversion**: si cualquier conjunto de tres pistas en el grafo lleva a *alguna* conclusión, el diseñador tiene libertad para distribuir pistas sin miedo a bloqueos.

**Principio extraíble**: *redundancia en la topología del grafo*. No es "tres copias de la misma pista"; es "tres caminos distintos a la misma conclusión".

**Referencias**:
- [The Alexandrian — Three Clue Rule](https://thealexandrian.net/wordpress/1118/roleplaying-games/three-clue-rule)
- [The Alexandrian — Node-Based Scenario Design](https://thealexandrian.net/wordpress/7985/roleplaying-games/node-based-scenario-design-part-3-inverting-the-three-clue-rule)

#### 2.10 Brindlewood Bay (Jason Cordova, Magpie Games)

**Estructura**: Variante PbtA donde los misterios se diseñan *sin solución predeterminada*. El GM genera pistas proceduralmente. Los jugadores investigan. Cuando acusan, el GM retrocede y decide qué pistas apoyan esa acusación.

**Filosofía de "la verdad se decide cuando..."**: La verdad del misterio no existe hasta que los jugadores *la crean* mediante su acusación. Esto evita completamente el problema de "los jugadores no preguntaron la pregunta clave."

**Principio extraíble**: *post-hoc coherence*. El mundo es suficientemente indeterminado que múltiples soluciones son válidas. El diseño valida la creatividad del jugador en lugar de castigarla.

**Referencia**: [The Alexandrian — Brindlewood Bay review](https://thealexandrian.net/wordpress/47226/roleplaying-games/review-brindlewood-bay).

### Juegos de mesa y escape rooms

#### 2.11 Sherlock Holmes: Consulting Detective (1981–presente)

**Estructura**: Un mapa de Londres. Un directorio de 300+ locaciones. El GM tiene libros que describen qué pasa en cada locación. El jugador elige dónde ir.

**Diseño de pistas**: Las pistas son multi-canal. La dirección postal de una persona está en el directorio. Sus conexiones aparecen en recortes de periódicos. Sus motivos emergen de conversaciones. El juego recompensa eficiencia: si resuelves visitando N locaciones, y Sherlock Holmes visitó M (M > N), has ganado.

**Principio extraíble**: *libertad de exploración + validación posterior*. El mundo existe independientemente del orden en que lo explores.

## 3. Cross-cutting principles

### 3.1 The Three Clue Rule (Justin Alexander)

Para cualquier conclusión crítica, incluir **mínimo 3 pistas independientes** que la sostengan.

**Por qué importa**:
- Asume que los investigadores fallarán, ignorarán o malinterpretarán.
- Cada pista extra no es redundancia perezosa; es un grado de libertad investigativa.
- El diseñador se libera de la paranoia de "¿y si el jugador no encuentra esto?"

**Para SREG**: cada GoldQuestion debe ser respondible vía **AL MENOS DOS** rutas distintas de evidencia en el dataset. Si solo un camino en el grafo causal lleva a una conclusión, y el LLM no explora ese camino, está stuck forever.

### 3.2 Solvability through redundancy

El mundo debe *sobre-determinar* la respuesta, no sub-determinarla.

**Manifestaciones**:
- *Redundancia semántica*: la misma información codificada en diferentes formatos (visual, textual, contextual).
- *Redundancia topológica*: múltiples caminos independientes a la misma conclusión.
- *Redundancia causal*: si A causa B, y A causa C, el investigador puede inferir A observando B O C.

**Ejemplo (Obra Dinn)**: la identidad de un personaje se revela por: uniforme + acento + ubicación en una escena + rol mencionado en un documento. Cualquier subconjunto de 2+ suficientemente específicos es suficiente.

**Para SREG**: diseñar SCMs donde cada parámetro estructural aparece en múltiples contextos observacionales. Si θ solo afecta una variable observada, el LLM no puede triangular. Si θ afecta 3+ variables de forma distinta, puede.

### 3.3 The discovery loop

**Observa → hipótesis → verifica → refina.**

Cada ciclo comprime el espacio de soluciones posibles. El juego está bien diseñado si:
- Cada ciclo es ejecutable en ~2-5 minutos de tiempo narrativo.
- El jugador nunca está "totalmente perdido" (siempre hay *algo* que observar).
- Las hipótesis refutadas son informativas, no frustrantes.

### 3.4 Gating de dificultad sin bloqueo absoluto

TTRPGs vs. videojuegos difieren aquí:

**TTRPGs (Gumshoe, Node-Based)**: no hay fracaso en acceso a pistas. La dificultad está en la *interpretación*.

**Videojuegos (Obra Dinn, Outer Wilds)**: el bloqueo es *epistémico*, no mecánico. Outer Wilds no te deja ir a X, pero solo porque no *entiendes* cómo hacerlo todavía.

**Para SREG**: *nunca* bloquear al LLM esperando una conclusión específica. En su lugar, gatar la *comprensión de qué preguntas hacer*. El dataset debe ser siempre consultable.

### 3.5 Manejo de "el jugador no preguntó la pregunta clave"

**Problema D&D**: el detective falla una tirada de Percepción e ignora la pista crítica.

**Solución Gumshoe**: la pista es automática si buscas. El jugador no puede fallar.

**Solución Brindlewood Bay**: no hay pregunta "clave". Múltiples soluciones coexisten.

**Solución Node-Based**: la pista existe en múltiples nodos. Incluso si el jugador no visita el nodo principal, encuentra la información en otro lado.

**Para SREG**: no asumir que el LLM formulará una pregunta específica. El dataset debe ser tal que exploración menos estructurada siga siendo informativamente progresiva.

### 3.6 Separación de pistas críticas de red herrings

**Pista crítica**: parte de la cadena causal verdadera. Puede ser sutil o ambigua, pero es *necesaria* para una conclusión.

**Red herring**: correlación falsa. Parece relevante pero no afecta la cadena causal.

**Diseño efectivo**:
- Las pistas críticas aparecen múltiples veces (redundancia).
- Los red herrings aparecen una o dos veces y pueden ser descartados lógicamente.
- El contraste enseña al jugador la diferencia.

**Para SREG**: incluir confounders en el dataset deliberadamente. El LLM debe aprender a discriminar entre correlación accidental y causalidad.

## 4. Top 5 principios transferibles a SREG

### 1. Redundancia esencial (Three Clue Rule)
Cada conclusión crítica debe ser respondible por ≥2 caminos independientes en el dataset. Para cada nodo oculto θ, contar cuántas rutas distintas de observaciones pueden triangularlo. **Mínimo 2**.

### 2. Los clues no son el puzzle; la interpretación lo es (Gumshoe)
No diseñar el mundo tal que una única observación "resuelve" todo. En su lugar, diseñar tal que el LLM debe *sintetizar* múltiples observaciones para llegar a una conclusión. Para cada conclusión C: complejidad inferencial ≥ 2 pasos lógicos.

### 3. Diseñar para el discovery loop iterativo
El dataset debe permitir al LLM formular preguntas progresivamente más específicas:
1. Preguntas amplias sobre estructura.
2. Preguntas sobre dependencias específicas.
3. Preguntas de validación.
4. Preguntas de refinamiento.

Cada nivel debe ser respondible en base a observaciones disponibles en niveles anteriores.

### 4. Multi-channel pistas: misma información, distintos formatos
Una observación clave debe ser deducible desde múltiples ángulos: correlación estadística, contexto causal, magnitud anómala, discontinuidad temporal.

**Ejemplo**: si el SCM es `dx/dt = θ₁·x + θ₂·y`, entonces θ₁ debe ser estimable desde:
- la pendiente de x sobre intervalos de y bajo,
- el cambio de x cuando y = 0,
- la estadística de residuales cuando se asume modelo incorrecto sin θ₁.

### 5. Validación semántica, no mera consistencia
El LLM debe poder detectar cuando una hipótesis de mecanismo es falsa no solo por mal fit, sino porque genera predicciones *absurdas* o *contradictorias*.

## 5. Casos límite y patrones de fracaso

### Cuándo el jugador está perdido

- **Información insuficiente**: el jugador ha visitado todos los nodos accesibles y sigue sin coherencia narrativa. Solución (Gumshoe): la pista crítica debe ser automática. Solución (Outer Wilds): rediseñar qué es accesible.
- **Demasiada libertad**: espacio de hipótesis tan vasto que el jugador no sabe qué preguntar. Solución (Node-based): estructura sin rigidez. Solución (Brindlewood Bay): cualquier conclusión es válida si es internamente consistente.
- **Pista crítica olvidada**: solución (Outer Wilds): logbook que el juego mantiene por ti. Solución (Obra Dinn): la matriz de personajes ES el logbook.

### Cuándo la mecánica es demasiado opaca

- **The Witness**: enseña reglas mediante ejemplos. No hay texto. Los puzzles MISMOS son la pedagogía.
- **Heaven's Vault**: contexto narrativo da hipótesis de traducción. Las hipótesis incorrectas resultan en absurdo semántico que señala el error.
- **Tunic**: el manual ES el mundo. Aprender y explorar son lo mismo.

## 6. Conclusión

El diseño de misterios para humanos resuelve décadas de iteración sobre los problemas que SREG enfrenta:

1. *Redundancia estructural* asegura que ningún camino único es crítico.
2. *Loops iterativos* permiten al investigador converger desde múltiples ángulos.
3. *Validación semántica* reemplaza validación mecánica — el mundo revela inconsistencias.
4. *Libertad investigativa con estructura implícita* permite exploración sin parálisis.
5. *Separación clara entre pistas críticas y ruido* enseña al investigador qué observar.

Para SREG: diseñar datasets donde la causalidad verdadera está sobre-determinada, observable desde múltiples ángulos, y donde la exploración menos óptima sigue siendo informativa.

## 7. Fuentes clave

- [The Alexandrian — Three Clue Rule](https://thealexandrian.net/wordpress/1118/roleplaying-games/three-clue-rule)
- [The Alexandrian — Node-Based Scenario Design](https://thealexandrian.net/wordpress/7985/roleplaying-games/node-based-scenario-design-part-3-inverting-the-three-clue-rule)
- [Pelgrane Press — GUMSHOE](https://pelgranepress.com/2018/02/14/gumshoe/)
- [Game Developer — Lucas Pope on Obra Dinn](https://www.gamedeveloper.com/design/for-lucas-pope-i-return-of-the-obra-dinn-i-was-a-bunch-of-appealing-design-problems)
- [Mobius Digital — Outer Wilds interview](https://www.pointnthink.fr/en/loan-verneau-creative-lead-at-mobius-digital-on-outer-wilds/)
- [Game Developer — Case of the Golden Idol](https://www.gamedeveloper.com/design/case-of-the-golden-idol)
- [80.lv — Tunic Manual Design](https://80.lv/articles/tunic-s-developer-on-creating-the-in-game-manual-full-of-mysteries)
- [Game Developer — Heaven's Vault language design](https://www.gamedeveloper.com/design/how-inkle-developed-its-own-ancient-language-for-i-heaven-s-vault-i-)
- [Game Developer — Paradise Killer mystery design](https://www.gamedeveloper.com/design/inside-the-fantastic-murder-mystery-design-of-i-paradise-killer-i-)
- [The Alexandrian — Brindlewood Bay review](https://thealexandrian.net/wordpress/47226/roleplaying-games/review-brindlewood-bay)
- [Mark Brown — What Makes a Great Detective Game (GMTK)](https://gmtk.substack.com/p/what-makes-a-great-detective-game)
- [DigiTales — Detective Game Design Problems](https://digitales.games/blog/detective-game-design-problems)
