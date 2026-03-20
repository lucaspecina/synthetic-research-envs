# Mediciones indirectas — senales proxy en el SCM

> Idea discutida 2026-03-20. Documentada para incorporar en el prompt del
> orchestrator cuando diseñe SCMs.

## El problema

En investigacion real casi nunca se miden las variables causales directamente.
El investigador recibe **senales proxy** — mediciones instrumentales que
reflejan las variables latentes de forma indirecta, ruidosa, y a veces
no lineal.

Ejemplo concreto (corrosion microbiologica en caños de petroleo):
- Variable causal real: biofilm, tasa de corrosion, pH, temperatura
- Lo que el investigador mide: impedancia EIS, potencial OCP, resistencia LPR

Otros ejemplos:
| Dominio | Variable latente | Señales observables |
|---------|-----------------|---------------------|
| Medicina | inflamacion | PCR, IL-6, leucocitos |
| Astronomia | composicion estelar | espectros de absorcion |
| Ecologia | salud ecosistema | biodiversidad, turbidez, clorofila |
| Geologia | actividad sismica | sismogramas, GPS |
| Neurociencia | actividad neuronal | fMRI, EEG, potenciales evocados |

## Solucion: ya lo tenemos en el SCM

**No necesitamos una capa nueva.** Las mediciones indirectas son simplemente
**nodos adicionales en el grafo** cuyas ecuaciones simulan la respuesta del
instrumento.

```
biofilm ----+
            +--> corrosion --+--> EIS_impedance
pH ---------+                +--> OCP_potential
temperature +                +--> LPR_resistance
```

- Los nodos internos (biofilm, corrosion) son **latentes** — no aparecen
  en el dataset.
- Los nodos hoja (EIS, OCP, LPR) son **observables** — el solver los ve.
- Las ecuaciones de los nodos hoja simulan la funcion de respuesta del
  instrumento: saturacion, no linealidad, ruido instrumental.

```python
equations = {
    "biofilm":        lambda p, rng: rng.lognormal(2, 0.5),
    "pH":             lambda p, rng: rng.normal(6.5, 0.8),
    "temperature":    lambda p, rng: rng.normal(40, 10),
    "corrosion":      lambda p, rng: (
        0.3 * p["biofilm"] + 0.1 * (7 - p["pH"])**2
        + 0.05 * max(p["temperature"] - 30, 0)
        + rng.normal(0, 0.5)
    ),
    # --- Mediciones instrumentales (lo que el solver ve) ---
    "EIS_impedance":  lambda p, rng: (
        1000 / (1 + p["corrosion"]) + rng.normal(0, 50)  # no lineal, saturacion
    ),
    "OCP_potential":  lambda p, rng: (
        -0.3 - 0.05 * p["corrosion"] + 0.02 * p["pH"]
        + rng.normal(0, 0.01)
    ),
    "LPR_resistance": lambda p, rng: (
        500 / (0.1 + p["corrosion"]) + rng.normal(0, 30)
    ),
}
```

## Que cambia para el orchestrator

El orchestrator, al diseñar un SCM inspirado por un paper, debe decidir:

1. **Que variables son latentes** (el investigador no las mide directamente).
2. **Que mediciones instrumentales existen** (nodos hoja observables).
3. **Que funcion de respuesta tiene cada instrumento** (ecuacion del nodo hoja).
4. **Cuales mediciones son mas directas** (pH_meter ~ pH) vs cuales son
   mas indirectas (EIS ~ f(corrosion, biofilm)).

Esto se incorpora en el prompt del orchestrator como parte del diseño del
caso. No requiere cambios en el engine SCM ni en el pipeline.

## Que cambia para el solver

El solver recibe datasets con columnas como `EIS_impedance`, `OCP_potential`,
etc. — NO ve `corrosion` directamente. Tiene que:

1. Entender que representan las señales.
2. Descubrir relaciones entre señales y fenomenos.
3. Razonar causalmente sobre variables que no observa directamente.

Esto es **exactamente** lo que hace un investigador real. Y el reward sigue
anclado al SCM — la verdad formal computa P(corrosion | do(X)) via Monte
Carlo sobre el grafo completo (incluidos los nodos latentes).

## Cuando implementar

- **No requiere cambios en SCMWorld** — ya soporta grafos con nodos latentes.
- **Requiere cambios en el orchestrator prompt** — que sepa diseñar mundos
  con mediciones indirectas.
- **Requiere que multi_dataset_sample sepa que nodos son observables** —
  hoy asume que todos lo son. Parametro `observable_nodes` en el futuro.
- **Prioridad:** incorporar cuando el orchestrator diseñe SCMs (Fase 3).
  Hasta entonces, documentado como patron de diseño.

## Conexion con LA PREGUNTA

> ¿Por que esto todavia no es una investigacion real?

Porque el solver ve las variables causales directamente. En investigacion
real, hay una capa de indirection entre el fenomeno y la medicion. Esta
nota documenta como resolverlo sin cambiar el engine — solo diseñando
grafos mas realistas.
