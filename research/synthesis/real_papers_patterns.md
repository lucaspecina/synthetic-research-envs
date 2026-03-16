# Patrones de investigaciones reales

> Sintesis consolidada a partir de `notes/real_investigations_analysis.md`.
>
> Resume los patrones que aparecen de manera consistente en los papers
> analizados y que importan para el diseno de SREG.

## Patrones principales

### 1. Data assembly es media investigacion

Los estudios reales rara vez parten de un solo dataset limpio. Suelen combinar
fuentes heterogeneas, con coberturas, granularidades y problemas distintos.

**Implicacion para SREG:** un solo CSV completo y pulcro es una simplificacion
fuerte. Los casos mas realistas deberian usar multiples artefactos de evidencia.

### 2. La dificultad central suele estar en la identificacion

En muchos trabajos, el reto no es "que modelo corro" sino "que comparacion me
permite aislar el efecto o mecanismo de interes".

**Implicacion para SREG:** no alcanza con tasks de respuesta final. El entorno
deberia valorar decisiones sobre comparaciones, controles, diseno y estrategia.

### 3. La validacion es multidimensional

La investigacion real no entrega una sola respuesta. Cambia especificaciones,
confounders, muestras y modelos para ver si la conclusion resiste.

**Implicacion para SREG:** robustez y sensibilidad no son extras; son parte del
trabajo cientifico que el entorno deberia capturar.

### 4. Las restricciones definen el tipo de investigacion

No se puede intervenir igual en epidemiologia, ecologia, materiales o economia.
Etica, costo y factibilidad moldean que acciones son validas.

**Implicacion para SREG:** las restricciones del caso deben ser especificas y no
solo un budget abstracto.

### 5. El framing cambia lo que cuenta como respuesta buena

Misma evidencia, distinta pregunta, distinta conclusion defendible. Subgrupos,
especificaciones o niveles de analisis pueden cambiar el sentido del hallazgo.

**Implicacion para SREG:** no todo deberia colapsar a una unica respuesta
descontextualizada.

### 6. La investigacion real es secuencial

Se formula, se explora, se mide, se corrige, se vuelve a probar. Los pasos
posteriores dependen de lo que revelan los anteriores.

**Implicacion para SREG:** el formato "recibe datos y responde" capta solo una
fraccion del trabajo real.

## Resumen para el proyecto

Los papers analizados empujan a SREG hacia casos con:

- evidencia heterogenea,
- restricciones especificas del dominio,
- mecanismos rivales,
- decisiones secuenciales,
- y evaluacion menos centrada en una unica salida final.

Esto no obliga a abandonar el nucleo formal del sistema. Obliga a usarlo para
generar casos mas parecidos a investigaciones reales.
