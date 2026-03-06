Run tests for the project.

1. If arguments are provided, run tests matching: $ARGUMENTS
   Example: `/test world_gen` runs `pytest tests/ -v -k world_gen`
2. If no arguments, run all tests: `pytest tests/ -v`
3. After running, summarize results: passed, failed, errors
4. If any tests fail, read the failing test and the relevant source code to diagnose the issue
