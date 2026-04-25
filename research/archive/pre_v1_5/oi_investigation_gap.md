# Investigation Gap: Data-Indexed Worlds for OI

> **Fecha:** 2026-03-28
> **Contexto:** Sesiones 10-11 del autoresearch (branch autoresearch-open-investigation)
> **Codex thread:** 019d3338-e69f-7483-863e-05590cd3f65c

## El problema (A17 + A1 + LA PREGUNTA)

Si un LLM puede responder correctamente las sub-preguntas de un mundo
SIN ver los datos, el mundo no fuerza investigacion. Esto es el problema
central de LA PREGUNTA: "por que esto todavia no es una investigacion real?"

## Metrica: investigation_gap

```
investigation_gap = score_with_data - score_no_data
```

- **gap > 0**: el mundo FUERZA investigacion (los datos son necesarios)
- **gap ~ 0**: el mundo se responde desde priors (no fuerza investigacion)
- **gap < 0**: el mundo CONFUNDE al investigador (posible, pero raro)

### Protocolo del no-data baseline probe

1. Darle al solver el brief + nombres de variables (NO datos)
2. Pedirle 3-5 claims basados en conocimiento de dominio
3. Compilar y scorear con el mismo pipeline que el solver real
4. Comparar contra el score del solver con datos

Script: `scripts/oi_nodata_baseline.py`

## Resultados (6 mundos, 2026-03-28)

| Mundo | v2 no-data | v2 con datos | v2 gap | Fuerza investigacion? |
|-------|------------|--------------|--------|----------------------|
| ecosystem | 0.236 | 0.806 | **+0.570** | SI |
| productivity | 0.250 | 0.738 | **+0.488** | SI |
| screen_time | 0.400 | 0.750 | **+0.350** | SI |
| treatment_simpson | 0.606 | 0.738 | **+0.132** | SI (moderado) |
| treatment | 0.674 | 0.581 | -0.093 | NO |
| education | 0.766 | 0.766 | 0.000 | NO |

### Detalle SQ scoring

| Mundo | SQ no-data | SQ con datos | SQ correctness no-data | SQ correctness con datos |
|-------|------------|--------------|------------------------|--------------------------|
| productivity | 0.167 | 0.553 | **0.000** | **1.000** |
| screen_time | 0.542 | 0.661 | 1.000 | 1.000 |
| treatment_simpson | 0.580 | 0.622 | 0.750 | 1.000 |

## Que hace que un mundo sea data-indexed?

Un mundo es data-indexed cuando los priors del LLM son **incorrectos** sobre
algun aspecto verificable del mundo. Tres patrones identificados:

### 1. Efecto supresor (productivity world)

**Mecanismo:** Una tercera variable (Team_size) SUPRIME la relacion entre
Training y Productivity. El efecto directo (Training -> Prod, positivo) se
cancela con el efecto indirecto (Team_size -> Training positivo, Team_size ->
Prod negativo).

- crude r(Training, Productivity) ~ 0 (near zero)
- partial r(Training, Productivity | Team_size) ~ 0.72 (strong positive)
- **Prior del LLM: "training mejora productividad" -> espera r positivo -> WRONG**

### 2. Confounding reversal (screen_time world)

**Mecanismo:** Parental_income confunde la relacion Screen_time -> Academic.
Income alta -> mas pantallas Y mejores notas. La asociacion cruda es POSITIVA
pero el efecto causal es NEGATIVO.

- crude r(Screen_time, Academic) ~ +0.56
- partial r(Screen_time, Academic | Income) ~ -0.44
- **Prior del LLM: "screen time perjudica academico" -> espera r negativo -> WRONG**

### 3. Simpson's paradox (treatment_simpson world)

**Mecanismo:** Severity confunde Treatment -> Recovery. Pacientes mas graves
reciben mas tratamiento Y tienen peor recovery. La asociacion cruda es NEGATIVA
pero el efecto causal es POSITIVO.

- crude r(Treatment, Recovery) ~ -0.64
- ATE(Treatment -> Recovery) = +0.4
- **Prior del LLM: "treatment ayuda recovery" -> espera r positivo -> WRONG para crude**

## Debate con Codex (Session 10, thread 019d3338)

### Preguntas de diseno (Q1-Q6)

- **Q1: Extender design_case o nuevo tool?** -> Extender (Option B). Razon:
  SQs son parte del diseno del caso, no un paso separado.
- **Q2: Cuantas SQs?** -> 4-6. Menos de 3 no cubren el espacio; mas de 7
  son dificiles de validar.
- **Q3: Validacion estricta o permisiva?** -> Estricta con repair loop.
  Si las SQs no pasan validacion, el LLM recibe feedback y reintenta.
- **Q4: Regimen epistemico?** -> Campo explicito (observational_only, mixed,
  experimental). Determina que patrones son validos.
- **Q5: Un solo CasePlan o separado?** -> Un solo CasePlan con campos
  opcionales (oi_sub_questions, epistemic_regime).

### Recomendacion post-no-data-baseline

Codex recomendo: "Si el no-data baseline confirma shortcut, movete a mundos
data-indexed inmediatamente." Patrones sugeridos: suppressor effect, ranking
inversion. -> Se implementaron productivity (suppressor) y screen_time (reversal).

## Implicaciones para el sistema

### investigation_gap como criterio de aceptacion

**Propuesta:** cada mundo curado o generado por el orchestrator debe pasar
un test de investigation_gap. Si gap < threshold (e.g., 0.15), el mundo se
rechaza o se redisena.

**Status:** Concepto validado. Falta implementar como gate formal en el pipeline.

### Mundos actuales no data-indexed (treatment, education)

Estos mundos siguen siendo utiles para testing del pipeline, pero NO son
buenos entornos de entrenamiento para RL — un solver puede responder bien
sin investigar. Opciones:
1. Redisenarlos con patrones counter-intuitive
2. Mantenerlos como test fixtures, no como training environments
3. Usar modos semanticos (fictional) para invalidar priors

### SQ scoring vs v2

El SQ scoring muestra gaps mas pequenos que v2 en algunos mundos. Posibles
causas:
- SQ matching es mas estricto (requiere patron + roles exactos)
- Algunos SQs triviales se satisfacen desde priors (sq3/sq4 de screen_time)
- El SQ scoring necesita SQs mas data-indexed para mostrar mejor gap

### Proximos pasos

1. Formalizar investigation_gap como test automatico
2. Mas patrones: collider bias, non-monotonic, ecological fallacy
3. Comparar SQs manuales vs orchestrator para mundos data-indexed
4. Decidir threshold de aceptacion (0.10? 0.15? 0.20?)
