# SREG — Vision del Proyecto
## Synthetic Research Environment Generator

> **Este documento es la estrella polar del proyecto.** Define que es SREG,
> para que existe, que deberia lograr y que principios no pueden romperse.
> No describe implementacion, estado actual ni backlog. Para eso existen
> `ARCHITECTURE.md`, `CURRENT_STATE.md` y `TODO.md`.

---

## Mision

SREG genera **entornos sinteticos de investigacion** con **verdad formal
verificable**, diseniados para que un solver solo pueda rendir bien si
**investiga bien**.

En una frase:

**SREG genera investigaciones sinteticas con reward signals exactos.**

```text
SREG genera:    entorno (SRC) + reward signal
Otros proveen:  policy + framework de RL + loop de entrenamiento
```

No es un benchmark estatico. Es un generador de casos nuevos, donde cada seed
puede producir un entorno distinto y evaluable con rigor.

**Criterio de exito**: una policy entrenada con entornos SREG demuestra mejor
razonamiento cientifico en benchmarks externos que la misma policy sin entrenar.

---

## Que quiere lograr

El objetivo de SREG no es solo producir casos interesantes ni preguntas bien
formadas.

El objetivo es construir entornos donde la estrategia ganadora sea investigar de
una manera parecida a como investiga un cientifico real.

Eso implica que, para resolver bien un caso, el solver deberia tener que:

- interpretar evidencia parcial,
- integrar datos con contexto y material teorico,
- **generar** hipotesis propias (no solo elegir entre opciones dadas) y
  compararlas como rivales genuinas,
- inventar el analisis correcto para la pregunta — disenar procedimientos,
  crear variables derivadas, estratificar por subgrupos, no elegir de un menu,
- decidir que medir, que analizar o que experimento conviene hacer,
- razonar bajo restricciones,
- y responder con fundamento en la evidencia del caso, no en memoria o priors.

### El caso define las reglas del juego

Cada SRC es un mundo con sus propias reglas. Es el **caso** el que define que
puede hacer el solver y bajo que condiciones: que instrumentos hay disponibles,
que tipo de experimentos se pueden proponer, que restricciones de presupuesto o
etica aplican, que fuentes de informacion existen, con que colaboradores puede
interactuar. SREG no impone una mecanica fija — el caso la diseña.

### El potencial es muy amplio

La vision de SREG no se limita a "datos tabulares + preguntas". En su maxima
expresion, un SRC podria simular muchos aspectos de una investigacion real:

- **Material teorico sintetico**: papers ficticios, hallazgos previos, teorias
  rivales — el solver tiene que hacer deep research en literatura inventada
  para descubrir pistas o descartar hipotesis.
- **Laboratorios y equipamiento simulado**: el caso define que maquinas o
  instrumentos hay disponibles, sus capacidades y limitaciones. "Tenes acceso
  a un espectrofotometro pero no a un microscopio electronico."
- **Diseno experimental**: el solver no solo elige que medir — propone
  experimentos completos dentro de reglas del caso (formulaciones, replicas,
  controles, condiciones).
- **Colaboradores simulados**: un "colega cientifico" (simulado) con quien el
  solver puede discutir hipotesis, pedir opiniones, o consultar expertise
  especifico del dominio.
- **Restricciones operativas realistas**: presupuesto limitado, tiempo,
  disponibilidad de muestras, limitaciones eticas, acceso parcial a datos.
- **Multiples fuentes contradictorias**: datos de distintas campanas que no
  coinciden, reportes con conclusiones opuestas, evidencia ambigua.
- **Ciclo iterativo**: los resultados de un experimento informan el siguiente.
  El solver gestiona una investigacion completa, no responde preguntas sueltas.

Todo esto es potencial — no todo esta implementado ni tiene que implementarse
a la vez. Pero la arquitectura debe permitirlo sin techo artificial.

La vara conceptual es esta:

> **Si el solver no tuvo que investigar como un cientifico real para llegar a
> su respuesta, el entorno fallo aunque el score final sea alto.**

---

## Que NO es SREG

- **No entrena policies.** Genera entornos y computa rewards; otros sistemas
  traen la policy y el framework de RL.
- **No es un benchmark fijo.** Cada caso debe poder ser nuevo.
- **No prescribe como razonar.** Da el entorno, las restricciones y las
  herramientas; la policy decide como proceder.
- **No depende de jueces humanos como nucleo de evaluacion.** La referencia
  central debe ser formal y verificable.
- **No busca replicar papers reales.** Los papers pueden inspirar casos, pero
  SREG debe construir mundos nuevos que controla completamente.

---

## Scope actual y horizontes futuros

### Roadmap del producto: v0 → v1 → v2 → v3

SREG evoluciona por **versiones de producto**. Cada version es un paradigma
de investigacion distinto, no una iteracion menor. Esta seccion fija el
vocabulario canonico:

| Version | Paradigma | Estado |
|---|---|---|
| **SREG v0** | Bayes Net + preguntas especificas fijas | Eliminado (2026-03-29). Historico. |
| **SREG v1** | Open Investigation sobre SCM: brief libre, sub-questions ocultas, claims en lenguaje natural, traduccion/compilacion a AtomicSpec, verificacion exacta contra el SCM, LLM juez para relevancia | **En cierre activo.** Es el foco de hoy. |
| **SREG v2** | Sherlock-type: research actions con budget, capas de revelacion, teoria sintetica, nuevos task types (time-series, anomalias, optimizacion) | Futuro. Ver horizontes abajo. |
| **SREG v3** | Sistemas complejos: mundos dinamicos, cellular automata, biologia real | Futuro lejano. |

Las dos subsecciones siguientes detallan que cubre v1 ("Lo que SREG evalua
HOY") y que corresponde a v2 y v3 ("Lo que queda FUERA del scope actual").

Los criterios de cierre de v1 fueron cumplidos (2026-04-09, tag `sreg-v1`).
Ver `docs/archive/todo_v1_history.md` para el historico. El detalle del
pipeline end-to-end vive en `CURRENT_STATE.md`.

> **Nota terminologica.** "SREG v1" refiere al **producto**. Dentro de
> SREG v1 existen sub-pipelines internos con nombres propios ("SQ v1
> pattern-based", "SQ v2 specs-based", "Suite v1"), que NO son versiones
> del producto — son evoluciones internas del compiler y del matcher.
> Ver `CURRENT_STATE.md` seccion "Sutileza terminologica".

### Lo que SREG evalua HOY

**Ciencia que produce conocimiento.** El solver investiga un mundo,
descubre relaciones, identifica mecanismos, reporta hallazgos. El
sistema verifica si esos hallazgos son verdaderos, relevantes y cubren
lo pedido. El output del solver es **claims sobre el mundo** -- no
artefactos ejecutables.

Esto incluye una diversidad amplia de investigacion:
- causal (efectos, mediacion, confounding, interacciones)
- descriptiva (perfiles, distribucion, segmentacion)
- epistemologica (identificabilidad, robustez, sensibilidad al ajuste)
- metodologica (comparacion de estimadores, sesgo de seleccion)
- predictiva como conocimiento ("que predice Y y cuanto")
- system mapping (estructura causal, ranking de drivers)

Todo esto es verificable contra el SCM con la gramatica composable
existente (AtomicSpec).

### Lo que queda FUERA del scope actual -- horizontes futuros

Estas son extensiones valiosas que la arquitectura debe permitir, pero
que no se implementan ni se evaluan todavia.

**1. Ciencia que produce capacidad / artefactos evaluables**

Investigacion donde el solver entrega un artefacto (modelo predictivo,
ranking, policy, diseno) y el sistema lo evalua con metricas de
performance (AUC, RMSE, reward acumulado, etc.) en vez de verificar
claims sobre el mundo.

Ejemplos: maximizar AUC en holdout, proponer la policy optima bajo
constraints, calibracion de probabilidades.

Requiere: validator programs mas generales que AtomicSpec, capaces de
evaluar artefactos del solver contra datos ocultos (horizonte A24).

**2. De data analysis flat a investigacion secuencial (Sherlock-type)**

Este es el salto mas importante. Hoy SREG es flat: el solver recibe todo
(brief + datos + tools), corre analisis, y submittea. Aunque le pongas 15
turnos y budget finito, si el caso se resuelve con "cargo el CSV, corro 3
regresiones, submitteo", sigue siendo flat.

Lo que hace que una investigacion real sea long-horizon no es que tenga
muchos datos. Es que **la informacion esta en capas, y cada capa revela
que hay que hacer en la siguiente**. No podes planificar todo de entrada
porque no sabes lo que vas a encontrar.

**El solver empieza con poco.** No recibe todos los datasets. Recibe un
brief, un dataset inicial (observacional, ruidoso, parcial), y un catalogo
de acciones disponibles: "pedir datos de calidad de agua", "pedir datos de
temperatura por estacion", "pedir un experimento intervencional". Cada
accion cuesta budget y devuelve datos nuevos del SCM.

**Las acciones son queries contra el SCM.** Ya existe la infraestructura.
El SCM sabe samplear, intervenir, condicionar. Cada accion del solver es
un query al SCM que devuelve un nuevo DataAsset. "Quiero ver la distribucion
de Y cuando fuerzo X a nivel alto" → el SCM genera esos datos → el solver
los recibe como un dataset nuevo.

**El caso tiene profundidad por diseno.** El orchestrator no solo genera un
SCM y un brief. Disena una **estructura de revelacion**: que se ve de
entrada, que se desbloquea con que accion, y donde estan las sorpresas. El
mundo tiene 15 variables pero el solver inicialmente solo ve 5. Las otras
10 son accesibles pero tiene que pedirlas. Y algunas son las que resuelven
el caso.

**Dead ends y honey traps son parte del diseno.** Algunas acciones llevan
a informacion que parece util pero es un callejon sin salida — una variable
que correlaciona fuerte con todo pero no causa nada, gasta budget sin
avanzar. El solver que planifica bien los evita, el que va a ciegas los
pisa.

**El numero de pasos emerge de la complejidad.** Un mundo simple se resuelve
en 5 acciones. Un mundo con 3 subsistemas interconectados, confounders
ocultos e interacciones no-lineales necesita 20-30.

Esto crea presion evolutiva directa para: workflow iterativo, plan dinamico,
descomposicion de preguntas, saber cuando parar, y separar evidencia de
priors. Porque el plan optimo cambia con lo que descubris, y hay que decidir
activamente cuando seguir y cuando es suficiente.

Requiere: research actions como interfaz del entorno (queries al SCM, no
herramientas internas), estructura de revelacion disenada por el
orchestrator, budget como recurso del caso, catalogo de acciones con costos.

**3. Material teorico sintetico**

Papers ficticios, hallazgos previos contradictorios, teorias rivales.
El solver tiene que integrar literatura inventada con datos para
investigar.

Requiere: generacion de literatura sintetica derivada parcialmente del
mundo verdadero, mecanismo para que el solver consulte y cite fuentes.

Cada horizonte es una etapa futura del proyecto, no una limitacion
permanente. La seccion "El potencial es muy amplio" describe la vision
completa. Esta seccion aclara que se evalua hoy y que no.

---

## Invariantes

### 1. Verdad formal y reward exacto

Detras de cada SRC debe existir una capa formal que permita verificar con rigor
la calidad de respuestas, decisiones y trayectorias. Esa verdad es un modelo
causal estructural (SCM): un grafo dirigido aciclico con ecuaciones que definen
como cada variable depende de sus causas. Esto permite computar reward signals
exactos sin jueces ni heuristicas — intervenciones, mediaciones, interacciones
y mas se resuelven contra el SCM. Si algo no puede evaluarse contra esa verdad
subyacente, no pertenece al nucleo de SREG.

### 2. El caso debe sentirse como investigacion real

Todo lo que diseniemos tiene que acercar el entorno a una investigacion
cientifica real, no a una mecanica de juego ni a un ejercicio abstracto
disfrazado.

> **LA PREGUNTA (filtro diagnostico):**
>
> **1. ¿Por que esto todavia no es una investigacion real? ¿Que le falta?**
>
> **2. ¿Por que un modelo entrenado con RL sobre SREG todavia no aprenderia
> buen juicio cientifico?** ¿Que le falta al sistema para ensenar research
> taste, descomposicion de problemas, generacion de preguntas fine-grained,
> saber que es relevante para el objetivo y que no, saber que mirar y que
> ignorar, saber cuando una conclusion es prematura vs bien fundada?
>
> **PRESIONES EVOLUTIVAS (criterio de diseno):**
>
> **3. ¿El scoring crea presion evolutiva para que el agente que investiga
> bien rinda mas que el que no?** Para cada componente de SREG: un agente
> SIN la propiedad X, obtiene en promedio un score mas bajo? Si no, hay que
> redisenar. Lista completa en "Presiones evolutivas" mas abajo.
>
> Ambas herramientas deben estar presentes en cada decision, cada evaluacion,
> cada linea de codigo. La respuesta evoluciona a medida que SREG mejora.
> Las brechas conocidas estan en `research/synthesis/sreg_scientific_coverage.md`.
>
> **Marco canonico para evaluar paper/tesis:** `research/synthesis/thesis_evaluation_framework.md`.

Litmus test operativo: "Un investigador real en este dominio haria esto?"

### 3. Las preguntas deben forzar investigacion

Las preguntas deben depender de la evidencia de **este caso**, no solo del
conocimiento general del dominio. Si un solver puede responder sin mirar los
datos, sin integrar contexto o sin investigar, la pregunta no sirve.

Lo que mas fuerza investigacion real no es una pregunta generica, sino la
**ambiguedad mecanica**: multiples explicaciones plausibles que solo pueden
distinguirse con evidencia del episodio.

### 4. La policy tiene libertad total para razonar

SREG no debe prescribir el razonamiento interno del solver. La policy puede
analizar, programar, comparar hipotesis o usar el procedimiento que quiera. Lo
que si importa es que las acciones del caso tengan sentido investigativo y que
sus consecuencias puedan evaluarse con rigor.

### 5. El paper inspira, no se replica

Cuando un paper real o un caso real inspira un SRC, SREG extrae problematica,
estructura, tipo de investigacion y tensiones relevantes, pero construye un
mundo nuevo. El agente no debe poder resolverlo por memoria.

### 6. La capa semantica es parte del entrenamiento

La semantica no es decoracion. Afecta que tipo de shortcuts aparecen, que
razonamiento exige el caso y que tan transferible puede ser lo aprendido.

### 7. Las restricciones son parte del problema

Costo, acceso a datos, imposibilidad de ciertas intervenciones, etica, ruido,
sesgo y ambiguedad no son detalles accesorios. Son parte constitutiva de la
investigacion.

### 8. Flow A vs Flow B: fronteras del compiler

SREG tiene dos caminos de compilacion con reglas OPUESTAS sobre cuanto del
SCM pueden ver. Confundirlos es una fuente recurrente de bugs silenciosos
que rompen o bien la presion evolutiva sobre el solver, o bien el ground
truth del reward exacto.

**Flow A** — compilacion de claims (`oi_extraction.py` grammar-direct
default, `oi_compiler.py::lower_intent` fallback): traduce claims del
solver en specs de verificacion. **Debe permanecer ciego al
DAG del SCM.** Dar a Flow A acceso estructural rescataria el razonamiento
causal del solver (auto-corregir un `adjust_set` invalido, canonicalizar
un control set malo) y romperia la presion evolutiva — razonar mal
deberia costarle puntos al solver, no ser reparado en silencio. El
comportamiento correcto de Flow A sobre un claim con error estructural es
validar referencias y abstenerse o fallar limpiamente, nunca repararlo.

**Flow B** — `src/sreg/tools/oi_sq_compiler.py::compile_sq_to_specs`:
compila sub-questions que genera el orquestador en verification specs
que se convierten en **ground truth**. En este paso **no se evalua al
solver** — el sistema esta fabricando la verdad contra la que despues va
a calificarlo. Flow B **debe** derivar decisiones estructurales (backdoor
sets, identifiability checks, etc.) del SCM en forma deterministica.
Dejar que un LLM adivine estas decisiones produce ground truth
silenciosamente roto. El comportamiento correcto de Flow B sobre una
ruta causal es que el LLM elija `treatment`, `outcome` y el wording; el
codigo rellena el backdoor set via
`oi_verifier.py::_find_backdoor_set`.

**Litmus test operativo:** ante cualquier cambio que toque contratos de
compile/verify, preguntar primero a que flow pertenece. Si un cambio
parece limpio en un flow pero rompe el otro, la regla correcta no es
unificarlos — es reconocer que los dos flows necesitan logica distinta.
La misma pregunta de superficie ("¿el compiler deberia ver el DAG?")
tiene respuestas opuestas segun el flow.

---

## Jerarquia de decision

Cuando hay conflicto entre objetivos, aplicar estas reglas en orden:

1. **Verificabilidad > realismo.** Si algo mejora el realismo pero rompe la
   capacidad de evaluar con rigor, no sirve para el nucleo de SREG.
2. **Experiencia investigativa > formalismo elegante.** Si algo mejora la
   formalizacion pero hace que el caso se sienta artificial, tampoco sirve.
3. **Forzar investigacion > facilitar respuesta.** Si un solver puede acertar
   sin investigar, el entorno esta mal disenado.
4. **El caso manda.** Las preguntas, acciones y datos deben nacer del research
   case como conjunto, no como piezas desconectadas derivadas mecanicamente.
5. **Simplicidad > complejidad vacia.** No agregar capacidad si no mejora la
   experiencia investigativa ni la calidad de evaluacion.

---

## Principios de diseno del scoring — NO NEGOCIABLE

Estos principios aplican a CUALQUIER diseno de scoring, presente y futuro.

1. **UN solo metodo de scoring para todo.** NO hay "scoring profiles" por tipo
   de investigacion. Hay UN metodo general que funciona para cualquier caso.
2. **El sistema se adapta a los casos, no al reves.** Los casos vienen de
   seeds reales — pueden ser cualquier cosa. El scoring no fuerza una forma.
3. **El brief es libre y puede tener multiples objetivos.** Una pregunta vaga,
   varias preguntas, objetivos mixtos — todo valido.
4. **No construir un juego estructurado.** Si el scoring requiere "roles",
   "slots", "pattern_weights" y 10 campos de metadata, estamos construyendo
   un juego, no evaluando investigacion.
5. **La verificacion es el core, el scoring es un wrapper.** El SCM verifica
   cualquier claim. El scoring solo pregunta: es verdad? es relevante? cubrio
   lo pedido? no spameo?

Validar cada cambio de scoring contra los 23 escenarios de investigacion:
`research/synthesis/investigation_scenarios_rubric.md`.

---

## Hacia donde va SREG

El punto de partida puede ser un entorno pequeno y controlado. El destino es un
generador de investigaciones sinteticas cada vez mas ricas, donde el solver
tenga que:

- situarse en un problema,
- trabajar con evidencia imperfecta,
- usar teoria ademas de datos,
- discriminar entre mecanismos rivales,
- decidir que acciones de investigacion valen la pena,
- y sostener conclusiones bajo restricciones y ambiguedad.

La direccion del proyecto no es "un CSV y una pregunta".

La direccion es **investigacion completa**: leer, situar, proponer, diseniar
experimentos, medir, intervenir, analizar, validar, consultar, y decidir.

A futuro, SREG deberia poder cubrir formas diversas de investigacion:
observacional, experimental, de campo, clinica, ingenieril u otras, cada una
con sus propias reglas, instrumentos, restricciones y acciones posibles.

El caso es el que define el universo del solver. Cuanto mas rico sea ese
universo — con literatura sintetica, colaboradores simulados, laboratorios
con capacidades especificas, restricciones operativas reales — mas se acerca
a lo que enfrenta un investigador real.

El resultado buscado no es solo "mas tasks". Es un entorno donde investigar
bien sea necesario, medible y transferible.

### Presiones evolutivas: que propiedades debe forzar SREG

SREG no es un curriculum ni una lista de habilidades a ensenar. Es un
**entorno con reward signal**. El objetivo es que las presiones evolutivas
del entrenamiento (RL u otro) fuercen que los agentes bien puntuados tengan
estas propiedades — porque no tenerlas produce, en promedio, scores mas bajos.

Esto es el criterio de diseno central: cada componente de SREG (el caso, los
datos, las herramientas, el scoring) debe estar disenado para que el agente
que investiga bien rinda mas que el que no. Si una propiedad no produce
ventaja medible en el score, el sistema esta fallando en crearla.

**Planificacion y descomposicion:**
- **Descomponer preguntas vagas en fine-grained** — y actualizarlas a medida
  que aprende cosas nuevas. No "que causa Y" sino "cual es el efecto de X
  sobre Y controlando por Z, y cambia segun el nivel de W?"
- **Buena planificacion** — tener un plan de investigacion, no ir a ciegas.
  No ejecutar analisis sueltos sin saber por que.
- **Plan dinamico** — actualizar la estrategia cuando la evidencia lo
  justifica. El plan no es un contrato, es un mapa vivo.

**Generacion de hipotesis:**
- **Generar hipotesis, no solo elegir** — dado lo que se hasta ahora, que
  podria explicar esto? No es seleccionar entre opciones dadas — es producir
  explicaciones candidatas. La habilidad mas importante de un investigador.
- **Hipotesis rivales** — no casarse con la primera explicacion. Generar al
  menos dos alternativas genuinamente competitivas antes de testear.
- **Hipotesis testeables** — generar hipotesis que sean verificables con los
  datos y herramientas disponibles, no especulaciones abstractas. "Si A es
  verdad, deberia ver X en los datos; si B es verdad, deberia ver Y."
- **Hipotesis que discriminen** — buscar predicciones que separen las hipotesis.
  Si A y B predicen lo mismo, no sirven para elegir entre ellas.
- **Refinamiento ante evidencia parcial** — cuando la evidencia no cierra
  del todo, ajustar la hipotesis en vez de descartarla o forzarla. La
  evidencia parcial es informacion, no fracaso.

**Diseno experimental y creatividad analitica:**
- **Inventar el analisis correcto** — no elegir de un menu de analisis. Dado
  la pregunta y los datos, disenar el procedimiento que realmente discrimina.
  Partir por subgrupos, crear variables derivadas, hacer permutation tests,
  testear interacciones, analisis de sensibilidad — lo que haga falta.
- **Creatividad analitica** — el solver tiene Python y los datos. Puede
  inventar analisis que nadie le pidio. La capacidad de ver "hmm, si
  estratifico por Z, puedo distinguir confounding de efecto directo" es
  exactamente lo que separa un buen investigador de uno mediocre.
- **Diseno de queries (H2)** — en la version secuencial, elegir que preguntarle
  al entorno y por que. Cada query cuesta budget. Un buen investigador elige
  queries que maximizan informacion, no las mas obvias.

**Ejecucion y proceso:**
- **Workflow iterativo** — ciclo de razonar, hipotetizar, experimentar,
  analizar, repetir. No un pipeline lineal de "cargo datos, corro regresion,
  concluyo".
- **Doble vision** — mantener la mirada macro del problema mientras se mete
  en los detalles. No perderse en un arbol y olvidar el bosque.
- **Eficiencia** — ir al resultado sin reinventar la rueda ni repetir lo que
  ya hizo. No recalcular cosas, no hacer analisis redundantes.

**Foco y toma de decisiones:**
- **Relevancia** — no perder el foco, no rabbit holes, no enamorarse de
  hallazgos que no importan para el objetivo.
- **Pivotear** — soltar algo que no funciona, no seguir insistiendo sin
  progreso. Cambiar de rumbo cuando la evidencia lo pide.
- **Saber cuando parar** — no declarar mision cumplida prematuramente
  cuando queda mas por descubrir, ni seguir indefinidamente cuando ya tiene
  suficiente.

**Rigor epistemico:**
- **Anti-overexcitement** — no declarar eureka por algo menor, sin
  significancia o artefacto estadistico. Un p-value de 0.04 con N=20 no
  es un descubrimiento.
- **Separar "me cierra" de "esta validado"** — que una explicacion suene
  coherente no significa que sea verdad. Necesita evidencia, no solo
  narrativa.
- **Verificacion honesta** — cuando dice "confirme X", que realmente lo
  haya chequeado con los datos, no superficialmente ni de memoria.
- **Mantener multiples restricciones activas** — no olvidarse de condiciones
  al chequear hipotesis. Si hay 3 confounders, controlar por los 3, no
  por 1.

**Independencia del caso vs priors:**
- **No driftear a lo familiar** — no retroceder a metodos comodos que
  invalidan la investigacion cuando algo se pone dificil. Si el caso
  requiere un approach incomodo, hacerlo.
- **Separar evidencia del caso vs priors del training** — investigar los
  datos de este episodio, no responder de memoria con conocimiento general.
- **Calibracion contextual** — saber si un R² de 0.3 es bueno o malo en
  este dominio, si una diferencia de 2% es relevante o trivial. El contexto
  del caso importa.

**Robustez ante trampas epistemicas:**
- **No snowballear errores** — si llega a una conclusion incorrecta
  temprano, no construir toda la investigacion encima de eso. Detectar
  cuando un hallazgo intermedio es fragil antes de invertir 15 pasos mas
  en esa direccion. El agente que propaga errores compuestos desperdicia
  budget y entrega conclusiones falsas al final.
- **No sobreexcitarse con resultados triviales** — ver una tendencia
  menor (efecto real pero insignificante) y perseguirla como si fuera
  el hallazgo principal. Un buen investigador sabe que algo puede ser
  estadisticamente real pero cientificamente irrelevante.
- **Detectar anomalias** — ver lo interesante en los propios resultados.
  Si un subgrupo se comporta distinto, si hay un patron inesperado, si
  un resultado contradice lo esperado, un buen investigador se detiene a
  investigar eso. No seguir el script predeterminado cuando los datos
  gritan algo diferente.
- **Saltos creativos, no repeticion mecanica** — cuando un analisis no
  da resultados, no repetir lo mismo con mas datos o hiperparametros
  distintos. Un buen investigador cambia de enfoque: prueba otro
  angulo, inventa una variable derivada, estratifica por algo inesperado.
  La capacidad de hacer un salto creativo ante un callejon sin salida
  es lo que separa investigacion real de fuerza bruta.

**El test de diseno:** para cada componente de SREG, preguntarse: si un
agente NO tiene la propiedad X, obtiene en promedio un score mas bajo?
Si la respuesta es no, hay que redisenar el componente hasta que la
respuesta sea si.

Si SREG no puede crear estas presiones, no cumple su proposito. Cada
decision de diseno debe evaluarse contra esta vara.

### Investigacion abierta (Open Investigation)

SREG debe evaluar no solo si el solver RESPONDE bien, sino si INVESTIGA bien.
El solver recibe un brief abierto ("investiga por que las internaciones son
desiguales") y tiene que descubrir que investigar, como, y que concluir.

La verificacion funciona en 3 capas: el solver investiga libre y entrega
hallazgos, un compiler los traduce a specs ejecutables via una gramatica
composable (~24 piezas atomicas combinables), y el SCM verifier ejecuta
contra la verdad formal — determinista, sin LLM.

**Honestidad sobre el reward:** en Open Investigation, la compilacion introduce
subjetividad encapsulada. Es mucho mas riguroso que LLM judge, pero no es
100% mecanico. Ver `ARCHITECTURE.md` para detalle tecnico y
`research/synthesis/open_investigation_vision.md` para la vision completa.

---

## Tensiones estrategicas abiertas

Estas tensiones si pertenecen a la vision del proyecto, porque afectan que tipo
de sistema estamos construyendo.

### Semantica realista vs semantica abstracta

Una semantica mas realista puede hacer que el agente razone como un cientifico
real, pero tambien puede empujarlo a usar priors del mundo real en vez de
investigar el caso. Una semantica mas abstracta reduce esa contaminacion, pero
puede volver el caso menos natural y menos transferible.

Esto no debe resolverse por gusto. Es una pregunta experimental del proyecto.

### Apertura del problema vs verificabilidad exacta

Cuanto mas abierto y ambiguo sea el caso, mas se parece a la ciencia real. Pero
cuanto mas abierto sea, mas dificil puede ser verificar con exactitud lo que
hizo el agente. SREG debe encontrar un equilibrio util entre apertura y rigor.

Open Investigation resuelve esta tension via compilacion: el solver investiga
libre, un compiler traduce a specs ejecutables, el SCM verifica. La compilacion
introduce subjetividad encapsulada pero el nucleo de verificacion es exacto.
El bottleneck actual es la calidad de la compilacion (ver CURRENT_STATE.md).

### Realismo investigativo vs control generativo

Los casos simples son mas faciles de generar, controlar y validar. Los casos
realistas son mas valiosos, pero tambien mas dificiles de diseniar y evaluar.
La arquitectura del proyecto debe permitir empezar simple sin fijar un techo
bajo para siempre.

---

## Ejemplo: como se ve un SRC

Un caso sobre declive en produccion de algas en un archipielago ficticio. El
solver recibe datasets de estaciones de monitoreo con datos faltantes, "estudios
previos" que sugieren hipotesis rivales, y la posibilidad de solicitar analisis
o proponer experimentos dentro de restricciones de presupuesto. Debe responder:
cual es la causa mas probable, que conviene medir, y que pasaria si se elimina
un compuesto del sedimento. Detras hay un modelo causal estructural (SCM) con
ecuaciones que definen las relaciones reales — cada respuesta se evalua
matematicamente. El solver no sabe que existe el SCM; solo ve un problema de
investigacion con datos y herramientas.

---

## Que no deberia contener este documento

Este documento no deberia describir:

- detalles finos de implementacion,
- estado actual del codigo,
- backlog o prioridades,
- bugs y deuda tecnica,
- resultados experimentales puntuales,
- decisiones locales todavia no estabilizadas.

Todo eso debe vivir en otros documentos.
