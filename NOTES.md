# NOTES — Inbox de ideas del usuario

> **Que es esto:** bloc de notas libre para volcar ideas, problemas, preguntas
> abiertas, criticas o cosas para pensar. No tiene formato fijo. En cada sesion
> de trabajo, estas notas se procesan: lo que sea research va a `research/`,
> lo que sea conclusion a `synthesis/`, lo que sea trabajo a `TODO.md`.
>
> **Regla:** una vez procesado, el item se mueve o se borra de aca. Este archivo
> no deberia crecer indefinidamente — es un inbox, no un archivo.

---

## Problemas a investigar / repensar

### El solver responde sin investigar

El solver responde de una sin hacer investigacion porque ya tiene todo.
Puede ser porque es muy facil lo que le damos, o porque al ser cosas
"realistas" ya sabe teoria el modelo, o porque los tasks estan mal y no
requieren investigacion.

**Conclusion parcial:** no es granularidad, no es nombres. Es **AMBIGUEDAD
MECANISTICA**. Un SRC requiere investigacion cuando:

1. Multiples explicaciones son semanticamente plausibles desde la narrativa
2. Esas explicaciones implican patrones observables diferentes
3. Solo los datos del episodio pueden resolver cual es correcta

No es un problema de nombres, ni de granularidad, ni de formato de datos.
Es de diseno del CASO: hay competencia real entre explicaciones?

> **Estado:** esto ya es casi una conclusion — candidato a `research/synthesis/`.

### Narrativa generica vs realista

Repensar si hay que hacer todo con nombres genericos. Incluso inventar
teoria sobre cosas irreales. Esto es porque quizas no queremos hacerlo
fiel a la realidad porque ahi el modelo que se entrene va a mezclar cosas
de la realidad con lo nuestro que tiene partes inventadas. Eso no esta
bueno. Entonces quizas sea mejor sacarle todo lo "real like" y hacerlo
bien generico, y que aprenda el core de investigacion. Pero esto es para
analizar y quizas para probar, manteniendo lo otro como otra version.

**Miedo concreto:** si usamos cosas basadas en la realidad, despues cuando
una AI se entrene usando estos mundos, se confunda porque van a ser cosas
parecidas a la realidad pero los mecanismos van a ser inventados, entonces
sea para peor.

**Posible solucion:** hacer opcional los nombres semanticos? Pero que
pasaria con la "historia" en general?

> **Estado:** pregunta abierta, necesita analisis y posiblemente experimento.
> Relacionado con la tension estrategica en PROJECT.md ("Semantica realista
> vs semantica abstracta").

### Que tipo de preguntas cientificas / tasks hacer?

Pedir tareas mas complejas. Por ejemplo que ayude a predecir algo, o darle
algo no tan armado, mas vago, y que ayude a plantearlo. Inspirado en QUE
SE PIDE COMO TAREA CIENTIFICA.

Inspirarnos en los que hacen envs con muchas preguntas y tipo rl agentico
para ver que tipos de preguntas y evaluaciones le hacemos, tanto
verificables como rubricas. Ver como entrenan Kimi o algunos de los
proyectos que crean tasks para rl long horizon o basado en papers como
Research Gym.

Como se hacen todos estos? Que metricas evaluan? Como? Como se hace en
agentic behavior en general?

Referencia: https://x.com/askalphaxiv/status/2030765298723283424

**Direccion:** pasar a que sea mas como Research Gym. Usarlo de referencia.
Que el LLM tenga un rol mas importante en el diseno del mundo y en la
seleccion de las tareas y subtasks a evaluar.

> **Estado:** pregunta abierta + referencia externa a investigar.

### Preguntas vagas y plan de investigacion

Entrenar la capacidad de armar un PLAN DE INVESTIGACION a partir de
preguntas vagas o abiertas.

> **Estado:** idea cruda, por explorar.

### Solo data-driven u otros tipos de investigacion?

Sirve esto? Para que casos? Porque quizas no generaliza. La gracia de
hacer investigacion no es hacer solo un juego de descubrimiento abstracto
de una realidad sino atarse a la realidad posta porque asi podes leer
papers, leer teoria que otro ya descubrio, etc. Y a partir de eso generar
modelos. Si no, es solo con los datos que hay que descubrir.

Habria que pensar si esto solo mejora data-driven pero pierde toda la
parte de deep research / literature.

**Critica importante:** si SREG se queda solo en "descubrimiento desde
datasets sinteticos", corre el riesgo de volverse demasiado data-driven y
perder una parte central de la investigacion real, que es leer teoria
previa, papers, hipotesis existentes y resultados contradictorios.

**Posible solucion:** enriquecer el research case con una segunda capa
visible: ademas de datasets y observaciones, el case deberia poder incluir
literatura previa, hipotesis historicas, papers/resumenes/notas tecnicas
inspiradas en casos reales. El agente entonces no solo razona sobre datos,
sino tambien sobre teoria previa, y tiene que decidir cuando seguirla,
cuando contrastarla y cuando refutarla.

El mundo formal sigue siendo la fuente de verdad verificable, pero el case
visible deberia evolucionar hacia **data + theory + literature**, no solo
data.

> **Estado:** critica fuerte, necesita discusion y posiblemente cambio en
> PROJECT.md. Relacionado con "Teoria inventada" abajo.

### Teoria inventada

Como se podria armar teoria inventada para replicar lo que seria buscar
papers o teoria general?

**Respuesta:** si, pero la teoria previa tambien la inventas, igual que
inventas el mundo. La clave: no inventas teoria arbitraria suelta. Inventas
teoria previa **derivada parcialmente del mundo verdadero**, pero de forma
**incompleta, sesgada o limitada**, como pasa en la realidad.

Estructura:

1. **Mundo verdadero oculto** — la BN / mecanismo real
2. **Literatura previa visible** — papers ficticios, hipotesis previas,
   reportes, "hallazgos historicos"

Pero esa literatura:
- no ve todo,
- puede haber estudiado solo una parte del fenomeno,
- o incluso puede estar equivocada.

**Ejemplo:** mundo verdadero dice que el declive lo causa un compuesto en
sedimentos + temperatura secundaria. Literatura ficticia: Paper 1 dice
"temperatura explica todo", Paper 2 dice "nitrogeno correlaciona", Nota
tecnica dice "se sospecha factor no medido en sedimentos". El agente
recibe datos nuevos + teoria previa, y tiene que usar la literatura como
prior, ver que parte parece correcta, y actualizar con evidencia nueva.

La teoria previa seria **un view parcial del mundo verdadero**, no una
verdad absoluta.

> **Estado:** idea bastante madura. Candidato a `research/synthesis/` o
> incluso a influir `PROJECT.md` (seccion "Hacia donde va SREG").

### Tipos de preguntas cientificas que nos faltan (hallazgo de inspiration reports)

Analizamos los 7 inspiration reports (2026-03-16) y encontramos que los
papers reales hacen preguntas que nuestros 9 eval types no pueden
representar. El orchestrator las fuerza en nuestros tipos y pierde lo
mas interesante.

**1. Mediacion — "por que camino llega el efecto?"**

No es solo "X causa Y?" sino "X causa Y *a traves de* Z?". Ejemplo:
el stress laboral aumenta el alcohol, pero... es porque la gente se
deprime? o porque usa coping evitativo? Saber por cual camino llega
el efecto cambia que intervencion haces.

**2. Modificacion de efecto — "para quien es diferente?"**

No es "X causa Y?" sino "X causa Y *mas* en un grupo que en otro?".
Ejemplo: el calor blanquea los corales, pero los ramificados sufren
mas que los masivos? Los arrecifes profundos resisten mejor?

**3. Evaluacion de sesgo de seleccion — "esto es real o es un espejismo?"**

Ejemplo: las escuelas privadas parecen mejores. Pero es porque ensenan
mejor? O es porque las familias ricas mandan a sus hijos ahi? Si no
pensas en seleccion, te enganas.

**4. Efectos heterogeneos — "funciona igual para todos?"**

Ejemplo: el programa anti-pobreza sube ingresos. Pero funciona igual
donde el 80% recibio el programa que donde solo el 10%? Quizas hay
spillovers.

**5. Atribucion de fuente — "de donde viene esto?"**

Ejemplo: hay metales pesados en los cultivos. Pero vienen del agua?
Del fertilizante? De la fabrica cercana? No es "que causa que?" sino
"cual de las multiples fuentes posibles es la dominante?".

**Patron comun:** no son preguntas que se responden con un numero o una
distribucion. Son preguntas sobre *estructura* — por que camino, para
quien, de donde viene, es real o es un artefacto. Nuestros 9 eval types
tienden a pedir "cual es el valor de X?" o "que variable conviene medir?".

**Tambien:** falta un seed de Vaca Muerta (el que se uso, causal_observational.pdf,
es un paper de epidemiologia estadistica sobre negative controls, no tiene nada
que ver con oil & gas). Crear el .md.

> **Estado:** hallazgo concreto de los inspiration reports. Candidato a
> research/synthesis/ y a TODO.md como nuevos eval types a disenar.

---

## Para implementar

- Categorizacion / taxonomia / dimensiones de lo que tienen las investigaciones
- BN con numericas y mas complejos
- Datasets realistas e inputs realistas
- Solver actions: experimentos cientificos (inspirados en papers reales seed)
- crear nuevas preguntas de investigacion para SRC -> porque hay pocas ahora y no captura la complejidad de tareas que hay en papers


## Otras

- Repasar el tema de evaluaciones y validaciones que se hicieron en su
  momento pero quedaron en la nada y sin uso (QualitySuite, diagnostics, etc)