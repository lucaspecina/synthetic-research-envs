# What Makes Real Scientific Research Real

> Resultado de: analisis de 7 papers reales + 7 rondas de debate con Codex +
> examen de 5 SRCs generados. Sesion 2026-03-15.
>
> Este documento es la referencia para TODO lo que diseñemos en SREG.
> Cada feature, cada accion, cada dataset debe poder justificarse
> contra lo que se describe aqui.

## El diagnostico

SREG v1 genera "benchmarks causales con wrappers realistas" — no ambientes
de investigacion. Un investigador real que viera nuestros SRCs diria:
"los nombres de variables y la narrativa estan bien, pero esto no es
como yo trabajo."

**La diferencia fundamental:**
- **Benchmark:** "aqui tenes datos limpios y 5 preguntas, responde"
- **Investigacion:** "los arrecifes se estan muriendo, averigua por que y que hacer"

---

## Los 10 patrones que hacen real a una investigacion

### De papers reales (7 estudios analizados)

#### 1. Armar los datos es la mitad del trabajo

Cada estudio real combina 3-8 fuentes de datos heterogeneas:
- Registros hospitalarios + encuestas + datos satelitales
- Transectos de campo + imagenes de satelite + quimica del agua
- Datos administrativos + censos + cuestionarios a padres

Cada fuente tiene distinta granularidad, cobertura temporal, y problemas.
Un investigador pasa semanas limpiando, alineando, y validando antes de
analizar. **Un solo CSV limpio de 80 filas es irreal.**

*Ejemplo: el estudio danes de asma (Pedersen et al.) combina 7 registros
nacionales, modelos de exposicion a contaminantes con 3 escalas de resolucion,
y dos cohortes con cuestionarios propios. Solo el linkage tarda meses.*

#### 2. La estrategia de identificacion importa mas que el metodo

Lo dificil no es "que regresion correr" sino "que comparacion aisla el efecto
causal". Cada estudio tiene una IDEA creativa de como atacar el problema:
- Double negative controls (epidemiologia: si el efecto es real, no deberia
  aparecer con un outcome placebo)
- Age-at-move (economia: mudarse a un mejor barrio a los 5 años tiene mas
  efecto que a los 15 — eso sugiere efecto causal del barrio)
- Instrumental variables (ecologia: usar variacion exogena como "instrumento")

**Un agente que solo corre regresiones no esta haciendo investigacion.
La investigacion es DISENAR la comparacion correcta.**

#### 3. Sensitivity analysis es multidimensional

NINGUN estudio reporta UNA respuesta. Todos varian:
- Especificacion del modelo (lineal, logistico, quantile)
- Conjunto de confounders (modelo minimo, maximo, intermedio)
- Definicion de la muestra (inclusion/exclusion)
- Definicion del outcome (diagnostico clinico vs self-report vs biomarcador)
- Nivel de agregacion (individuo vs municipio vs cohorte)

El PATRON a traves de las especificaciones es lo que da confianza.
Si el efecto aparece en 15 de 20 especificaciones, es robusto.
Si solo aparece en una, es fragil.

**SREG deberia evaluar si el agente CHEQUEA su propia respuesta, no solo
si la respuesta es correcta.**

#### 4. Las restricciones moldean todo

Cada investigacion esta fundamentalmente definida por lo que NO puede hacer:
- No podes randomizar humanos a contaminacion (observacional obligatorio)
- No podes calentar un arrecife (solo observar variacion natural)
- No podes asignar familias a barrios (buscar "experimentos naturales")
- No podes probar 1000 composiciones de aleacion (presupuesto de muestras)
- No podes hacer un trial de 10 años con un farmaco no aprobado

**Las restricciones no son un extra — son lo que DEFINE el tipo de
investigacion. Un SRC deberia empezar por las restricciones, no por
las variables.**

#### 5. La respuesta depende del framing

Los mismos datos dicen cosas distintas segun como se analicen:
- School funding parece dañino sin controles, neutro con SES, y beneficioso
  para alumnos de bajo rendimiento (quantile regression)
- Dexamethasone ayuda a pacientes ventilados pero puede dañar a casos leves
- El efecto promedio de la contaminacion esconde que es mucho peor para
  ninos asmaticos que para ninos sanos

**No hay UNA respuesta correcta. Hay respuestas defensibles bajo distintos
supuestos. SREG deberia evaluar si las elecciones analiticas son defensibles,
no solo si el numero es correcto.**

#### 6. Toma de decisiones secuencial

La investigacion se desarrolla como una serie de decisiones:
- Resultados iniciales sugieren una variable importante → se mide con mas detalle
- Un experimento falla → se redisena con otros parametros
- Un analisis muestra confounding → se busca un instrumento
- Un subgrupo muestra efecto opuesto → se investiga por que

**No es "recibir datos, analizar, responder". Es un loop iterativo donde
cada paso informa el siguiente.**

### Del debate con Codex (7 rondas)

#### 7. Un investigador produce evidencia, no la revela

En un benchmark, la evidencia existe y se "descubre".
En la investigacion real, el investigador CREA evidencia:
- Diseña un estudio
- Recluta participantes
- Fabrica muestras
- Despliega instrumentos
- Decide que medir, como, y cuando

**Las acciones de un investigador no son "revelar un nodo oculto".
Son "lanzar un programa de recoleccion de datos con restricciones reales".**

#### 8. Los datos vienen con problemas de origen

No es que los datos son "limpios + algo de ruido". Los datos reales tienen:
- Missing NOT at random (los pacientes graves abandonan mas)
- Measurement error diferencial (self-report de fumadores subestima)
- Selection bias (solo ves los que sobrevivieron)
- Sesgo de publicacion (los estudios negativos no se publican)
- Definiciones inconsistentes (asma = diagnostico clinico O self-report O biomarcador)

**Estos problemas no son ruido — son amenazas sistematicas a la validez
que el investigador debe reconocer y manejar.**

#### 9. Las claims tienen tipo y peso

Un investigador no dice "la respuesta es 0.34". Dice:
- "Encontramos una asociacion moderada (OR 1.45, IC95% 1.12-1.88)"
- "La evidencia sugiere un efecto causal pero no podemos descartar confounding residual"
- "El efecto es robusto a 12 de 15 especificaciones alternativas"
- "Recomendamos un estudio experimental para confirmar"

**La claim tiene: tipo (causal/asociativa), fuerza, confianza, supuestos,
limitaciones, y recomendaciones. No es un numero — es un argumento.**

#### 10. El problema no viene pre-formulado

Un benchmark te dice "responde estas 5 preguntas". Un investigador empieza con:
- "Los arrecifes se estan muriendo. ¿Por que?"
- "La mortalidad infantil es alta en esta region. ¿Que factores son modificables?"
- "Este material falla bajo estrés térmico. ¿Como lo mejoramos?"

**Elegir QUE preguntar es parte del trabajo cientifico. A veces la pregunta
original no es la correcta y el investigador la redefine durante el proceso.**

---

## Que puede hacer SREG HOY vs que deberia hacer

| Patron | SREG v1 | SREG v2 (propuesto) |
|--------|---------|-------------------|
| 1. Multi-fuente | 1 CSV, 80 filas | 2-3 artifacts, 500-5000 filas |
| 2. Identificacion | No evaluada | Evaluar eleccion analitica |
| 3. Sensitivity | No existe | Requerir robustez como parte del eval |
| 4. Restricciones | Budget generico | Restricciones por tipo de investigacion |
| 5. Framing | 1 respuesta correcta | Multiples respuestas defensibles |
| 6. Secuencial | Acciones atomicas | Resultado informa siguiente paso |
| 7. Producir evidencia | Revelar variables | Comisionar estudios/experimentos |
| 8. Datos problematicos | Sampling limpio | Noise, MNAR, selection bias |
| 9. Claims tipadas | Distribucion exacta | Direccion + fuerza + confianza |
| 10. Problema abierto | 5 preguntas fijas | Brief general + claims libres |

---

## Papers analizados

| Dominio | Paper | Tipo de investigacion | Lo que lo hace real |
|---------|-------|----------------------|-------------------|
| Epidemiologia | Pedersen et al. (asma + contaminacion, 1M sujetos) | Cohorte observacional | 7 registros, modelos de exposicion, 3 cohortes |
| Ecologia | Hughes et al. (coral bleaching, GBR) | Survey de campo + satelite | 1000+ arrecifes, multi-año, escala continental |
| Clinica | RECOVERY trial (dexamethasone, COVID) | RCT multicentro | 6425 pacientes, subgrupos con efectos opuestos |
| Educacion | Jackson et al. (school funding) | Cuasi-experimental | Court-ordered reforms como variacion exogena |
| Materiales | High-entropy alloys (BO-guided) | Lab experimental | Optimizacion Bayesiana secuencial, 20 composiciones |
| Economia | Card & Krueger (minimum wage) | Experimento natural | DiD entre New Jersey y Pennsylvania |
| Ecologia | Biodiversity-productivity | Causal inference observacional | IV + negative controls en datos ecologicos |

---

## Implicaciones para el roadmap

**Prioridad 1:** Datos mas ricos y realistas (patron 1, 8)
- Multi-artifact DataSampler
- Noise, missingness MNAR, metadata de proveniencia

**Prioridad 2:** Acciones realistas (patron 4, 6, 7)
- Restricciones por dominio/tipo de investigacion
- Acciones que producen artifacts, no verdad
- Secuencialidad (resultado de accion A informa accion B)

**Prioridad 3:** Evaluacion mas rica (patron 2, 3, 5, 9)
- Claims estructuradas (no distribuciones exactas)
- Evaluar robustez (sensitivity analysis)
- Evaluar defensibilidad de elecciones analiticas

**Prioridad 4:** Problema abierto (patron 10)
- Brief general en vez de preguntas fijas
- El agente elige que investigar

Ver `docs/SREG_V2_DESIGN.md` para el plan de implementacion detallado.
