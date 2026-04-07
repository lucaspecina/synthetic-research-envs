# SREG v1 — Hardening loop (working note)

**Date:** 2026-04-07
**Status:** TENTATIVE — do not elevate to `synthesis/` until P06 mini re-test
on `chemical + confounding + immunotherapy` confirms the predicted recovery.
Not yet indexed in `research/README.md` for the same reason.

## Objective for the current phase

We are NOT trying to "close the thesis" or "solve the science in general".

The objective right now is narrower:

> Leave a v1 of SREG reliable enough to use and learn from its results
> without everything being contaminated by bugs or broken contracts.

This is hardening, not feature work.

## What this resolves (and what it doesn't)

The trajectory of confounds we have walked through:
1. We initially thought the scoring formula was the bottleneck.
2. The scorer turned out not to be the main culprit on its own.
3. The system was pushing the solver toward bundled claims (cap=5, prompt
   wording).
4. After the atomicity intervention, a NEW confound surfaced:
   `evidence_basis` mis-anchored — the solver cannot reliably attach a
   valid `artifact_id` to its claims, so good claims take a 90% penalty
   for wearing wrong nametags.

Fix A (in flight, see `research/notes/p06_phase_c_forensics.md`) resolves:
- Good claims should not sink because of a wrong label.
- Solver should be able to cite real artifacts correctly.
- The bundling experiment can then be measured cleanly, without the
  evidence-fabrication confound bleeding into the result.

Fix A does NOT resolve:
- **Force-submit / iteration exhaustion.** When the solver runs out of
  iterations before consolidating with `save_artifact`, it still has no
  valid artifact to cite. This is orthogonal and remains open.
- **The bundling hypothesis itself.** A clean contract is a *prerequisite*
  for re-testing the atomicity intervention. The hypothesis is still
  unsettled and will need a clean re-run.

So Fix A cleans ONE confound out of two-or-three, deliberately. It is the
one we can diagnose and fix surgically today.

## The candidate loop

The pattern that produced this fix, which we want to evaluate as a
standard working pattern:

1. **Forensics** (read-only): inspect raw artifacts and conversations,
   identify the failure mode precisely. No code changes.
2. **Diagnosis writing**: produce a concrete prediction of the form
   "if we change X, Y disappears in cases Z, and W does not regress."
   If you cannot write this kind of prediction, stop and re-investigate.
3. **Surgical fix**: smallest change that addresses ONE confound, plus
   any visibility/documentation needed for the contract to be obvious.
4. **Mini re-test**: 3-5 cases in a NEW directory, never overwriting
   prior evidence. Same seeds, same models.
5. **Decide**: did the prediction hold? If yes, commit and move on. If
   no, revert and re-investigate.

This is the opposite of "run a 12-case batch and hope it tells us
something". The 12-case batches are valuable as final validation, not
as exploration loops.

## Test of the framing

The implicit mental test the framing relies on:

> If SREG measured wrong because of a bug, and we therefore reported a
> finding that later did not replicate, the failure would have been "we
> didn't clean contracts first".

We accept the cost of pausing the bundling experiment to do this fix
*precisely* to avoid that failure mode.

## When to elevate this note

Promote to `research/synthesis/` and index in `research/README.md` if AND
only if:
- Fix A's mini re-test produces the predicted recovery on confounding
  (0 fab refs, correctness > 0.5), AND
- chemical or immunotherapy improve at least partially under Fix A.

If neither condition holds, this note stays here as "an attempt and what
we learned", and we re-plan from forensics.
