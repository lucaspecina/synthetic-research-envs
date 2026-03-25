# Brief vs Eval Separation: Architectural Finding

> Status: IMPLEMENTADO (Fase 5, 2026-03-21)
> Contexto: Fase 4 SCM wiring completada, prueba E2E con Vaca Muerta
> Participantes: Claude, Codex (gpt-5.2), usuario
> Implementacion: CasePlan.research_brief + deliverables, SCMProblemBuilder,
> orchestrator prompts. Validado E2E. Pendiente: task questions individuales
> siguen siendo semi-mecanicas (futuro: task primitives).
>
> **Evolucion (2026-03-25):** las 3 capas identificadas aqui (brief visible,
> eval agenda, query formal) se expanden en la vision de Open Investigation
> donde el solver descubre la agenda investigativa libremente y un LLM
> translator compila hallazgos a queries formales.
> Ver `research/synthesis/open_investigation_vision.md`.

## El problema

El mundo generado por el orchestrator con SCM es excelente -- variables
continuas, ecuaciones realistas (sigmoides, thresholds, interacciones),
unidades reales. Pero las preguntas que recibe el investigador parecen
un examen, no un encargo de investigacion.

### Lo que genero el orchestrator (Vaca Muerta)

```
Q1: "How would changing pad spacing affect the probability of sanding?"
    (causal_effect, intervention_node=pad_spacing)
Q2: "Which controllable intervention is likely to reduce sanding risk
    the most: increasing pad spacing or lowering child fluid intensity?"
    (compare_interventions)
Q3: "What hidden factor best explains why some apparently similar
    interference events still end in sanding?"
    (infer_latent_cause)
Q4: "What is the expected sanding risk given observed conditions?"
    (infer_target)
```

### Lo que recibiria un investigador real

```
"Investigue por que algunos eventos de interferencia por fractura
terminan en arenamiento en pozos padre y otros no. Identifique los
factores operativos y geomecanicos que mas probablemente explican
el fenomeno. Evalue si cambios en distanciamiento, intensidad de
fluido y presion maxima reducirian materialmente el riesgo. Entregue
una recomendacion preventiva para la proxima campana."
```

La diferencia es enorme. Las preguntas generadas:
- Nombran variables especificas (pad_spacing, child_fluid_intensity)
- Son atomicas (una variable, un tipo de analisis)
- Usan lenguaje de benchmark ("maximize sanding_risk being above 0.35")
- No piden investigacion abierta sino respuestas puntuales

## Diagnostico: tres capas confundidas

El sistema hoy confunde tres capas:

1. **Brief** para el investigador: lo que una persona real recibiria
   - "Investigue que causa el arenamiento y recomiende medidas"
   - Lenguaje natural, abierto, sin nombrar variables formales

2. **Agenda de evaluacion**: que queremos scorear
   - 4 tasks: causal_effect(pad_spacing), compare_interventions, etc.
   - Estructura interna, NO visible para el investigador

3. **Query formal**: ground truth computable desde el SCM
   - P(Y|do(X=high)) vs P(Y|do(X=low)), KL divergence, etc.
   - Puramente computacional, NUNCA visible

Hoy las tres estan colapsadas en `CasePlan.questions`. La primera
question se convierte en `ResearchProblem.research_question` (visible).
Resultado: el investigador ve eval-speak.

### Donde se manifiesta en el codigo

- `CasePlan`: no tiene `research_brief`; solo `questions`, y la primera
  es la "principal"
- `SCMProblemBuilder._build_question()`: construye la pregunta visible
  desde `plan.questions[0]` y le agrega "Analyze the data to estimate
  the distribution"
- `SCMTaskGenTool.generate_from_plan()`: `compare_interventions` nunca
  permite override seguro del wording -- el template de maquina sale
  a superficie

## Solucion propuesta

### Camino corto (sin romper nada)

1. Agregar `research_brief: str` y `deliverables: list[str]` a `CasePlan`
2. El orchestrator escribe el brief como un encargo real de investigacion
3. `ResearchProblem.research_question` se construye desde el brief,
   NO desde `questions[0]`
4. `questions` queda como plan oculto de scoring
5. Dejar de mostrar templates internos (compare_interventions, etc.)

### Camino de fondo (mediano plazo)

"Free-form research brief, closed-form decomposition":
- Una pregunta amplia compila a un bundle de primitivas exactas
- Para Vaca Muerta: el brief principal compila a ~4 primitivas
  (multiple causal_effect, compare_interventions, infer_latent_cause,
  infer_target)
- El investigador ve el brief; el sistema scorea las primitivas

## Restriccion sagrada

**El reward exacto es innegociable.** La separacion de capas no
cambia como se computa el score -- solo cambia que ve el investigador.
El ground truth sigue viniendo del SCM via Monte Carlo.

## Conexion con LA PREGUNTA

> Por que esto todavia no es una investigacion real?

Porque un investigador real no recibe "How would changing pad_spacing
affect the probability of sanding?" con la variable ya nombrada.
Recibe un problema abierto y tiene que descubrir las variables
relevantes el mismo. Separar brief de eval es el paso mas critico
para cerrar esta brecha.
