# Linear Gaussian BN — Hallazgos del prototipo

> Prototipo exploratorio 2026-03-18. NO implementado en SREG.
> Motivado por A8 en TODO.md.

---

## Que funciona en pgmpy (v1.0.0)

### Modelo y CPDs

```python
from pgmpy.models import LinearGaussianBayesianNetwork
from pgmpy.factors.continuous import LinearGaussianCPD

model = LinearGaussianBayesianNetwork([('A', 'B'), ('B', 'C'), ('A', 'C')])
cpd_a = LinearGaussianCPD('A', beta=[5.0], std=1.0)              # A ~ N(5, 1)
cpd_b = LinearGaussianCPD('B', beta=[2.0, 0.8], std=0.7, evidence=['A'])  # B|A
cpd_c = LinearGaussianCPD('C', beta=[1.0, 0.3, 0.6], std=0.5, evidence=['A', 'B'])
model.add_cpds(cpd_a, cpd_b, cpd_c)
# model.check_model() -> True
```

- `LinearGaussianCPD(var, beta=[intercept, coef1, coef2...], std=noise, evidence=[parents])`
- beta[0] = intercept, beta[1:] = coefficients for each parent
- std = standard deviation of the noise term
- Escala linealmente con padres: 6 padres = 7 betas, no 3^6=729 entries

### Sampling: FUNCIONA

```python
samples = model.simulate(500, seed=42)  # -> DataFrame con columnas A, B, C
```

Produce datos continuos realistas (normales, con correlaciones correctas).

### Inferencia: NO hay modulo en pgmpy

`CausalInference(model)` -> `NotImplementedError: only implemented for BayesianNetworks`
No existe `pgmpy.inference.continuous`.

### Inferencia analitica: TRIVIAL

Para Linear Gaussian, la joint es multivariada normal. Conditioning y
marginalization son algebra lineal:

```
P(C | A=a) = N(mu_c + Sigma_CA * Sigma_AA^-1 * (a - mu_a),
              Sigma_CC - Sigma_CA * Sigma_AA^-1 * Sigma_AC)
```

Verificado empiricamente: P(C|A=7) analitico = N(7.66, 0.43),
muestras filtradas A in [6.5,7.5] dan mean=7.54. Coincide.

### do-calculus: TRIVIAL

do(X=x) en Linear Gaussian = eliminar edges entrantes a X, fijar X=x,
recalcular la joint. Es lo mismo que conditioning PERO eliminando la
correlacion con los padres de X.

Verificado:
- P(C | B=8) = N(7.72, 0.29) — observacional, incluye info sobre A via B
- P(C | do(B=8)) = N(7.30, 0.34) — interventional, corta A->B
- Diferencia = confounding por A. Exacto.

### KL divergence: CLOSED-FORM

```python
KL(N(mu1,var1) || N(mu2,var2)) = 0.5 * (log(var2/var1) + var1/var2 + (mu1-mu2)^2/var2 - 1)
```

Para el ejemplo: KL(do || obs) = 0.319 nats. Una linea de codigo.

---

## Que hay que implementar nosotros

| Componente | pgmpy da | Nosotros |
|---|---|---|
| Modelo (crear, validar) | SI | — |
| CPDs (definir) | SI | — |
| Sampling | SI | — |
| Joint distribution | NO | Calcular Sigma de los CPDs (recursivo, O(n^2)) |
| Conditioning P(Y\|X=x) | NO | Gaussian conditioning formula |
| do-calculus P(Y\|do(X=x)) | NO | Eliminar edges + recondicionar |
| KL divergence | NO | Formula closed-form (1 linea) |
| d-separation | SI (networkx) | — |

**Esfuerzo estimado:** ~200-300 lineas de codigo para un `GaussianSolver`
equivalente al `ExactBayesSolver` actual.

---

## Que cambia en el stack completo (para migrar)

### Capa formal (world/)
- `cpd_gen.py`: generar betas + std en vez de CPD tables
- Edge strength -> coeficientes (0.8 = relacion fuerte, 0.1 = debil)
- Edge direction (positive/negative) -> signo del coeficiente
- MAX_PARENTS ya no es limitante (6 padres = 7 floats, no 729 entries)

### Teacher (solver/)
- Nuevo `GaussianSolver` con joint, conditioning, do-calculus
- Scoring: KL entre Gaussianas (closed-form) en vez de KL entre discretas

### Eval types
- `causal_effect`: P(Y|do(X=x)) devuelve N(mu, sigma) en vez de tabla
- `infer_target`: marginal/posterior es N(mu, sigma)
- `should_condition`, `adjustment_set`: d-separation no cambia (networkx)
- `best_intervention`: argmax sobre do(X=x) para un rango continuo
- NUEVOS posibles: regresion, correlacion, intervalos de confianza

### Datos / datasets
- Columnas continuas (temperatura: 37.2, VO2max: 52.1) en vez de discretas
- El solver haria regresion, correlacion, scatterplots en vez de crosstabs
- Mucho mas realista

### Prompts del solver
- Format de submission: `distribution={mean: X, std: Y}` en vez de `{low: 0.3, ...}`
- O podria pedir un intervalo de confianza

### Modelo mixto (CLG - futuro)
- pgmpy tiene `FunctionalCPD` (requiere pyro) — no ideal
- Mejor opcion: mantener nodos discretos como categoricos que condicionan
  los parametros de los nodos Gaussianos. Implementar nosotros.

---

## Decision pendiente

**Opcion A: Migrar todo a Gaussian.** Mas limpio, mas realista.
Rompe compatibilidad con todo lo actual.

**Opcion B: Agregar Gaussian como modo paralelo.** `World` puede ser
discreto o Gaussiano. Los dos coexisten. Mas trabajo pero no rompe nada.

**Opcion C: CLG mixto desde el principio.** Nodos discretos (tipo_lesion,
posicion) + continuos (temperatura, VO2max). Lo mas realista pero lo mas
complejo de implementar.

**Recomendacion:** empezar con Opcion B (Gaussian paralelo). Validar que
funciona end-to-end con un mini ejemplo. Despues decidir si migrar todo
o ir a CLG.
