"""Environment v1.5 — sustrato ejecutable de los WorldModels.

Define interfaces (`Protocol`) y adapters concretos. El Environment es
la "capa física" del sistema: sabe samplear, intervenir y simular.
Cualquier agente del Designer (Architect, Explorer/Designer, etc.) puede
escribir scripts Python que la usen en design-time, capturando el
resultado en `EvidenceArtifact` (ver `multi_explorer_redesign.md`).

Reglas:
- El Environment NO conoce a las GoldQuestions ni a las Rubrics.
- Los agentes del Designer llaman al Environment en design-time. NO se
  llama en runtime de evaluación.
- El Investigator NO ve el Environment directamente — solo recibe los
  `Dataset`s pre-sampleados que el Designer le metió en `ResearchCase`.
- NO existe un "Verifier" centralizado con catálogo cerrado de
  operaciones (eliminado en re-diseño multi-agente).
"""

from sreg.v1_5.environment.protocols import (
    BaseEnvironment,
    ODEEnvironment,
    SCMEnvironment,
)
from sreg.v1_5.environment.scm_env import SCMEnvironmentAdapter

__all__ = [
    "BaseEnvironment",
    "SCMEnvironment",
    "ODEEnvironment",
    "SCMEnvironmentAdapter",
]
