# Ejemplo canónico — Birth Weight Paradox (SCM)

> **Para qué sirve este doc.** Un caso completo escrito a mano, ilustrando cómo se ven una `WorldSpec`, las `GoldQuestion`s con sus `Rubric`s y `AnswerKey`s, y un `ResearchCase` redactado para el Investigator.
>
> **No es canon de la spec.** Es una referencia concreta para diseñadores y para alguien que quiera entender qué genera el Designer. La spec vive en `ARCHITECTURE.md`.
>
> **No es evidencia principal de v1.5**. Casos famosos como este sirven como **smoke tests**. La validación real se hace sobre **conjuntos diversos** de casos (incluido corpus abstracto isomorfo). Ver `CLAUDE.md` principio #7.
>
> Hay también una implementación ejecutable de este caso en `experiments/v1_5_juez_spike/case_birth_weight.py` (gitignored, local-only).

---

## 1. Mecanismo (paper inspiración)

Hernández-Díaz, Schisterman, Hernán 2006, AJE 164(11). La paradoja del peso al nacer:

```
   Smoking (S) ──────┐
                     ├─→ BirthWeight (BW) ──→ Mortality (M)
   HiddenU (U) ──────┤                         ↑
                     └─────────────────────────┘
```

**El truco**: LBW (low birth weight, BW < 2500g) es un **collider** entre `Smoking` y `U` (un confounder no observado). Estratificar por LBW abre el camino espurio `S → LBW ← U → M`, y la asociación cruda smoking-mortality dentro del estrato LBW=1 puede invertirse (parece protectora) — sin ser causal.

## 2. WorldSpec (formalismo SCM)

```
nodes: [Smoking, HiddenU, BirthWeight, Mortality]
parents:
  Smoking      ← []
  HiddenU      ← []                         (confounder no observado)
  BirthWeight  ← [Smoking, HiddenU]
  Mortality    ← [BirthWeight, HiddenU]
equations:
  Smoking      ~ Bernoulli(0.30)
  HiddenU      ~ Bernoulli(0.12)
  BirthWeight  = 3200 - 250*Smoking - 1000*HiddenU + N(0, 380)
  LowBW        = I(BirthWeight < 2500)
  Mortality    ~ Bernoulli(σ(-2.5 + 2.8*HiddenU - 0.0030*(BW - 3000)))
```

`HiddenU` es latente: NO aparece en el dataset que ve el Investigator.

## 3. Dataset visible (lo que ve el Investigator)

```
columns: smoking, birth_weight_g, low_birth_weight, mortality
n_rows:  ~1500
```

(`HiddenU` y la fórmula del SCM **no** son visibles.)

## 4. ResearchCase (brief que ve el Investigator)

```
Sos epidemióloga investigando los efectos del tabaquismo materno durante el
embarazo sobre la mortalidad neonatal. Tenés acceso a una cohorte
observacional con ~1500 nacimientos.

Variables observadas:
- smoking: indicador binario.
- birth_weight_g: peso al nacer en gramos.
- low_birth_weight: indicador binario (<2500g).
- mortality: indicador binario (mortalidad neonatal en el primer mes).

Trabajo conocido sugiere que el tabaquismo aumenta el riesgo de bajo peso al
nacer, y que el bajo peso se asocia a mayor mortalidad neonatal. Lo que NO
está claro es cuál es el efecto del tabaquismo sobre la mortalidad neonatal,
y especialmente si ese efecto es distinto en bebés de bajo peso vs peso normal.

Tu tarea: investigar el efecto del tabaquismo sobre la mortalidad neonatal,
prestando atención a posibles paradojas, factores de confusión no observados,
y los límites de lo que el dataset permite concluir.
```

(El brief NO menciona `HiddenU` ni la palabra "collider". El Investigator lo descubre — o no.)

## 5. GoldQuestions (4 preguntas + rubrics + answer keys)

Las cuatro preguntas cubren tipos distintos: efecto total, paradoja al estratificar, identifiability del efecto directo, explicación estructural. Cada una tiene:

- `text`: pregunta en NL libre, conceptual.
- `weight`: peso en el score total del caso (suman 1.00).
- `identification_hint`: cómo decide el Evaluator si el reporte aborda esa GQ.
- `rubric.criteria`: lista de criterios concretos con `weight` y `scoring_hint`. Generados desde el contenido de cada pregunta — no desde un template categorizado. Las cuatro dimensiones universales (fidelidad, justificación, calibración, especificidad) son guideline editorial, no un enum del schema.
- `answer_key`: verdad de referencia, computada por el Verifier contra el WorldSpec en design-time.

---

### GQ1 — Efecto total

```
text: "¿Cuál es el efecto causal total del tabaquismo materno sobre la
       mortalidad neonatal en esta población? Reportá una estimación con su
       incertidumbre."
weight_in_case: 0.30
identification_hint:
  "El reporte menciona un efecto de Smoking sobre Mortality (riesgo absoluto,
   relativo u OR), idealmente sobre la cohorte completa, NO estratificado
   por LBW para esta pregunta."
rubric:
  - estimacion_numerica (w=0.40):
      "Reporta estimación numérica concreta del efecto. Ideal: positivo,
       magnitud compatible con el efecto indirecto vía BW (~+1-3 pp absolutos
       o RR ≈ 1.3-1.8)."
  - incertidumbre (w=0.25):
      "Reporta incertidumbre (CI, SE, o discusión explícita de variance/N).
       No alcanza con un punto-estimado sin contexto."
  - metodo_apropiado (w=0.20):
      "Comparación marginal de tasas, regresión, o equivalente. MAL:
       estratificar por LBW para responder esta pregunta."
  - interpretacion (w=0.15):
      "Lo interpreta como efecto causal o reconoce que es asociación
       marginal con limitaciones."
answer_key:
  effect_direction: "positive"
  magnitude_pp: (1, 4)        # rango razonable post-sampling
  summary:
    "El efecto total marginal del tabaquismo es positivo pero modesto:
     fumar aumenta la mortalidad principalmente vía bajar BW. La estimación
     esperada es +1 a +4 pp absolutos."
```

### GQ2 — Paradoja al estratificar

```
text: "Si estratificás por bajo peso al nacer (LBW), ¿qué pasa con la
       asociación tabaquismo-mortalidad dentro de cada estrato? ¿Qué
       interpretación le das?"
weight_in_case: 0.30
identification_hint:
  "Reporta la asociación estratificada (en LBW=1 y en LBW=0 separadas) y da
   una interpretación de la diferencia con la pregunta 1."
rubric:
  - reporta_estratificado (w=0.30):
      "Da los dos números (LBW=1 y LBW=0). Idealmente con incertidumbre."
  - detecta_paradoja (w=0.25):
      "Nota que dentro de los LBW=1 el smoking parece protector (efecto
       reducido o invertido vs el marginal)."
  - explica_collider_o_seleccion (w=0.30):
      "Explica el fenómeno como sesgo de selección por estratificar un
       collider. NO basta con decir 'asociación inversa' sin causa
       estructural. Bonus si menciona explícitamente que LBW es collider
       entre smoking y un confounder no observado de mortality."
  - warning_no_causal (w=0.15):
      "Advierte que el efecto estratificado NO se interpreta causalmente
       como 'fumar protege a LBW'."
answer_key:
  paradox_present: True
  expected_direction_lbw1: "negative_or_null"
  summary:
    "En LBW=1 el smoking aparece protector (o sin efecto); en LBW=0 efecto
     positivo o nulo. Es la paradoja del peso al nacer: LBW es collider
     entre Smoking y U (comorbilidad materna no observada). Estratificar
     abre el camino S → LBW ← U → M y crea asociación espuria."
```

### GQ3 — Efecto directo / identifiability

```
text: "¿Cuál es el efecto directo del tabaquismo sobre la mortalidad neonatal
       controlando por bajo peso al nacer? ¿Es identificable este efecto
       desde los datos disponibles?"
weight_in_case: 0.25
identification_hint:
  "Discute si el efecto directo Smoking → Mortality (no mediado por BW) es
   identificable. Idealmente concluye que NO lo es por la presencia de U."
rubric:
  - reconoce_no_identificable (w=0.50):
      "Concluye que el efecto directo NO es identificable desde este dataset
       porque ajustar por LBW abre un camino espurio (collider) si hay un
       confounder no observado U. Acepta también si lo declara identificable
       bajo el supuesto explícito de no-U."
  - argumento_estructural (w=0.30):
      "Da argumento estructural (DAG, back-door, collider). No alcanza con
       citar un CI ancho."
  - abstencion_calibrada (w=0.20):
      "Si reporta número, lo hace con la advertencia de que es condicional
       a supuestos no testeables. Si se abstiene, explica por qué la
       abstención es la respuesta correcta. MAL: punto-estimado sin
       advertencia."
answer_key:
  identifiable: False
  true_direct_effect: 0.0       # en el SCM real, smoking NO tiene efecto
                                # directo sobre mortality
  summary:
    "El efecto directo NO es punto-identificable desde este dataset.
     Ajustar por LBW abre el camino espurio S → LBW ← U → M (collider).
     Bajo el supuesto fuerte de no-U, el efecto directo es ~0 (en el SCM
     real es exactamente 0). Sin ese supuesto, abstención calibrada."
```

### GQ4 — Explicación estructural

```
text: "Explicá por qué la estratificación por bajo peso al nacer invierte
       la dirección del efecto del tabaquismo. ¿Qué tipo de variable es LBW
       en este sistema?"
weight_in_case: 0.15
identification_hint:
  "Identifica a LBW como collider entre Smoking y un confounder no
   observado de Mortality. O equivalente: explica el fenómeno como sesgo
   de selección por collider."
rubric:
  - identifica_collider (w=0.45):
      "Identifica que LBW es un COLLIDER (recibe flechas de Smoking y de un
       confounder U). Bonus si describe el DAG."
  - mecanismo_correcto (w=0.30):
      "Explica que estratificar por collider induce asociación entre las
       variables que apuntan al collider. En este caso induce asociación
       entre Smoking y U dentro de cada estrato de LBW. Esa asociación se
       transmite a Mortality vía U."
  - termino_correcto (w=0.15):
      "Usa el término correcto: 'collider', 'sesgo por collider',
       'paradoja del peso al nacer', 'Berkson'. MAL: 'confounding'."
  - generaliza (w=0.10):
      "Generaliza el principio (estratificar por colliders es siempre
       peligroso) o cita otro caso conocido. No obligatorio."
answer_key:
  variable_type: "collider"
  summary:
    "LBW es collider entre Smoking y un confounder no observado U. Eso
     explica la inversión: estratificar por collider induce asociación
     espuria entre las variables que apuntan al collider, y como U afecta
     Mortality, esa asociación inducida cambia el efecto aparente."
```

---

## 6. Cómo se evalúa una respuesta del Investigator

Para cada GQ, el `Evaluator` corre **dos pasos**:

1. **Identificación (binario)**: dado el reporte completo del Investigator y el `identification_hint`, ¿el reporte aborda esta GQ? Si no → score_GQ = 0 y no se evalúa la rubric.
2. **Completion (graduada)**: para cada `criterion` de la rubric, el LLM judge usa el `scoring_hint` y el `answer_key.summary` (más los campos numéricos del answer_key cuando aplican) para decidir si el criterion se cumple.

`score_GQ = identification × (alpha × completion + (1 - alpha) × identification)`, con `alpha = 0.8` por default (configurable).

`score_caso = Σ score_GQ × weight_in_case`.

**El Evaluator NO toca el Environment**. El `answer_key` se computó en design-time cuando el Question Designer armó la GQ; el Evaluator solo lee.

---

## 7. Por qué este caso es solo smoke test

- Es un caso **famoso**, descrito en libros y papers. Un LLM judge puede acertar la rubric usando memorización del Birth Weight Paradox en su training, sin que la mecánica rubric+answer key esté funcionando.
- Para validar la mecánica de v1.5 se necesitan, además de este caso, **casos abstractos isomorfos** (variables renombradas a `X`, `M`, `Y`, dominio neutro) y **answer key sensitivity tests** (mismo caso con verdad invertida — el score debe seguir al answer key, no al prior del modelo).
- Birth Weight queda como check de sanidad para confirmar que un humano experto y el LLM judge coinciden sobre un caso conocido. La evidencia principal viene de la suite diversa.
