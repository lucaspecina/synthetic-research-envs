# SREG — Vision del Proyecto
## Synthetic Research Environment Generator

> **Norte filosófico.** Define qué es SREG, por qué existe, qué fuerza, e invariantes que no pueden romperse. No describe implementación ni estado actual.
>
> Implementación: `ARCHITECTURE.md` · Estado actual: `CURRENT_STATE.md` · Trabajo pendiente: GitHub Issues.

---

## Misión

SREG genera **entornos sintéticos de investigación** con **verdad formal verificable**, diseñados para que un agente (Investigator) sólo pueda rendir bien si **investiga bien**.

```
SREG genera:    entorno + reward signal exacto
Otros traen:    policy + framework de RL + loop de entrenamiento
```

No es un benchmark estático: es un generador de casos nuevos donde cada seed puede producir un entorno distinto, y el reward se computa contra una verdad matemática (no humana, no LLM).

**Criterio de éxito**: una policy entrenada con entornos SREG demuestra mejor razonamiento científico en benchmarks externos que la misma policy sin entrenar.

---

## Lo que SREG quiere lograr

El objetivo no es producir preguntas con respuestas correctas. Es construir entornos donde **la estrategia ganadora sea investigar como un científico real**, y donde el output evaluable sea un **reporte científico con conclusiones**, no la respuesta a un cuestionario.

Para resolver bien un caso, el Investigator debería tener que:

- interpretar evidencia parcial,
- integrar datos con contexto y material teórico,
- **generar hipótesis propias** y compararlas como rivales genuinas,
- **inventar el análisis correcto** (no elegir de un menú),
- decidir qué medir, qué analizar, qué experimento conviene,
- razonar bajo restricciones (presupuesto, ética, acceso),
- responder con fundamento en la evidencia del caso, no en memoria o priors.

> **La vara conceptual:** si el Investigator no tuvo que investigar como un científico real para llegar a su respuesta, el entorno falló — aunque el score final sea alto.

---

## Lo que NO es SREG

- **No entrena policies.** Genera entornos y computa rewards.
- **No es un benchmark fijo.** Cada caso debe poder ser nuevo.
- **No prescribe cómo razonar.** Da entorno, restricciones y herramientas.
- **No depende de jueces humanos como núcleo.** La referencia central es formal y verificable.
- **No replica papers reales.** Los papers inspiran, SREG construye mundos nuevos.
- **No es un examen disfrazado.** El sistema interno tiene targets ocultos, pero esos targets son **descubrimientos esperados** (conclusiones científicas), no preguntas que el agente debería hacerse explícitamente. Ver §"Investigación abierta vs examen cerrado".

---

## Investigación abierta vs examen cerrado

SREG vive en una tensión central:

- Si los targets internos son demasiado específicos (*"Estimate the ATE of X on Y"*), SREG se vuelve un examen cerrado: el agente ya no investiga, responde subpreguntas implícitas.
- Si no hay target oculto, no hay forma de evaluar — una pregunta vaga tiene infinitas respuestas válidas.

**La solución conceptual**: el sistema interno no almacena *preguntas*, almacena **DiscoveryTargets**. Un DiscoveryTarget es un descubrimiento central oculto que el mundo sintético fue diseñado para contener, y que una buena investigación libre debería recuperar.

Cada DiscoveryTarget tiene **dos capas**:

> **Arriba**: conclusión científica flexible, redactable como abstract de paper.
> *Ej: "El investigador debería descubrir que el riesgo de arenamiento es impulsado principalmente por la intensidad de frac-hits, pero el efecto aparente está distorsionado a menos que se considere la presión del pozo madre y la historia del pad."*
>
> **Abajo**: verdad formal verificable, anclada al `Environment` ejecutable (dirección de efecto, magnitud aproximada, ranking, mediación, heterogeneidad, threshold, etc.).

La apertura está en el proceso (el agente decide hipótesis, análisis, modelos, pruebas). La verificabilidad está en los anchors formales (el evaluator compara conclusiones contra la verdad del SCM/ODE).

### 4 protecciones contra el regreso al examen cerrado

El renombre de "GoldQuestion" a "DiscoveryTarget" no alcanza por sí solo. Para que el sistema sea genuinamente investigación abierta, deben coexistir las cuatro:

1. **Capa A flexible en NL** — el target se expresa como conclusión científica redactable libremente, no como wording exacto.
2. **Capa B formal en anchors** — la verdad subyacente es matemática contra el `Environment`, computada en design-time vía `EvidenceArtifact`.
3. **Evaluator que acredita conclusiones equivalentes** — la rubric reconoce paráfrasis y claims cuantitativas que implican la misma conclusión cualitativa. No premia wording.
4. **Case Writer ciego al target oculto** — el brief que ve el Investigator NO se construye desde los DiscoveryTargets. Se construye desde el `narrative_capsule` saneado y el `WorldSpec` (visible). Si el brief hereda los textos de los targets, el agente parafrasea y no investiga.

Si falla cualquiera de las cuatro, el sistema vuelve a ser examen disfrazado.

### Knowledge vs Capability — qué evalúa v1.5

SREG distingue dos tipos de contribución científica:

- **Knowledge contribution**: mecanismo, causa, explicación, mapeo del sistema, limitación epistémica, hipótesis respaldada por evidencia. **Foco de v1.5.**
- **Capability contribution**: predictor con métrica de performance, controlador, optimizador, policy, modelo generativo. **Reservado para v2+.**

En v1.5, el Investigator puede usar capabilities (entrenar modelos, optimizar, simular) **como herramientas internas**, pero el output scoreado son las **claims/conclusiones** del reporte. Capability-as-evidence es válido si se expresa como conclusión ("la señal predictiva principal viene de X y Y"), no como artefacto numérico ("AUC=0.87 sobre el test set").

v1.5 NO incluye: hidden test set submissions, scoring por ROC AUC/RMSE programático, optimización de policies, controllers ejecutables, acciones interactivas de `observe/intervene/simulate` por el Investigator.

---

## LA PREGUNTA (filtro diagnóstico)

Cada decisión y cada componente pasa por estas dos preguntas:

> **1. ¿Por qué esto todavía no es una investigación real? ¿Qué le falta?**
>
> **2. ¿Por qué un modelo entrenado con RL sobre SREG todavía no aprendería buen juicio científico?** ¿Qué le falta al sistema para enseñar research taste, descomposición de problemas, generación de hipótesis fine-grained, saber qué es relevante y qué ignorar, distinguir cuando una conclusión es prematura vs bien fundada?

## Presiones evolutivas (criterio de diseño)

SREG **debe estar diseñado para que las presiones evolutivas del entrenamiento fuercen** que los agentes bien puntuados tengan estas propiedades — porque NO tenerlas produce, en promedio, scores más bajos.

**Test de diseño operativo**: para cada componente, ¿un agente SIN la propiedad X obtiene un score más bajo? Si no, hay que rediseñar.

Lista de propiedades agrupadas:

- **Planificación**: descomponer preguntas vagas en fine-grained, plan dinámico que se actualiza con la evidencia, no ir a ciegas.
- **Hipótesis**: generar (no elegir), rivales genuinas, testeables, que discriminen, refinables ante evidencia parcial.
- **Diseño analítico**: inventar el análisis correcto, creatividad analítica, diseño de queries con costo (en v2).
- **Ejecución**: workflow iterativo, doble visión macro/micro, eficiencia.
- **Foco**: relevancia, pivotear cuando no funciona, saber cuándo parar.
- **Rigor epistémico**: anti-overexcitement, separar "me cierra" de "está validado", verificación honesta, mantener restricciones activas.
- **Independencia caso vs priors**: no driftear a métodos cómodos cuando el caso pide otra cosa, separar evidencia del caso vs conocimiento del entrenamiento, calibración contextual.
- **Robustez ante trampas**: no snowballear errores, no obsesionarse con resultados triviales, detectar anomalías, saltos creativos en callejones sin salida.

Si SREG no puede crear estas presiones, no cumple su propósito.

---

## Invariantes (NO negociables)

1. **Verdad formal y reward exacto.** Detrás de cada caso existe una capa formal (SCM, ODE, en el futuro SDE) que permite verificar respuestas con rigor matemático. Si algo no puede evaluarse contra esa verdad subyacente, no pertenece al núcleo de SREG.

2. **Los descubrimientos deben forzar investigación.** Cada caso tiene targets ocultos (DiscoveryTargets) que dependen de la evidencia de **este caso**, no del conocimiento general del dominio. Si un agente puede llegar a la conclusión esperada sin mirar los datos, el target no sirve. Ver §"Investigación abierta vs examen cerrado" para las 4 protecciones que mantienen esta invariante.

3. **El caso debe sentirse como investigación real.** Todo lo que se diseñe acerca el entorno a una investigación científica real, no a una mecánica de juego ni a un ejercicio abstracto.

4. **El Investigator tiene libertad total para razonar.** SREG no prescribe cómo razonar internamente. Da entorno, restricciones, herramientas. La policy decide cómo proceder.

5. **El paper inspira, no se replica.** Cuando un paper inspira un caso, SREG extrae problemática y estructura, pero construye un mundo nuevo. El agente no debe poder resolver por memoria.

6. **La capa semántica es parte del entrenamiento.** Los nombres, dominios y framings no son decoración — afectan qué shortcuts aparecen y qué tan transferible es lo aprendido.

7. **Las restricciones son parte del problema.** Costo, acceso a datos, imposibilidad de ciertas intervenciones, ética, ruido, sesgo, ambigüedad — son constitutivas, no accesorias.

---

## Jerarquía de decisión

Cuando hay conflicto entre objetivos, aplicar en este orden:

1. **Verificabilidad > realismo.** Si algo gana realismo pero rompe la capacidad de evaluar con rigor, no sirve.
2. **Experiencia investigativa > formalismo elegante.** Si formaliza más pero el caso se siente artificial, tampoco sirve.
3. **Forzar investigación > facilitar respuesta.** Si un Investigator puede acertar sin investigar, el entorno está mal diseñado.
4. **El caso manda.** Las preguntas, acciones y datos nacen del caso como conjunto, no como piezas desconectadas.
5. **Simplicidad > complejidad vacía.** No agregar capacidad si no mejora la experiencia investigativa ni la calidad de evaluación.

---

## Principios de scoring (NO NEGOCIABLES)

1. **UN solo método de scoring para todo.** No hay "scoring profiles" por tipo de investigación.
2. **El sistema se adapta a los casos**, no al revés.
3. **El brief es libre**: una pregunta, varias, vagas, mixtas — todo válido.
4. **No construir un juego estructurado.** Si necesita "roles", "slots", "pattern_weights" para funcionar, es un juego — no evaluación de investigación.
5. **La verificación es el core**, el scoring es un wrapper.
6. **Diversidad de investigación**: el sistema debe funcionar para tipos diversos (causal, system mapping, descriptivo, epistemológico, etc.).
7. **DIVERSIDAD DE CASOS — sin esto nada tiene sentido.** El MVP debe entregar varios casos diversos por formalismo (NO un caso canónico único). Distintos dominios, distintos tipos de trampa, distintas dificultades. Casos famosos son **smoke tests**, no evidencia principal.

---

## Roadmap conceptual

| Versión | Paradigma | Estado |
|---|---|---|
| **v0** | Bayes Net + preguntas fijas | Eliminada (2026-03-29). Histórica. |
| **v1** | Open Investigation sobre SCM con compiler NL↔IR + LLM judge de relevancia. | Congelada en `main` (tag `pre-v1.5`). Compiler tocó techo ~82%. |
| **v1.5** | Rubric + LLM judge con answer keys grounded en Environment ejecutable. SCM + ODE (con observation noise opcional). | **Foco actual.** Rama `dev`. |
| **v1.6** | Agrega SDE intrínseco. | Futuro post-v1.5. |
| **v2** | Investigación interactiva multi-turno tipo Sherlock: budget visible, action-cost, capas de revelación, "next best action". | Futuro. |
| **v3** | Sistemas dinámicos complejos, biología real, agent-based models. | Lejano. |

Cada versión es un paradigma de investigación distinto, no una iteración menor.

---

## Hacia dónde va SREG

El destino es un generador de investigaciones cada vez más ricas, donde el agente tenga que situarse en un problema, trabajar con evidencia imperfecta, usar teoría además de datos, discriminar mecanismos rivales, decidir qué acciones de investigación valen la pena, y sostener conclusiones bajo restricciones y ambigüedad.

La dirección no es "un CSV y una pregunta". Es **investigación completa**: leer, situar, proponer, diseñar experimentos, medir, intervenir, analizar, validar, decidir.

---

## Qué NO contiene este documento

- Detalles de implementación → `ARCHITECTURE.md`
- Estado actual del código → `CURRENT_STATE.md`
- Backlog y prioridades → GitHub Issues
- Bugs y deuda técnica → Issues
- Resultados experimentales → `research/notes/`
- Decisiones locales no estabilizadas → `research/notes/`
