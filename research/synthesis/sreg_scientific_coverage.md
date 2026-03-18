# SREG Scientific Coverage Assessment

> **Que tipos de ciencia puede representar SREG hoy y cuales no.**
> Basado en el framework de `research/synthesis/scientific_research_taxonomy.md`.
> Actualizado: 2026-03-18

---

## Research Objectives — que puede generar SREG

### Clase A: Produce Conocimiento (output epistemico)

```
Explanatory/Causal  ████████░░  8/10  EL CORE DE SREG
Descriptive         ██████░░░░  6/10  infer_target + EDA con python_exec
Predictive          ████░░░░░░  4/10  infer_target, pero sin train/test split real
Methodological      ███░░░░░░░  3/10  should_condition toca esto; falta mucho
Space Exploration   ███░░░░░░░  3/10  el solver puede explorar, pero no hay eval type
Benchmarking        ██░░░░░░░░  2/10  compare_interventions es un mini-benchmark
Replication         ██░░░░░░░░  2/10  podria simularse (2 SRCs, mismo mundo); no impl.
Theoretical         █░░░░░░░░░  1/10  sin teoria inventada, sin frameworks formales
Synthesis           ░░░░░░░░░░  0/10  imposible — SREG genera datos primarios
Historical          ░░░░░░░░░░  0/10  imposible — sin temporalidad ni evidencia indirecta
```

### Clase B: Produce Capacidades (output funcional)

```
System Design       ░░░░░░░░░░  0/10  el solver no construye artefactos
Pure Predictive     ████░░░░░░  4/10  infer_target; sin generalizacion real
```

### Detalle por objetivo

**Explanatory/Causal (8/10)** — Lo mejor de SREG.
- `causal_effect`: P(Y|do(X)) con ground truth exacto
- `best_intervention`: cual do(X=x) maximiza Y
- `compare_interventions`: do(A) vs do(B)
- `should_condition`: condicionar en Z es correcto o introduce sesgo?
- `adjustment_set`: que variables controlar para estimar efecto causal
- `infer_latent_cause`: inferir variable oculta desde observables
- Falta: mediacion ("por que camino llega el efecto"), effect modification
  ("para quien es diferente"), mecanismo completo

**Descriptive/Measurement (6/10)**
- `infer_target` da una prediccion descriptiva del outcome
- El solver puede hacer EDA completa con python_exec (crosstabs, distribuciones,
  correlaciones, subgrupos)
- Falta: cuantificacion con incertidumbre, tipologia/clasificacion emergente,
  descripcion temporal/dinamica

**Methodological (3/10)**
- `should_condition` es una pregunta metodologica (controlar o no por Z)
- Pero no hay eval types para: diseño de estudio, evaluacion de protocolos,
  comparacion de metodos estadisticos, deteccion de sesgo de seleccion
- El solver PODRIA hacer sensibilidad o robustez con python_exec pero nada
  lo incentiva

**Space Exploration (3/10)**
- El solver puede explorar el espacio de variables libremente
- Pero no hay eval type que premie "descubrir estructura" o "encontrar regiones
  interesantes" — solo hay preguntas puntuales

**Theoretical (1/10)**
- No hay literatura inventada, ni hipotesis previas contradictorias, ni frameworks
  formales que el solver deba integrar o refutar
- Si se implementa I7 (teoria inventada), sube a ~5/10

---

## Research Axes — donde cae SREG

### Ejes fijos (SREG siempre cae aca)

| Eje | Valor SREG | Score | Que faltaria |
|---|---|---|---|
| Data vs Theory vs Literature | **100% data-driven** | Data:10 Theory:0 Lit:0 | I7 (teoria inventada) |
| Bottom-up vs Top-down | **100% bottom-up** | BU:10 TD:0 | Solver sin modelo previo |
| Empirical vs Formal | **100% empirico** | Emp:10 Formal:0 | — |
| Computational vs Experimental vs Obs | **100% observacional** | Comp:0 Exp:0 Obs:10 | Research actions futuras |
| Explicit vs Implicit ontology | **100% explicito** | Expl:10 Impl:0 | Variables continuas (A8) + discovery |
| Closed vs Open world | **100% closed** | Closed:10 Open:0 | Variables no dadas |
| Human-in-loop vs Automated | **100% automated** | Human:0 Auto:10 | — (es un solver, ok) |

### Ejes con algo de variacion

| Eje | Valor SREG | Score | Notas |
|---|---|---|---|
| Mechanistic vs Phenomenological | **~70% mechanistic** | Mech:7 Phenom:3 | El DAG ES mecanistico, pero el solver no lo ve directamente |
| Confirmatory vs Exploratory | **~80% exploratory** | Conf:2 Expl:8 | No hay hipotesis previa; todo es "explora y responde" |
| Simple vs Complex vs Hidden | **~mixed** | Simple:2 Complex:6 Hidden:7 | Las latentes son el diferenciador |
| Epistemic vs Functional | **~90% epistemic** | Epist:9 Func:1 | Casi todo es "aprende algo", no "construye algo" |
| Local vs Generalizable | **~70% local** | Local:7 Gen:3 | Cada SRC es un caso aislado |

### Ejes irrelevantes para SREG

| Eje | Por que no aplica |
|---|---|
| Wet lab vs Dry lab vs Field | Todo es dry lab por definicion |
| Incremental vs Disruptive | No aplica a un caso individual |
| Disciplinary vs Interdisciplinary | Depende del seed, no de SREG |
| Type of evidence (controlled/obs/simulated) | Siempre es simulated (pero se presenta como observational) |

---

## Workflows — que workflows puede simular SREG

```
Exploratory               ████████░░  8/10  LO QUE HACE HOY
Bayesian refinement       ███░░░░░░░  3/10  el solver podria iterar pero no hay incentivo
Build-test-iterate        ██░░░░░░░░  2/10  sin artefactos que construir
Hypothetico-deductive     ██░░░░░░░░  2/10  sin hipotesis previa que testear
Exploratory+confirmatory  ██░░░░░░░░  2/10  podria hacerse con 2 datasets separados
Multi-method              █░░░░░░░░░  1/10  solver tiene una sola herramienta (python)
Automated closed-loop     █░░░░░░░░░  1/10  sin loop de experimentacion
Longitudinal              ░░░░░░░░░░  0/10  sin temporalidad
Synthesis/meta-analytic   ░░░░░░░░░░  0/10  sin estudios previos que integrar
```

---

## Curriculum de complejidad (del framework scientific_research_taxonomy)

| Level | Descripcion | SREG hoy |
|---|---|---|
| 1 | Explicit ontology, simple/deterministic, closed world, causal objective | **SI** — SRCs simples con pocos nodos |
| 2 | + Stochasticity, confounders, noisy measurements | **SI** — CPDs con noise, missingness, confounders |
| 3 | + Hidden variables, implicit ontology parcial | **PARCIAL** — latentes SI, implicit ontology NO |
| 4 | High-dimensional implicit ontology, phenomenological, complex stochastic | **NO** — necesita variables continuas (A8) |
| 5 | Open world, hidden variables, multi-scale, mixed epistemic/functional | **NO** — necesita cambios fundamentales |

---

## Que ampliaria mas la cobertura (priorizado por impacto)

1. **Variables continuas (A8)** — Desbloquea niveles 4+, hace los datos realistas,
   habilita regresion/correlacion, elimina el cuello de botella de MAX_PARENTS.
   Impacto: Descriptive +2, Predictive +2, Space Exploration +2, ejes Implicit +5.

2. **Teoria inventada (A4/I7)** — Papers ficticios con hallazgos parciales o
   contradictorios. El solver tiene que integrar teoria + datos. Impacto:
   Theoretical +4, Theory-driven +5, Confirmatory +3.

3. **Nuevos eval types (I1)** — Mediacion, effect modification, subgroup effects.
   Impacto: Explanatory +1, Methodological +2.

4. **Research actions rediseniadas** — No observe/intervene de juguete, sino
   "diseñar experimento", "pedir campaña de datos", "consultar experto".
   Impacto: Experimental +5, Workflows (Bayesian, closed-loop) +4.

5. **Dos fases con datasets separados** — Exploratory en dataset A, confirmatory
   en dataset B. Impacto: Methodological +3, Workflows +3, Replication +3.

---

## Conclusion

SREG hoy es un generador de entornos de **causal inference observacional en
mundos discretos con ontologia explicita**. Es muy bueno en eso (~8/10) pero
cubre ~15% de los tipos de investigacion cientifica que existen.

Los dos cambios que mas ampliarian la cobertura son **variables continuas** y
**teoria inventada**. Sin ellos, SREG entrena un tipo muy especifico de
razonamiento cientifico — valioso, pero estrecho.
