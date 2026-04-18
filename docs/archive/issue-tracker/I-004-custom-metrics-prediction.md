---
id: 4
title: Custom metrics para prediccion y optimizacion (A25)
status: open
type: research
lane: scoring
priority: later
created: 2026-04-10
origin: TODO:A25
---

# I-004: Custom metrics para prediccion y optimizacion

## Status
- **Estado:** idea documentada, no implementada
- **Ultimo resultado:** A28 audit confirma que `vaca_predict` FAIL por tipo
  predictivo no implementado
- **Proximo paso:** decidir si es un tipo especial de AtomicSpec o algo aparte

## Pregunta
SREG evalua con AtomicSpecs (DSL composable contra el SCM). Para prediccion
y optimizacion, el caso definiria UNA metrica puntual (MSE, AUC, rendimiento)
+ un holdout no visible al solver. El solver entrega modelo/prediccion, el
sistema ejecuta la metrica contra el holdout.

**Preguntas abiertas:**
- Cuanta infra nueva necesita? (dataset holdout, metrica runner)
- Se puede expresar como AtomicSpec especial o es algo aparte?
- Como convive con SQs?
- Es compatible con el principio "un solo metodo de scoring"?

**Pensar despues de cerrar A23 + P2.**
