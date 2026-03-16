# Hallazgos de trayectorias del solver (2026-03-15/16)

> Hallazgos empiricos de correr SRCs con el solver diagnostico.
> Informa TODO.md y decisiones de diseño en ARCHITECTURE.md.

## 5-SRC evaluation (2026-03-15)

5 dominios: oil&gas (Vaca Muerta), epidemiologia (smoking/birthweight),
salud ocupacional (alcohol/COVID HCW), ecologia marina (coral reef),
educacion (school performance).

**Resultados:**
- E2E funciona en los 5 dominios
- CPD directions correctas post-fix (smoking=heavy -> 97% preterm)
- Budget usado: 0/9, 0/5, 0/7, 6/9, 0/8 (solo coral reef investigo)
- Escala: 9-16 nodos (razonable)
- Narrativas relevantes y apropiadas por dominio
- Causal structure: 20-60% inspiracion (DAGs demasiado simples)

**Conclusion principal**: el solver uso 0 research_actions en 4/5 casos.
El agente responde desde el dataset sin investigar. "Es un benchmark causal
con wrappers realistas, pero NO un ambiente de investigacion" (Codex).

## 7-SRC evaluation (2026-03-16)

7 SRCs de papers reales SIN budget ni research_actions. El solver solo
tiene python_exec + think + submit.

**Patron claro:**
- Descriptive questions (infer_target): FUERZAN analisis de datos.
  El solver tiene que hacer value_counts/crosstabs. Scores GOOD.
- Causal questions (should_condition, adjustment_set): NO fuerzan analisis.
  El solver responde desde priors del dominio. A menudo WRONG.
- causal_effect: intermedio — a veces compara grupos (empirico shallow),
  a veces adivina desde priors.

**Conclusion**: si queremos forzar investigacion, las preguntas deben ser
DATA-INDEXED (su respuesta depende de los datos de este episodio). Las
preguntas STRUCTURAL-CAUSAL no fuerzan investigacion porque se responden
desde conocimiento de dominio.

## LOOP.1: ocultar variables — REVERTIDO

Se intento ocultar padres del target para forzar budget usage. Resultado:
el solver solo desbloqueaba columnas mecanicamente, sin investigar.
Creo un "data-unlock game" artificial, no investigacion real. REVERTIDO.

Conclusion: research_actions deberian comisionar NUEVOS datos, no revelar
datos ocultos.

## Implicacion para SREG

Separar dos objetivos:
1. Data-grounded empirical analysis (descriptivo, estimacion) — fuerza
   investigacion naturalmente
2. Causal structure reasoning (condicionar, confounders, mecanismo) — no
   fuerza investigacion, se responde desde priors

Solo el primero fuerza investigacion con el diseño actual.
