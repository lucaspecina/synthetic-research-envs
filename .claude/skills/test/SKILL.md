---
name: test
description: Run targeted tests for the project. NEVER run the full suite unless explicitly asked.
disable-model-invocation: true
---

Run TARGETED tests for the project. The full suite takes 40+ minutes — avoid it.

1. If arguments are provided, run tests matching: $ARGUMENTS
   Example: `/test scm_task_gen` runs `pytest tests/ -v -k scm_task_gen`
2. If no arguments: ask the user what to test. Do NOT run the full suite.
3. After running, summarize results: passed, failed, errors
4. If any tests fail, read the failing test and the relevant source code to diagnose

**IMPORTANT:** The real validation is E2E with LLM (`/run --oi`), not pytest.
Unit tests only verify code doesn't break. Run the minimum needed.
