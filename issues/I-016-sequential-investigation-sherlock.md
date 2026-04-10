---
id: 16
title: Sequential investigation — Sherlock / gated info layers (A3b)
status: open
type: research
lane: research
priority: later
created: 2026-04-10
origin: TODO:A3b
---

# I-016: Sequential investigation — Sherlock / gated info layers

## Status
- **Estado:** vision documentada, no implementada
- **Ultimo resultado:** disenado en PROJECT.md Horizonte 2
- **Proximo paso:** research sobre como estructurar revelacion de informacion

## Pregunta
SREG hoy es flat: el solver recibe todo, analiza, submittea. La investigacion
real es long-horizon porque la informacion esta en capas y cada capa revela
que hacer en la siguiente.

El salto: convertir el caso de un paquete estatico a un entorno con
informacion gated. El solver empieza con poco (brief + dataset parcial +
catalogo de acciones), y cada accion cuesta budget y devuelve datos nuevos.
Dead ends y honey traps son parte del diseno.

Crea presion evolutiva directa para: workflow iterativo, plan dinamico,
descomposicion de preguntas, saber cuando parar.

**Dependencias:** requiere research actions como interfaz, estructura de
revelacion en el orchestrator, budget como recurso del caso.

**Referencia:** `PROJECT.md` Horizonte 2
