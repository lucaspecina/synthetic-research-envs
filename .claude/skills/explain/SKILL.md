---
name: explain
description: Explain recent changes to the user in friendly, detailed, simple language. Use before every commit to ensure the user understands what changed and why.
---

Explain the current changes to the user in a friendly, detailed way. This is MANDATORY
before every commit.

## What to cover

1. **What was done** — in simple language, no jargon. What did we build/change?

2. **Where it fits in the big picture** — show a simple diagram or list:
   - What existed before
   - What's new
   - How the new thing connects to the rest

3. **What's now possible that wasn't before** — concrete examples. Show code snippets
   of what a user can now do. Make it tangible.

4. **E2E results** (if applicable) — if there was validation/testing:
   - Show the key metrics in a table
   - Explain what the numbers mean
   - Flag anything surprising or concerning

5. **What's NOT done yet** — be honest about limitations, next steps, known issues.

## Style guidelines

- Write in Spanish (the user's language)
- Use simple, friendly language — explain like talking to a smart colleague, not writing a paper
- Use analogies when helpful ("es como si un profesor solo pudiera hacer 3 tipos de examen")
- Show concrete before/after comparisons
- Keep it conversational but informative
- Use markdown formatting: headers, tables, code blocks, bullet points

## How to gather info

1. Run `git diff --cached` or `git diff` to see what changed
2. Read the modified files to understand the changes
3. Check CHANGELOG.md for the entry you wrote
4. If there was E2E validation, summarize the results

## Output format

A single, well-structured message to the user. End with "Puedo commitear?" to ask
for approval (unless the commit was already made, in which case explain what was committed).
