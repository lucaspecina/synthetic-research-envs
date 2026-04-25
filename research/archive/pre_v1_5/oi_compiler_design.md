# OI Compiler Design — Research Note

**Date:** 2026-03-27
**Context:** Alpha-0 works. Verifier + salience map + pilot validated (77 tests).
Next step: compiler that translates solver ClaimCards to AtomicSpecs.

## The Problem

The solver submits ClaimCards in semi-structured natural language:
```
claim_text: "Higher A increases Y, especially when Z is above median"
focus_variables: ["A", "Y", "Z"]
confidence: 0.8
evidence_basis: [{"artifact_id": "dataset_1", "rationale": "regression on 500 obs"}]
pattern_tags: ["causal_effect", "heterogeneity"]
```

The verifier needs AtomicSpecs:
```
AtomicSpec(
  arms=(INTERVENE(A=hi), INTERVENE(A=lo)),
  measurement=MEAN(Y),
  comparison=DIFFERENCE(ref=lo),
  assertion=POSITIVE
)
```

The compiler bridges these. This is where "controlled subjectivity" lives.

## Key Design Principle: Blind Parse

The compiler NEVER sees the salience map or SCM truth. It only sees:
1. The ClaimCard (solver output)
2. World metadata: variable names, observable variables list
3. Problem brief: what the research question is

References (salience map families) guide SCORING only, after compilation.

## Design Options

### Option A: Single-Shot LLM

One prompt: "Given this claim card and world metadata, produce AtomicSpec JSON."

**Pros:** Simple, fast, cheap.
**Cons:** No error correction. Hallucinated variable names. Missing fields.

### Option B: Structured Extraction + LLM Fallback

1. Parse claim_text with rules/regex for common patterns
2. Use focus_variables + pattern_tags for slot filling
3. LLM only for ambiguous cases or complex claim_text

**Pros:** Deterministic for simple cases, cheaper.
**Cons:** Limited coverage, brittle rules.

### Option C: LLM with Preview Loop (RECOMMENDED)

1. LLM generates candidate AtomicSpec from claim card
2. Preview validator checks: valid variable names? valid QueryKind?
   consistent with focus_variables? parseable spec?
3. If preview fails: LLM retries with error feedback (max 2 retries)
4. If still fails: mark as ABSTENTION (compiler couldn't translate)

**Pros:** Robust, self-correcting, measurable precision.
**Cons:** More LLM calls per claim (1-3), higher cost.

### Option D: Few-Shot with Exemplar Bank

Use the salience map families (from OTHER worlds, not this one) as
few-shot examples. "Here are examples of claims and their formal specs..."

**Pros:** LLM sees the target format clearly.
**Cons:** Examples might bias toward particular patterns.

## Recommendation: Option C + D

LLM with preview loop, using exemplar bank for few-shot. Specifically:

1. **Exemplar bank**: 15-20 hand-crafted (claim_text → AtomicSpec) pairs
   covering all 7 pattern types. Static, not from the current world.

2. **Input to LLM**: system prompt (grammar description + exemplars) +
   user message (claim card + variable list from brief).

3. **Output**: JSON with AtomicSpec fields.

4. **Preview validator**: check variable names exist, QueryKind is valid,
   arms have distinct labels, measurement target exists, etc. This is
   deterministic — no LLM judge.

5. **Retry on failure**: re-prompt with error message, max 2 retries.

6. **Abstention**: if all retries fail, emit CompilerAbstention (claim
   skipped, doesn't count toward correctness or coverage).

## Abstention Design

Critical question: how does abstention affect scoring?

**Option 1: Abstention = 0 score, counts toward n_claims**
- Conservative. Punishes vague claims.
- Risk: punishes legitimate complex claims the compiler can't parse.

**Option 2: Abstention = excluded from scoring**
- Lenient. Doesn't punish unparseable claims.
- Risk: solver game by submitting vague claims that the compiler skips.

**Option 3 (RECOMMENDED): Abstention = 0 correctness, doesn't count for coverage**
- Middle ground. Vague claims get 0 (can't verify = can't score).
- But they don't block coverage from other claims.
- Efficiency penalty still applies if solver submits too many.

## Compiler Output Model

```python
class CompilerOutput(BaseModel):
    """Result of compiling one ClaimCard."""

    claim_id: str
    status: Literal["compiled", "abstention"]
    specs: list[AtomicSpec]  # usually 1, sometimes 2-3 for multi-part claims
    matched_family_ids: list[str]  # filled AFTER compilation by matcher
    compiler_confidence: float  # 0-1, how sure the compiler is of its translation
    abstention_reason: str | None  # if status == "abstention"
```

## Matching: Compiled Specs → Salience Families

After compilation, we need to match compiled specs to salience families.
This is where the scoring bridge lives.

**Algorithm:**
1. For each compiled spec, compute atom verdicts (verify against SCM)
2. For each salience family, find the best-matching compiled spec
3. Matching by: focus_variables overlap, pattern_class match, atom verdicts

**Key:** matching is deterministic (no LLM). It's just set intersection
+ scoring from the existing `score_claim_against_family()`.

## Benchmark Design (Step 4 of Build Order)

**Offline benchmark: 200+ claims, 15+ worlds, >90% precision**

Setup:
1. Build 15+ diverse SCMWorlds
2. For each world, build salience map
3. For each family, generate "oracle claim text" (natural language
   describing the truth in the family)
4. Also generate adversarial claims: wrong direction, wrong variables,
   overly vague, overly specific

Metrics:
- **Precision**: compiled spec matches the intended family AND verifies True
- **Recall**: fraction of oracle claims that compile successfully (not abstention)
- **Harmful error rate**: compiled spec verifies True but matches WRONG family
  (this is the worst case — rewards wrong answers)

Thresholds:
- Precision > 90%
- Recall > 80%
- Harmful error rate < 2%

## What This Note Does NOT Cover

- Exact LLM prompt (needs iteration)
- Cost optimization (batching, caching)
- Multi-claim compilation (when one claim maps to 2+ specs)
- Confidence calibration scoring (separate design)

## Implementation Status

### DONE (no LLM needed):
1. **ClaimIntent IR** — symbolic intermediate representation with PatternClass,
   Direction, variable roles. Pydantic model with validation.
2. **WorldSummary** — canonical anchors (percentiles per variable) shared between
   salience map and compiler. `build_world_summary()` from SCMWorld.
3. **Deterministic lowering** — `lower_intent()` for all 7 pattern types.
   Multi-part claims (mediation, heterogeneity) → 2 specs.
4. **Preview validator** — `validate_intent()` checks variable existence,
   observability, role requirements. Deterministic, no LLM.
5. **Matching algorithm** — `match_specs_to_families()` by focus_signature
   overlap + pattern_class compatibility. Deterministic.
6. **Full pipeline scorer** — `score_compiled_episode()` handles compile →
   verify → match → score with abstention handling.
7. **Exemplar bank** — 14 positive (all 7 patterns) + 5 negative (abstention).
   Hand-crafted per Codex recommendation.
8. **CompilerOutput model** — compiled specs or abstention with reason.

### REMAINING (needs LLM):
9. **LLM extraction** — ClaimCard → ClaimIntent via few-shot prompting
10. **Offline benchmark** — 200+ claims, >90% precision, <2% harmful error

### Architecture (implemented per Codex debate)
```
ClaimCard (NL) → [LLM + exemplars] → ClaimIntent (symbolic)
    → [validate_intent] → [lower_intent] → AtomicSpec(s)
    → [match_specs_to_families] → family matches
    → [verify_atom] → verdicts
    → [score_compiled_episode] → EpisodeScore
```
