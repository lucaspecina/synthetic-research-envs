# Estrategia de evaluacion de SREG

> Sintesis consolidada a partir de `notes/eval_design_notes.md`.
>
> Resume que significa evaluar bien SREG y que tipos de evidencia importan.

## Pregunta estrella

La pregunta principal no es "subio el score?" sino:

> "Este SRC funciona como una mini-investigacion cientifica verificable y util
> para entrenar o evaluar agentes?"

Las metricas importan, pero son medios para responder esa pregunta.

## Principios consolidados

### 1. Evaluar con el sistema real

Cuando evaluamos el producto SREG, deberiamos usar el pipeline real:

- orchestrator,
- `CasePlan`,
- semantica,
- caso visible,
- solver,
- teacher y scoring.

### 2. Separar infraestructura de diseno experimental

El runner y los adapters son infraestructura. Los experimentos son otra capa.
No conviene mezclar ambos niveles en un solo script mental.

### 3. Comparar mas que medir en absoluto

Las comparaciones importantes son:

- agent vs teacher,
- agent vs baseline,
- run nuevo vs run anterior,
- solver A vs solver B,
- goal o dominio X vs Y.

### 4. Combinar metricas cuantitativas con inspeccion cualitativa

Un caso puede tener numeros aceptables y aun asi sentirse artificial. La
inspeccion cualitativa sigue siendo necesaria para no reducir la vision del
proyecto a scores faciles.

## Tres niveles de validacion

### Nivel 1: Tests

Verifican que el codigo y los contratos funcionen.

### Nivel 2: Diagnostico de entornos

Verifica que los SRCs producidos sean solubles, no triviales, coherentes y
realmente investigables.

### Nivel 3: Transferencia externa

Verifica si entrenar con SREG mejora capacidades fuera de SREG.

## Consecuencia para el proyecto

Una buena estrategia de evaluacion no solo mide rendimiento. Tambien protege la
vision del sistema:

- que no se vuelva un benchmark disfrazado,
- que no premie shortcuts,
- y que no confunda respuesta correcta con investigacion real.
