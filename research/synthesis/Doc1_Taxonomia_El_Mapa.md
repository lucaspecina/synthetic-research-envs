# Doc 1 — Taxonomía de la Investigación Científica (El Mapa)

## Para qué sirve este documento

Este documento permite clasificar cualquier investigación científica ubicándola en un espacio multidimensional. Dado un paper, un proyecto, o un entorno sintético de SREG, este framework te dice *qué tipo de ciencia es*.

Tiene tres usos:
1. **Clasificar investigaciones reales** — analizar papers o proyectos
2. **Orientar SREG** — evaluar si los entornos sintéticos cubren el espacio de tipos de ciencia
3. **Conectar con ARS** — cada posición en el mapa demanda capacidades distintas del investigador

---

## 1. La gran división: ciencia que explica vs. ciencia que produce

Antes de las dimensiones finas, hay una división que organiza todo lo demás.

**Ciencia clásica (produce conocimiento):** analizar variables explícitas, crear teorías interpretables, establecer relaciones causales. Se busca *entender* — explicaciones e interpretaciones que un humano puede articular como un cuento causal. Variables pocas y bien definidas, modelos interpretables, ontología dada.

**Ciencia moderna (produce capacidades):** sistemas tan complejos que ya no pasa por entender explícitamente sino por poder predecir y hacer. Basada en herramientas computacionales, alta dimensionalidad, ontología por descubrir. Se buscan *predicciones y representaciones*.

La mayoría de la ciencia real vive en algún punto entre los dos polos, no en un extremo. Y frecuentemente la misma investigación tiene fases de cada tipo.

### El patrón de dos capas

Muchas investigaciones modernas operan en dos niveles simultáneos:

**Capa fenomenológica/computacional** — maneja la complejidad bruta. Alta dimensionalidad, patrones implícitos, sin interpretabilidad. No produce conocimiento — produce *acceso*: una representación manejable del sistema, candidatos filtrados, o predicciones.

**Capa mecanística/interpretable** — opera sobre el output de la primera. Acá se hacen preguntas causales, se construyen hipótesis, se busca comprensión. Trabaja sobre un espacio reducido que la capa computacional habilitó.

La capa computacional es infraestructura epistémica, no conocimiento en sí misma. Sin AlphaFold no tenés estructuras sobre las que razonar mecánicamente. Sin el pipeline de scRNA-seq no tenés tipos celulares sobre los que construir hipótesis de desarrollo.

**Ejemplos del patrón:**
- Drug discovery: red neuronal hace screening (fenomenológica) → modelo causal evalúa por qué funciona (mecanística)
- AlphaFold + biología estructural: AlphaFold predice estructura (fenomenológica) → biólogos infieren función a partir de forma (mecanística)
- Modelos de clima: deep learning predice patrones (fenomenológica) → climatólogos testean hipótesis sobre circulación oceánica (mecanística)
- scRNA-seq + biología del desarrollo: pipeline clusteriza células (fenomenológica) → biólogos preguntan qué genes regulan transiciones (mecanística)

---

## 2. Tipos de objetivo de investigación

Toda investigación tiene al menos un objetivo. Los objetivos pueden ser finales (el punto del proyecto) o intermedios (un paso hacia otro objetivo). Se dividen en dos clases según la naturaleza del output.

---

### Clase A: Producen conocimiento (output epistémico)

#### Descriptiva / Medición

Establece qué existe y cómo se comporta, sin explicar por qué. El mapa es el aporte. No pregunta "por qué", pregunta "qué hay ahí."

**Señales:** muchos gráficos y tablas, foco en medir bien y reportar incertidumbre. La palabra "causa" no aparece.

**Preguntas típicas:** ¿Qué tipos de X existen en Y? ¿Cuánto hay y cómo se distribuye? ¿Cómo cambia en el tiempo sin intervenir?

**Subtipos:** detección/existencia, cuantificación y distribución, tipología y clasificación, dinámica descriptiva.

**Ejemplos:** Human Genome Project, censos de biodiversidad, atlas de tipos celulares, catálogos astronómicos, mapeo de microplásticos en océanos.

---

#### Explicativa / Causal

Busca entender por qué ocurre algo. Desde mostrar que una intervención funciona (sin entender por qué) hasta reconstruir la cadena molecular completa. El criterio de éxito no es "el modelo predice bien" sino "la afirmación causal resiste intentos de refutación."

**Señales:** siempre aparece "¿y si esto es por otra cosa?" y el paper lo ataca con controles o inferencia causal. Sección de métodos densa.

**Preguntas típicas:** ¿Cambiar A realmente hace que B cambie? ¿A través de qué intermediario? ¿Qué pasaría si bloqueara ese paso?

**Subtipos:** asociación controlada, efecto causal de intervención, mecanismo proximal, mecanismo molecular completo, principio generativo.

**Ejemplos:** RECOVERY trial (dexametasona/COVID), Snow y el cólera, CRISPR fases 4-5, ensayos de CO₂ en bosques, fumar y cáncer.

---

#### Metodológica

Inventa una mejor manera de mirar el mundo. El output es una herramienta epistémica. Su impacto se mide por cuánto mejora la ciencia que otros hacen con esa herramienta.

**Señales:** el aporte no es "descubrí X" sino "así deberías hacer tu investigación." Comparación explícita contra método previo.

**Preguntas típicas:** ¿Este método produce resultados más válidos? ¿Sus propiedades se sostienen cuando los supuestos no son perfectos?

**Subtipos:** protocolo de dominio, método estadístico/computacional, marco de evaluación y estándares, nuevo paradigma experimental.

**Ejemplos:** Benjamini & Hochberg (FDR), Transformer (como contribución metodológica), tabla periódica (como sistema de organización), CONSORT para ensayos clínicos.

---

#### Teórica

Establece principios generales aplicables a familias de fenómenos. La validación es coherencia interna, poder predictivo sobre casos no anticipados, y capacidad de unificar fenómenos separados.

**Señales:** menos experimentos, más argumentación general con derivaciones. Los experimentos ilustran, no establecen el resultado.

**Preguntas típicas:** ¿Estos principios aplican a toda la clase? ¿Unifica fenómenos que necesitaban explicaciones separadas?

**Subtipos:** modelo formal de fenómeno específico, teoría de clase de fenómenos, marco unificador, revisión de fundamentos.

**Ejemplos:** Selección natural (Darwin), relatividad (Einstein), teoría de la información (Shannon), No Free Lunch theorem, tabla periódica (como principio organizador).

---

#### Síntesis

Integra lo que otros ya produjeron para establecer qué sabemos según la evidencia acumulada. No genera datos propios.

**Señales:** no hay datos propios. Flowchart de selección de estudios o protocolo de búsqueda.

**Preguntas típicas:** ¿Qué sabemos según toda la evidencia? ¿Por qué los estudios se contradicen?

**Subtipos:** revisión narrativa, revisión sistemática, meta-análisis, con modelado de heterogeneidad.

---

#### Replicación

Testea si un hallazgo de otro grupo se sostiene al reproducirlo.

**Señales:** referencia explícita a estudio previo. Pregunta central sobre robustez, no sobre el fenómeno.

**Subtipos:** directa, conceptual, con extensión.

---

#### Benchmarking / Evaluación comparativa

Establece qué métodos existentes funcionan mejor bajo qué condiciones, sin proponer ninguno nuevo.

**Señales:** no propone modelo nuevo. Tabla comparativa es resultado central. Criterios predefinidos.

**Subtipos:** comparación ad hoc, benchmark sistemático, con análisis de failure modes, benchmark evolutivo.

---

#### Exploración de espacio

Mapea un espacio de posibilidades — qué opciones existen, cuáles son prometedoras, qué estructura tiene el espacio. A diferencia de descriptiva, el espacio es parcialmente construido por el investigador.

**Señales:** el output es "encontramos N candidatos" o "el espacio tiene esta estructura."

**Preguntas típicas:** ¿Qué fracción satisface la propiedad Y? ¿Dónde están las regiones prometedoras?

**Subtipos:** muestreo aleatorio, dirigida por propiedades, mapeo de estructura, descubrimiento de estructura latente.

**Ejemplos:** GNoME (materiales), neural architecture search, drug discovery computacional.

---

### Clase B: Producen capacidades (output funcional)

#### Diseño / Ingeniería de sistemas

El objetivo no es entender sino construir algo que funcione. El valor es funcional: velocidad, precisión, costo, robustez.

**Señales:** arquitectura, pipeline, latencia, throughput, tests end-to-end.

**Subtipos:** herramienta asistida, pipeline automatizado, sistema adaptativo con loop cerrado, sistema con descubrimiento abierto.

**Ejemplos:** AlphaFold, A-Lab, CRISPR como herramienta de edición (fase final).

---

#### Predictiva pura

Modelos cuyo único criterio es predecir bien datos no vistos. No hay mecanismo, hay métricas de error.

**Señales:** train/test split, métricas out-of-sample, comparación contra baselines.

**Subtipos:** interpolación, extrapolación, cross-dominio, eventos raros.

---

### Tareas de soporte (nunca son objetivo final)

Habilitan la investigación pero nunca son el resultado. Si alguien pregunta "¿qué descubriste?", la respuesta nunca es ninguna de estas: buscar información, formular la pregunta/objetivo, definir variables y mediciones, elegir criterio de éxito, generar hipótesis, proponer mecanismo/modelo mental, derivar predicciones observables, diseñar el estudio/experimento, planificar recursos, recolectar datos/correr experimentos, construir/implementar sistema, correr pruebas, limpiar y explorar datos, estimar/entrenar/ajustar, chequear validez, interpretar fallos.

**Excepciones donde una tarea de soporte se convierte en contribución:** si el diseño experimental es tan innovador que *es* el aporte, se convierte en investigación metodológica. Si la exploración de datos revela algo sorprendente, se convierte en hallazgo descriptivo. Si la interpretación de un fallo revela algo sobre el sistema, se convierte en hallazgo explicativo.

---

## 3. Las 4 preguntas y sus dimensiones

Toda investigación se puede clasificar respondiendo 4 preguntas. Cada pregunta agrupa dimensiones scoreables (0-10 por categoría, scores independientes dentro de cada dimensión).

---

### Pregunta 1: ¿Qué querés? (objetivo y criterio de éxito)

Esta pregunta captura qué busca la investigación y cómo se juzga si lo logró.

#### Tipo de objetivo

Es el tipo de investigación según la sección 2: descriptiva, causal, teórica, predictiva, de diseño, metodológica, síntesis, replicación, benchmarking, exploración de espacio. Un caso puede tener varios objetivos (uno final y varios intermedios), y el tipo puede evolucionar en el tiempo (CRISPR pasó de descriptiva a causal a ingeniería a lo largo de 26 años).

#### Criterio de éxito

| Valor | Descripción |
|---|---|
| **Epistémico** | Éxito = afirmación verdadera sobre el mundo que resiste refutación |
| **Funcional** | Éxito = el sistema hace lo que tiene que hacer (predice, sintetiza, opera) |

El criterio no tiene que ser uno solo. Vaca Muerta tiene ambos: querés predecir cuánta arena retorna (funcional) *y* entender por qué (epistémico).

#### Scope

| Valor | Descripción |
|---|---|
| **Local** | Aplica en estas condiciones, este dataset, esta población |
| **Generalizable** | Aplica más allá de las condiciones específicas del estudio |

Darwin está en el extremo generalizable (principio universal). Vaca Muerta es local (aplica a esta formación, con estos pozos).

#### Relación con paradigma

| Valor | Descripción |
|---|---|
| **Incremental** | Refina, extiende, o valida dentro del paradigma actual |
| **Disruptivo** | Cuestiona los supuestos básicos del paradigma |

---

### Pregunta 2: ¿Qué tenés enfrente? (naturaleza del sistema)

Esta pregunta captura las propiedades del sistema que se investiga — lo que está ahí independientemente de lo que el investigador haga.

#### Ontología

| Valor | Descripción |
|---|---|
| **Explicit** | Variables relevantes definidas de antemano. El vocabulario del mundo está dado |
| **Implicit** | Variables deben descubrirse. Parte del trabajo es encontrar una forma útil de hablar del mundo |

En ciencia clásica la ontología suele estar dada (sabés qué variables importan). En ciencia moderna frecuentemente hay que descubrirla (scRNA-seq: ¿qué tipos celulares existen?).

#### Complejidad

| Valor | Descripción |
|---|---|
| **Simple/determinista** | Estado actual determina el siguiente. Todo observable |
| **Estocástico** | Variabilidad irreducible. Piso de incertidumbre |
| **Variables ocultas** | Causas que nunca se pueden medir directamente. No es problema de datos sino de acceso |

La complejidad no es lo mismo que dificultad. Un sistema puede ser simple pero el problema puede ser difícil (Einstein: la física es simple, el insight fue dificilísimo). Un sistema puede ser complejo y el problema puede ser relativamente directo (AlphaFold: el sistema es hipercomplicado, pero el objetivo está bien definido).

#### Mundo

| Valor | Descripción |
|---|---|
| **Closed** | Espacio de posibilidades bien definido. Variables y hipótesis enumerables |
| **Open** | Espacio potencialmente infinito. Pueden existir variables no anticipadas |

#### Tipo de modelo

| Valor | Descripción |
|---|---|
| **Mecanístico** | Refleja estructura interna real: causas, intermediarios, procesos. Permite razonar sobre intervenciones |
| **Fenomenológico** | Describe comportamiento observable sin representar lo que pasa adentro. Caja negra |
| **Dos capas** | Capa fenomenológica reduce complejidad, capa mecanística opera sobre su output |

---

### Pregunta 3: ¿Con qué contás? (recursos epistémicos)

Esta pregunta captura todo lo que el investigador tiene disponible para abordar el problema: fuentes de conocimiento, modos de producción, tipos de evidencia, herramientas, datos, y restricciones.

#### Fuente del conocimiento

| Valor | Descripción |
|---|---|
| **Data-driven** | El conocimiento emerge de patrones en datos sin hipótesis previa fuerte |
| **Theory-driven** | Se parte de principios o modelos y se testean |
| **Literature-driven** | El punto de partida es integrar y extender lo que otros produjeron |

#### Modo de producción

| Valor | Descripción |
|---|---|
| **Computational** | A través de simulaciones o modelos, sin contacto directo con el sistema real |
| **Experimental** | Intervención activa sobre el sistema real |
| **Observacional** | Mirar el sistema real sin tocarlo |
| **Teórico** | Derivación formal sin datos directos |

#### Contexto físico

| Valor | Descripción |
|---|---|
| **Wet lab** | Materia real: cultivos, reactivos, organismos, muestras físicas |
| **Dry lab** | Computadora: análisis de datos, simulaciones, modelos, código |
| **Field** | Sistema en contexto natural: ecología, geología, astronomía, campo industrial |

#### Tipo de evidencia

| Valor | Descripción |
|---|---|
| **Controlada** | Intervención activa con aleatorización o manipulación controlada. Permite inferencia causal directa |
| **Observacional** | Registros de lo que pasó sin intervención. Causalidad requiere supuestos fuertes |
| **Simulada** | De un modelo computacional. Solo encontrás lo que el simulador ya sabe |

#### Empirical vs Formal

| Valor | Descripción |
|---|---|
| **Empirical** | Verdad establecida por evidencia del mundo |
| **Formal** | Verdad establecida por derivación matemática o lógica |

#### Autonomía

| Valor | Descripción |
|---|---|
| **Human-in-loop** | Todo pasa por juicio humano |
| **Supervisor** | Sistema propone y ejecuta, humano revisa y aprueba |
| **Automated** | Sistema decide, ejecuta, y actualiza sin consultar |

---

### Pregunta 4: ¿Qué te puede engañar? (trampas epistémicas)

Esta pregunta no tiene dimensiones scoreables como las otras tres. Es una descripción cualitativa de las fuentes de error, confusión, y engaño que el investigador enfrenta. Es lo que hace que investigar sea difícil: no solo que el sistema sea complejo, sino que activamente puede llevar a conclusiones equivocadas.

Las fuentes principales de engaño son:

**Confounders:** una tercera variable causa tanto lo que creés que es la causa como lo que creés que es el efecto. Ves correlación y pensás que es causalidad. Es la trampa más frecuente en ciencia observacional.

**Colliders:** condicionás en la variable equivocada y generás una asociación espuria que no existe en la realidad. Más sutil que confounders porque requiere entender la estructura causal para detectarlo.

**Mediadores no observados:** A causa B, pero no podés ver el paso intermedio X. Esto impide distinguir si A causa B directamente o a través de X, lo cual importa para intervenciones.

**Sesgo de selección:** tus datos no son representativos del sistema real. Los pacientes que llegan al hospital no son iguales a la población general. Los papers publicados no son iguales a los estudios realizados.

**Ruido heterogéneo:** la precisión de tus mediciones varía entre condiciones. Si no lo sabés, puede distorsionar tus conclusiones.

**Efectos temporales:** trends, estacionalidad, o cambios graduales que se confunden con el efecto que estás estudiando.

**Feedback loops:** A causa B y B causa A. Hace que sea imposible separar causa de efecto sin intervención o sin modelado causal cuidadoso.

**Red herrings:** patrones reales en los datos pero irrelevantes para la pregunta. Especialmente peligrosos porque *son* reales — solo que no importan para lo que estás investigando. El investigador puede pasar tiempo estudiando algo genuino pero irrelevante.

**Conocimiento incorrecto aceptado:** hipótesis que se convirtieron en "hechos" por repetición. Modelos que todos usan pero cuyos supuestos nadie chequea. La teoría miasmática del cólera era conocimiento aceptado que Snow tuvo que enfrentar.

---

## 4. Workflows

Describen la estructura temporal de la investigación — cómo se encadenan las acciones en el tiempo. Un workflow no es una receta: es un patrón reconocible que aparece una y otra vez en investigaciones reales.

### Workflows iterativos

**Hipotético-deductivo.** El workflow clásico de la ciencia confirmatoria: formular una hipótesis, derivar una predicción, diseñar un experimento que pueda falsificarla, ejecutar, interpretar, y actualizar. Es eficiente cuando ya tenés un marco teórico rico del que derivar predicciones. Si el marco es pobre, no hay de dónde derivar — y forzar este workflow cuando no hay teoría es un error frecuente. Es el workflow de Barrangou con CRISPR: tenía una hipótesis clara (los espaciadores confieren inmunidad), derivó predicciones, diseñó el experimento de los tres grupos, ejecutó.

**Refinamiento bayesiano.** Empezás con un prior (lo que creés antes de ver evidencia), recolectás evidencia, actualizás tu creencia (posterior), y repetís. La diferencia con el hipotético-deductivo es que acá no hay "refutación" binaria — hay actualización gradual de confianza. Es el workflow natural cuando tenés múltiples hipótesis con distintos grados de plausibilidad y la evidencia va moviendo probabilidades. Cada nueva observación achica la incertidumbre. Terminás cuando la incertidumbre es suficientemente baja para decidir.

**Closed-loop automatizado.** Es refinamiento bayesiano pero donde el humano está fuera del loop: un sistema computacional propone la siguiente acción, ejecuta (o instruye ejecución), recibe resultado, actualiza, y repite. Es el workflow de surfactantes con BO (el Gaussian Process propone la siguiente formulación) y el que SREG implementa idealmente.

**Build-test-iterate.** El workflow de ingeniería: construir una versión, testearla contra criterio funcional, identificar dónde falla, mejorar, repetir. No hay hipótesis causal ni marco teórico — hay un objeto que funciona o no funciona. Es el workflow de AlphaFold (múltiples iteraciones de arquitectura evaluadas en CASP) y de Zhang con CRISPR en células humanas.

### Workflows lineales

**Observacional longitudinal.** Seguir un sistema sin intervenir a lo largo del tiempo. El investigador no toca nada — registra qué pasa. El valor viene de la duración y la consistencia de la observación. Es el workflow de Darwin durante el viaje del Beagle: cinco años observando y recolectando sin intervenir.

**Síntesis / meta-analítico.** Integrar datos de otros sistemáticamente. No hay recolección de datos propios. El valor viene de la capacidad de comparar, detectar inconsistencias, y llegar a conclusiones que ningún estudio individual podía.

### Workflows paralelos

**Exploratorio + confirmatorio.** Explorar en un dataset para generar hipótesis, y después confirmar en datos completamente distintos. La separación es obligatoria — si usás los mismos datos para explorar y confirmar, no confirmaste nada. Es el workflow que debería haberse usado en muchas crisis de replicación.

**Triangulación / multi-método.** Atacar la misma pregunta con métodos independientes que tienen sesgos distintos. Si todos convergen, la confianza es mucho mayor que con cualquier método solo. Es el workflow de Darwin después del viaje: fósiles por un lado, biogeografía por otro, embriología por otro, cría artificial por otro. Cada línea de evidencia tiene sus propias limitaciones, pero las limitaciones son distintas.

**Generación-evaluación masiva.** Muchos candidatos generados y evaluados en paralelo contra criterios predefinidos. Es el workflow de drug discovery computacional, neural architecture search, o cualquier búsqueda de espacio donde generás variantes y filtrás. La capacidad clave es definir bien los criterios de filtrado.

---

## 5. Tabla resumen comparativa de los 9 casos

Los 9 casos están analizados en profundidad en Doc 4. Esta tabla es una referencia rápida para ver el contraste entre tipos de investigación.

|  | Darwin | Snow | CRISPR | Einstein | Mendeleev | AlphaFold | Transformer | VacaMuerta | Surfactantes |
|---|---|---|---|---|---|---|---|---|---|
| **Objetivo** | Teórica | Causal | Desc→Caus→Ing | Teórica | Teórica+Met | Diseño/ing | Diseño+Met | Pred+Causal | Diseño+Expl |
| **Output** | Conocimiento | Conocimiento | Conoc→Capac | Conocimiento | Conocimiento | Capacidades | Capacidades | Conoc+Capac | Capacidades |
| **Fuente dom.** | Theory | Theory+Data | Theory | Theory+Lit | Data+Lit | Data | Data+Lit | Data | Data |
| **Producción dom.** | Observ+Teór | Observacional | Experimental | Teórico | Observ+Teór | Computational | Computational | Comp+Observ | Exp+Comp |
| **Modelo** | Mecanístico | Mecanístico | Mecanístico | Mecanístico | Mixto | Fenomenológ | Fenomenológ | Mixto | Fenomenológ |
| **Intervención** | No | No | Sí (fases 4+) | No | No | No | Sí (benchm) | No | Sí |
| **Disruptivo** | 10 | 8 | 8 | 10 | 8 | 8 | 8 | 2 | 2 |
| **Scope** | Universal | Medio | Alto | Universal | Universal | Alto | Alto | Local | Local |
| **Éxito** | Epistémico | Epistémico | Ambos | Epistémico | Epistémico | Funcional | Funcional | Ambos | Funcional |

---

## 6. Combinaciones frecuentes y raras

Ciertas posiciones en el mapa de dimensiones aparecen una y otra vez porque reflejan patrones naturales de cómo se hace ciencia. Otras posiciones son raras — no porque sean imposibles, sino porque representan formas inusuales de investigar que solo surgen en circunstancias específicas.

### Combinaciones frecuentes

La combinación **data-driven + fenomenológico + funcional** es el pan de cada día de la ciencia moderna de machine learning. AlphaFold, Transformer, cualquier modelo predictivo puro: tenés muchos datos, no te importa el mecanismo, y el éxito se mide por si funciona. Es eficiente y escalable, pero no produce comprensión.

La combinación **theory-driven + mecanístico + epistémico** es la ciencia clásica causal en su forma pura. Snow, las fases causales de CRISPR, ensayos clínicos: partís de una hipótesis sobre cómo funciona algo, diseñás un experimento para testearla, y el éxito es que la afirmación causal resista intentos de refutación. Es más lenta y costosa, pero produce comprensión transferible.

La combinación **data-driven + exploratorio + closed-loop** es la optimización experimental moderna: surfactantes con BO, drug discovery con active learning. No hay teoría fuerte — hay un espacio grande, un modelo probabilístico que guía la exploración, y un loop de proponer-ejecutar-actualizar.

La combinación **observacional + estocástico + variables ocultas** es la situación más difícil de la epidemiología, las ciencias sociales, y mucha ciencia industrial (Vaca Muerta, tabaquismo y cáncer): no podés intervenir, hay variabilidad irreducible, y las causas reales son inobservables. Todo el arsenal de diseño observacional y causalidad sin intervención existe por esta combinación.

### Combinaciones raras

La combinación **teórico + funcional** es rara porque la teoría usualmente busca entender, no hacer. Pero existe: la teoría de códigos para comunicación es derivación formal cuyo criterio de éxito es funcional (¿el código permite transmitir información de forma confiable?).

La combinación **data-driven + disruptivo** es rara porque los datos solos rara vez producen cambio de paradigma. Casi siempre lo disruptivo viene de reinterpretar datos existentes bajo un marco nuevo, no de datos nuevos. Einstein no tenía datos nuevos; Snow sí los tenía, pero el insight fue la reinterpretación.

La combinación **automated + epistémico** es rara y es el horizonte más ambicioso: producir conocimiento causal de forma automatizada, sin humano en el loop. Casi toda la ciencia automatizada que existe hoy produce capacidades (predicciones, optimización), no comprensión causal. Lograr esto es uno de los objetivos de largo plazo de SREG.

La combinación **open world + confirmatorio** es rara por razones lógicas: si el mundo es abierto (pueden existir variables que no anticipaste), es difícil pre-especificar una hipótesis con suficiente precisión para confirmarla. La ciencia confirmatoria asume implícitamente un mundo cerrado donde las alternativas están enumeradas.
