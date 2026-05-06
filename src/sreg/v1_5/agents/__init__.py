"""Agentes del Designer multi-agente v1.5.

Cada agente toma un input tipado y produce un output tipado, usando un
`ModelClient` (Azure Foundry / OpenAI / vLLM) por debajo. Los prompts
viven en `prompts/` como archivos `.md` para iteración cómoda.

Orden esperado del flujo (post Ronda 13):

    Paper crudo
        ↓ [paper_digestion.PaperDigestionAgent]
    PaperInsights (mecanismos + narrative_capsule saneada)
        ↓ [architect.ArchitectAgent]                          (Fase 1.3)
    WorldSpec + intended_phenomena
        ↓ [validators.ValidatorAgent × N]                     (Fase 2)
    list[ValidatedPhenomenon]
        ↓ [question_designer.QuestionDesignerAgent]           (Fase 3)
    QuestionsBundle
        ↓ [case_writer.CaseWriterAgent]                       (Fase 4)
    ResearchCase
        ↓ [validator_transversal.ValidatorTransversalAgent]   (Fase 5)
    ValidationReport (passed=True ⇒ caso listo para Investigator)
"""

from sreg.v1_5.agents.paper_digestion import PaperDigestionAgent

__all__ = ["PaperDigestionAgent"]
