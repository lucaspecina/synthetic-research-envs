Review recent code changes for quality and correctness.

1. Run `git diff` to see unstaged changes, or `git diff --cached` for staged changes
2. For each changed file:
   - Check that it follows project conventions from CLAUDE.md
   - Check for type hints on public functions
   - Check for security issues (injection, hardcoded secrets, etc.)
   - Check that pydantic models are used correctly
   - Check that tests exist for new functionality
3. Summarize findings: what looks good, what needs attention
4. If arguments specify a file or module, focus review there: $ARGUMENTS
