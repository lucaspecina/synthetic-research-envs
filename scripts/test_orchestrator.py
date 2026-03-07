"""Quick test: run the orchestrator with a real LLM."""

import logging

logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

from sreg.orchestrator.orchestrator import Orchestrator

o = Orchestrator()
print(f"Using model: {o.model}")
print("Running orchestrator...")

result = o.run("Generate a simple world with 5 nodes about weather prediction, medium difficulty")

print(f"\n=== RESULT ===")
print(f"World: {result.world}")
print(f"Attempts: {result.attempts}")
print(f"Validation: {result.validation_passed}")
print(f"Episode: {result.episode}")
print(f"Task: {result.task}")
print(f"Messages exchanged: {len(result.messages)}")

if result.world:
    print(f"\nWorld nodes:")
    for n in result.world.nodes:
        print(f"  {n.name} ({n.type.value}) -> {n.states}")

if result.task:
    print(f"\nTask question: {result.task.question}")
