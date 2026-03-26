Sí. Te dejo un texto en modo **memo de debate**, no como propuesta cerrada. Está escrito para pegarle a Claude Code y seguir pensando desde ahí.

---

# Memo de debate — Open Investigation en SREG

Este texto resume la discusión que venimos teniendo sobre cómo migrar SREG desde su estado actual, basado en un SCM como mundo subyacente y tareas más estructuradas/verificables, hacia una versión de **Open Investigation**. No es una decisión final ni una especificación cerrada. La idea es capturar bien la tensión del problema, las dudas reales, las alternativas que aparecieron y las intuiciones que surgieron, para seguir pensándolo con cuidado.

## Contexto: por qué aparece Open Investigation

Hoy SREG ya tiene una base fuerte: hay un mundo subyacente formal, y en particular un SCM, que funciona como verdad oculta contra la que se puede evaluar. Eso es muy valioso porque evita que la evaluación dependa solo de un judge narrativo o de impresiones blandas. En esa visión, la estructura causal real del sistema la define el generador, y la calidad de la investigación se mide por la brecha entre lo que el investigador cree y cómo funciona realmente el sistema【turn19file6】.

Pero al mismo tiempo, venimos sintiendo una limitación importante del esquema actual: muchas tareas se parecen más a un **examen** que a una investigación real. O sea, el solver recibe algo relativamente bien formulado, responde, y el sistema chequea si acertó. Eso sirve para muchas cosas, pero no captura bien lo que nos interesa de verdad: que el agente pueda recibir una consigna vaga, decidir qué subpreguntas abrir, cómo interpretar los datos, si reformular la pregunta, si pivotear, si distinguir entre explicaciones rivales, y si darse cuenta de que no puede concluir tanto como creía.

Ese punto además conversa perfecto con la anatomía del proyecto: una investigación real casi nunca arranca con una pregunta ya operable; parte del trabajo del investigador es justamente volverla más precisa, delimitarla o incluso reformularla【turn19file5】. Y en los docs aparece también algo muy importante: no hay un único “buen juicio investigativo” universal, porque lo que cuenta como buena investigación depende del tipo de ciencia que tengas enfrente【turn17file7】.

Entonces, Open Investigation aparece como intento de abrir la capa visible del entorno, sin perder el anclaje duro abajo.

## La intuición base del cambio

La imagen mental que venimos usando es esta.

Hoy SREG se parece a un profesor que le da al alumno preguntas relativamente específicas: “¿Cuál es el efecto de X sobre Y?”, “¿Qué importa más, A o B?”, “¿Cuál es el mecanismo?”. El alumno responde, y nosotros chequeamos contra el SCM.

Lo que queremos explorar ahora es otra cosa: darle al solver algo más parecido a una situación real de investigación. Por ejemplo: “Tenés datos de pozos en Vaca Muerta. Algunos se arenan, otros no. Investigá qué está pasando y qué se podría hacer.” Ahí ya no hay una única pregunta explícita ni un único camino obvio. El solver puede explorar, reformular, proponer hipótesis, descubrir que está mezclando dos fenómenos distintos, o incluso concluir que con esos datos no se puede identificar causalidad fuerte.

Y ahí aparece la pregunta dura de diseño:

**¿cómo mapeamos de “el razonamiento y la conclusión del solver son válidos” a “esto realmente sirve para responder la investigación”?**

Ese es el corazón del debate.

## La tensión central

La discusión fue girando alrededor de dos extremos, y enseguida se vio que ambos tienen problemas.

Un extremo sería **predefinir respuestas verdaderas** de antemano y ver si el solver, en el fondo, las encuentra. Esto tiene la ventaja obvia de que hay anclaje. No quedamos flotando en si el judge “compró” una narrativa. Pero tiene una contra muy fuerte: si predefinimos demasiado, corremos el riesgo de sesgar el entorno hacia una única forma de investigar. Y entonces Open Investigation se vuelve una ilusión. El solver puede terminar siendo premiado por reconstruir “la respuesta esperada” y penalizado por llegar a algo válido pero por otro camino.

El otro extremo sería hacer el mundo, generar una pregunta vaga, dejar que el solver investigue libremente y después evaluar post hoc lo que hizo, usando combinación de LLM judge y simulaciones o queries al mundo subyacente. Eso preserva mucha más apertura. Pero también tiene un riesgo evidente: el solver puede producir conclusiones correctas pero irrelevantes, o razonables localmente pero desconectadas del problema importante. Y si dependemos demasiado de un judge posterior, podemos terminar premiando cosas que “suenan a ciencia” más de lo que realmente hacen avanzar la investigación.

Entonces la sensación fue que ninguna de las dos versiones puras cierra del todo.

## La distinción que fue emergiendo: verdad local, relevancia global, calidad investigativa

Un avance conceptual importante de la charla fue separar tres planos que al principio estaban mezclados.

El primero es la **verdad local** de un claim. Por ejemplo: “hay dos regímenes”, “la presión tiene efecto positivo”, “esta política reduce el riesgo”, “con estos datos no se puede distinguir H1 de H2”. Ese tipo de afirmación, en principio, sí se puede mapear al mundo subyacente y verificar contra el SCM o contra otras estructuras latentes del entorno.

El segundo plano es la **relevancia global**. O sea: aunque algo sea cierto, ¿sirve para responder la investigación? Esta distinción nos empezó a parecer central. Porque un solver puede descubrir algo real y aun así no estar tocando el corazón del problema. Los docs lo dicen muy claramente con los red herrings: pueden ser patrones genuinos, que incluso resisten validación, pero no responden la pregunta【turn18file1】. Y también aparece como failure mode explícito: hacer cosas correctas y sofisticadas que no conectan con la pregunta principal【turn17file2】.

El tercer plano es la **calidad del proceso investigativo**. Acá entran ya cosas mucho más “AI scientist”: si eligió buenas subpreguntas, si mantuvo alternativas vivas, si pivotó cuando el progreso marginal cayó, si separó lo que venía del caso de lo que venía de sus priors, si buscó refutar su propia hipótesis, si siguió una línea solo porque sonaba bien o porque de verdad discriminaba entre hipótesis. Todo esto conversa directamente con el estado epistémico, el loop de juicio y los failure modes del proyecto【turn17file8】【turn17file9】【turn17file7】.

La sensación fue que Open Investigation probablemente obliga a separar estos tres planos si queremos que la evaluación tenga sentido.

## Una duda central: ¿qué conviene predefinir realmente?

Una cosa que fue apareciendo es que tal vez la pregunta no sea “¿predefinir respuestas sí o no?”, sino “¿qué exactamente predefinimos?”.

Porque parece bastante mala idea predefinir una frase o una conclusión canónica tipo “la respuesta correcta es X causa Y por Z”. Pero tampoco parece buena idea no predefinir nada.

Entonces empezó a aparecer otra intuición: quizá lo que conviene predefinir no son respuestas textuales, sino algo más abstracto, como el **espacio de descubrimientos posibles** que ese mundo permite.

Por ejemplo, en un mundo tipo arenamiento, quizás el entorno sabe de antemano que podrían ser hallazgos válidos cosas como:

* descubrir un efecto causal dominante,
* separar dos subtipos de fenómeno que estaban mezclados,
* mostrar que con el acceso observacional dado no se puede distinguir entre dos mecanismos,
* proponer una medición o experimento que sí los discriminaría,
* encontrar una política operativa útil aunque no cierre el mecanismo,
* o reformular la pregunta de una forma más discriminativa.

Acá la idea no era ya “predefinir una respuesta”, sino más bien **predefinir el espacio de hallazgos valiosos que ese mundo hace posibles**. Eso sigue siendo solo una idea de trabajo, no una conclusión cerrada, pero apareció varias veces como una posible salida elegante al dilema.

## Otra idea que apareció: no todo descubrimiento verdadero es relevante para todo brief

Ligado a lo anterior, apareció otra distinción que parece importante para Open Investigation.

Un mismo mundo puede permitir muchos descubrimientos verdaderos. Pero no todos son igual de útiles para cualquier investigación. Es decir, el mundo abajo puede ser el mismo, pero el brief arriba puede cambiar qué cuenta como “responder bien”.

Eso llevó a pensar si no haría falta algo así como un **contrato de relevancia** del brief. No una gold answer, sino una definición previa de qué familias de output serían consideradas avances realmente valiosos para esta investigación concreta.

Por ejemplo, en un brief tipo “investigá por qué se arenan los pozos y qué se podría hacer”, tal vez sería razonable decir que cuentan como buen progreso cosas como:

* una explicación causal plausible y bien sustentada,
* una separación en regímenes o subtipos,
* una política operativa útil,
* una delimitación honesta de lo que no se puede inferir,
* o la elección de la siguiente medición/experimento con mayor valor informativo.

Eso nos gustó porque evita dos problemas a la vez: no congela una sola respuesta, pero tampoco deja que cualquier claim correcto sume igual.

## El rol del judge / translator

Otra parte importante del debate fue el rol del LLM posterior.

La intuición que fue apareciendo es que el LLM posterior probablemente no debería ser “el juez supremo de si esto es verdad”, sino más bien un **traductor / compilador semántico** de lo que hizo el solver.

O sea: el solver investiga libremente y produce una trayectoria y un reporte. Después, otro modelo intenta extraer de ahí cosas como:

* cuál fue la pregunta activa real que terminó persiguiendo,
* qué subpreguntas abrió,
* qué claims hizo efectivamente,
* de qué tipo eran esos claims,
* con qué evidencia los sostenía,
* qué alternativas consideró,
* qué confianza expresó,
* qué siguiente paso propuso.

La verdad de esos claims no la decidiría el judge, sino el mundo subyacente. Esta intuición está muy alineada con la arquitectura que ya apunta a algo tipo `solver → translator → verifier`, donde el traductor media entre el reporte libre y el chequeo grounded【turn15file4】.

Lo que todavía no está resuelto es cuán ambicioso debería ser ese translator. No sabemos si debería mapear a una ontología muy pequeña y robusta, o a algo más rico y flexible. Tampoco está del todo claro qué tanto debería “entender intención” versus simplemente extraer afirmaciones más literales.

## Tipos de preguntas y tipos de output

Otra línea importante del debate fue darse cuenta de que no todo Open Investigation debería asumir el mismo tipo de investigación.

Los docs ya insisten en que hay muchos tipos de objetivo: descriptivo, causal, teórico, predictivo, diseño, exploración de espacio, etc., y que un caso real muchas veces pasa por varios en secuencia【turn19file5】. Además, la generación de hipótesis no siempre es lo central: en ciencia descriptiva, en optimización o en ingeniería, a veces lo importante es medir bien, representar bien, priorizar bien o construir bien【turn18file14】.

Eso llevó a pensar que una misma consigna vaga puede dar lugar a outputs muy distintos y aun así válidos. Por ejemplo:

* una explicación causal,
* una taxonomía de subtipos,
* una representación nueva del fenómeno,
* una regla predictiva útil,
* una política operativa,
* una reformulación de la pregunta,
* una conclusión de subidentificación,
* o una propuesta de experimento siguiente.

Y acá apareció un miedo concreto: si Open Investigation termina aceptando de verdad solo un tipo de output —por ejemplo, “explicación causal final”— entonces en la práctica vamos a estar castigando investigaciones buenas que fueron por otro carril.

Ese punto además se reforzó al pensar en distintos casos del Doc 4. Snow es causal observacional y su genialidad fue encontrar el natural experiment adecuado【turn19file11】【turn19file12】. Vaca Muerta mezcla objetivo predictivo y explicativo, con fuerte limitación observacional y muchas variables ocultas【turn19file17】【turn19file2】. Surfactantes con BO es optimización: ahí la gracia no es explicar, sino decidir bien el siguiente ensayo y balancear exploración/explotación【turn19file15】. AlphaFold directamente muestra un caso donde el output valioso es capacidad funcional más que explicación【turn19file4】【turn19file7】. Mendeleev enfatiza confianza en estructura【turn19file1】【turn19file18】. Einstein pone en el centro el reencuadre【turn19file8】. Todo eso nos empujó a pensar que Open Investigation va a necesitar tolerar variedad real de preguntas y outputs, no solo variaciones semánticas de la misma task causal.

## La preocupación por el sesgo al “camino del paper”

Esto también apareció fuerte: si un caso abierto termina siendo evaluado según si el solver reconstruyó el mismo camino que siguió un paper real, entonces no estamos evaluando investigación abierta sino reconstrucción histórica.

Y eso sería especialmente grave si queremos capturar creatividad investigativa: reencuadrar, perturbar supuestos, confiar en un patrón, buscar por estructura, priorizar por valor de información, etc. Los docs justo remarcan varias de esas capacidades como diferenciadoras, y muestran que distintos casos reales activan heurísticas muy distintas【turn18file3】【turn19file9】【turn19file13】.

Entonces apareció varias veces la idea de que Open Investigation debería permitir que el solver llegue a algo valioso **por otro camino**, siempre que ese camino esté bien apoyado y el resultado realmente reduzca la brecha con el mundo.

La duda que queda abierta es: ¿cómo hacemos para permitir eso sin que el sistema se vuelva demasiado permisivo?

## Cómo pensar las métricas más “soft”

Otra parte de la conversación fue mirar más a futuro y pensar que Open Investigation, si se diseña bien, podría abrir la puerta a evaluar cosas mucho más profundas que accuracy final.

Por ejemplo, **relevance grounding**. Si el solver hace cosas interesantes pero no conectadas con la pregunta, eso debería notarse. El loop de juicio del Doc 2 es muy claro en eso: antes de cada acción, el investigador debería reanclar su atención a la pregunta, revisar hipótesis vivas y justificar que su próxima acción realmente lo acerca al objetivo【turn17file8】【turn17file9】.

También **plan de investigación**. Los docs describen planificar como convertir una situación abierta en un plan con prioridades, descomponer el problema, delimitar scope y secuenciar con bifurcaciones, no simplemente listar pasos【turn17file11】【turn18file10】. Open Investigation podría permitir medir si el solver hizo eso bien.

También **pivoteo**. Si el progreso cayó a cero y siguió insistiendo, eso es mal score. Si detectó dead end y reformuló, eso debería sumar. Eso está mapeado muy explícitamente tanto en los failure modes como en el estado epistémico【turn17file2】【turn17file8】.

También **separar caso de priors**. Esto es especialmente importante en Vaca Muerta y en cualquier setting observacional: el doc de ARS lo pone como habilidad prioritaria número uno【turn19file3】. Un solver que ve datos del caso pero termina diciendo “en la literatura suele pasar X” no está investigando el caso; está recitando.

También **refutación activa**. No solo proponer una hipótesis, sino buscar activamente cómo destruirla. El Doc 3 lo presenta como diferencia entre storytelling y ciencia【turn17file10】.

La duda acá no es tanto si estas métricas importan. Importan muchísimo. La duda es más bien cómo instrumentarlas sin caer otra vez en puro judge narrativo.

## Una intuición recurrente: mundo cerrado abajo, apertura arriba

Sin quererlo, la conversación fue volviendo siempre a una misma imagen.

Por abajo, el mundo sigue siendo formal, cerrado, verificable, grounded. Ahí vive la verdad.

Por arriba, la investigación se vuelve más libre: preguntas vagas, subpreguntas elegidas por el solver, caminos distintos, outputs heterogéneos.

En el medio aparece una capa de traducción y otra de evaluación que todavía no están del todo diseñadas, pero que probablemente son las piezas clave.

Lo que no está resuelto es **cuánto** hay que preanclar abajo y **cuánto** dejar emerger arriba.

## Dudas abiertas que quedaron vivas

Quedaron varias preguntas sin resolver, y probablemente son las que más vale la pena seguir trabajando.

Una es si conviene pensar el preanclaje como “discoverable set”, como “relevance contract”, como ambos, o como otra cosa más general todavía.

Otra es cuánto debe mirar la evaluación al **output final** versus a la **trayectoria entera**. Porque hay un mundo en el que un solver llega a una buena conclusión por un proceso malo, y otro donde investiga muy bien pero no termina cerrando una conclusión fuerte. Todavía no está claro cómo balancear eso.

Otra es qué tan grande o chica debería ser la ontología de outputs canónicos. Si es muy chica, puede forzar demasiado. Si es muy grande, el translator puede volverse frágil.

Otra es cómo distinguir bien entre “claim correcto pero irrelevante” y “claim de soporte que sí era una pieza necesaria del camino”.

Otra es cómo hacer para que la evaluación no premie solo el hallazgo final, sino también la **elección correcta de la siguiente acción**. Esto parece muy importante para AI scientist real, pero todavía es menos obvio cómo aterrizarlo.

Y otra muy importante es cómo hacer que Open Investigation siga siendo suficientemente grounded y no se deslice hacia algo donde lo que manda sea solo la plausibilidad narrativa del reporte. Ese riesgo está recontra presente en los deficits del Doc 3: optimización por plausibilidad narrativa, ausencia de estado epistémico persistente y ausencia de función de valor de información【turn17file6】【turn17file7】.

## Sensación general de la discusión

La sensación general no fue “ya sabemos qué hacer”, sino más bien esta:

Queremos abrir SREG para que deje de parecerse tanto a un examen y se acerque más a una investigación real. Pero no queremos perder la gran virtud que ya tiene: un mundo subyacente conocido, formal y verificable.

Entonces el problema no es simplemente “abrir”. El problema real es **cómo abrir sin perder grounding**.

Y eso nos fue llevando a pensar que probablemente la respuesta no sea ni gold answers únicas, ni judge libre post hoc, sino alguna combinación más sutil entre:

* verdad preanclada en el mundo,
* posibilidad de múltiples rutas válidas,
* evaluación separada de verdad, relevancia y proceso,
* y una capa intermedia que traduzca lo que el solver hizo a algo que el mundo pueda chequear.

Pero eso todavía está en debate. No es una conclusión cerrada. Justamente lo que queremos es seguir pensándolo con ejemplos diversos, distintos tipos de preguntas y distintos tipos de output, para ver si SREG puede abarcar casi todos o al menos muchos de los modos reales de investigar.

---

Si querés, ahora te lo transformo en una segunda versión todavía más “Claude-friendly”, con tono más corto y directo, como prompt de continuidad tipo: “esto es lo que venimos debatiendo; ayudame a explorarlo”.
