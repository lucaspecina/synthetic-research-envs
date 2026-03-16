# Research Seed

## Context

Interferencia por fracturación hidráulica y arenamiento en pozos padre de Vaca Muerta. El caso estudia por qué algunos pozos en producción sufren arenamiento después de operaciones en pozos hijo o PADs cercanos, mientras otros no. El input es un dataset de eventos de interferencia con variables operativas, geológicas, espaciales e históricas para cada par Pozo padre - PAD hijo. El objetivo no es solo predecir riesgo, sino entender qué factores explican el evento y encontrar la causa más probable del arenamiento.

## Variables of interest

- `Presion max (kg/cm2)`, `Presion PEM (kg/cm2)`, `ratio_Pmax_PEM`
- `Tiempo de produccion`, `Largo estimulado (m)`, `Propante [lbs/ft]`
- `Fluido Hijo [bbl/ft]`, `Distanciamiento entre PADS`
- `SH min (kg/cm2)`, `TVD RH`, `Inclinación de pozo`
- `Zona*`, `Nivel`, `flag_Nivel_medio_match_PADsum`
- `Coordenada x`, `Coordenada y`
- `HIST_riesgo_zona`, `HIST_riesgo_coordenadas`, `HIST_riesgo_nivelmedio`
- `HIST_count_pads_hijos`
- Variable objetivo: ocurrencia de arenamiento en el pozo padre
- Variable latente posible: susceptibilidad geomecánica no observada del pozo o de la formación

## Research questions

- ¿Qué factores explican que una interferencia derive en arenamiento en un pozo padre?
- Si cambiara el distanciamiento, el fluido bombeado o la presión máxima, ¿cómo cambiaría el riesgo de arenamiento?
- ¿Qué variables adicionales deberían medirse para identificar mejor la causa real del evento?

## Constraints

- Medium-high difficulty
- The case should feel like a real upstream oil & gas operational study
- Include observed variables, historical risk variables, and at least one latent geomechanical factor
- Focus on causal attribution, not only classification
- The generated case should preserve realistic relationships between pressure, distance, geology, and interference history