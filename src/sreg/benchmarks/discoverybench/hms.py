"""HMS (Hypothesis Matching Score) evaluation via LLM.

Implements the scoring algorithm from DiscoveryBench (arXiv:2407.01725).
Uses an LLM to decompose hypotheses into sub-components (context, variables,
relationship) and scores alignment between gold and predicted hypotheses.

Score range: 0.0 to 1.0 (paper uses 0-100, we normalize).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel

from sreg.inference.protocol import ChatResponse, Message, MessageRole, ModelClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class SubHypothesis(BaseModel):
    """A decomposed sub-hypothesis with context, variables, and relationship."""

    text: str = ""
    context: str = ""
    variables: list[str] = []
    relationship: str = ""


class HMSDetail(BaseModel):
    """Detailed HMS scoring breakdown for a single example."""

    gold_subs: list[SubHypothesis] = []
    pred_subs: list[SubHypothesis] = []
    matched_pairs: int = 0
    context_f1: float = 0.0
    mean_var_f1: float = 0.0
    mean_rel_acc: float = 0.0
    score: float = 0.0


# ---------------------------------------------------------------------------
# Prompts (adapted from DiscoveryBench eval code)
# ---------------------------------------------------------------------------

DECOMPOSE_PROMPT = """\
Given a hypothesis, decompose it into sub-hypotheses. Each sub-hypothesis \
should capture a distinct claim with three dimensions:

1. **Context**: Boundary conditions or scope (e.g., "for men over 30", \
"in 1989 data", "when controlling for income"). Use "general" if no \
specific context.
2. **Variables**: The entities/concepts involved (e.g., ["BMI", "time preference", \
"gender"]).
3. **Relationship**: How the variables interact (e.g., "positive correlation", \
"quadratic relationship", "no significant effect").

Return a JSON array of sub-hypotheses. Each element must have:
- "text": the sub-hypothesis in natural language
- "context": boundary conditions (string)
- "variables": list of variable names (list of strings)
- "relationship": description of the relationship (string)

If the hypothesis is simple (single claim), return an array with one element.

Hypothesis: {hypothesis}

Return ONLY the JSON array, no other text."""

CONTEXT_MATCH_PROMPT = """\
Determine if these two contexts are semantically equivalent (they describe \
the same scope, conditions, or boundary).

Context A (gold): {context_a}
Context B (predicted): {context_b}

Return ONLY a JSON object: {{"match": true}} or {{"match": false}}"""

VARIABLE_OVERLAP_PROMPT = """\
Compare the variable sets from two sub-hypotheses. Variables may be named \
differently but refer to the same concept (fuzzy matching).

Variables A (gold): {vars_a}
Variables B (predicted): {vars_b}

Return ONLY a JSON object with:
- "size_a": number of variables in A
- "size_b": number of variables in B
- "intersection": number of overlapping variables (counting fuzzy matches)"""

RELATIONSHIP_PROMPT = """\
Compare the relationships described in two sub-hypotheses.

Relationship A (gold): {rel_a}
Relationship B (predicted): {rel_b}

Score the match:
- 100: Exact match (same relationship type and direction)
- 50: Predicted is broader but encompasses the gold relationship
- 0: Different or incompatible relationships

Return ONLY a JSON object: {{"score": <0|50|100>}}"""


# ---------------------------------------------------------------------------
# HMS Scorer
# ---------------------------------------------------------------------------


def compute_hms(
    gold_hypothesis: str,
    predicted_hypothesis: str,
    client: ModelClient,
    model: str | None = None,
) -> HMSDetail:
    """Compute HMS between a gold and predicted hypothesis.

    Args:
        gold_hypothesis: The ground-truth hypothesis.
        predicted_hypothesis: The model's predicted hypothesis.
        client: LLM client for decomposition and matching.
        model: Model name override.

    Returns:
        HMSDetail with score in [0, 1] and breakdown.
    """
    if not predicted_hypothesis or not predicted_hypothesis.strip():
        return HMSDetail(score=0.0)

    # Step 1: Decompose both hypotheses
    gold_subs = _decompose(gold_hypothesis, client, model)
    pred_subs = _decompose(predicted_hypothesis, client, model)

    if not gold_subs or not pred_subs:
        return HMSDetail(gold_subs=gold_subs, pred_subs=pred_subs, score=0.0)

    # Step 2: Match contexts and score pairs
    matched_count = 0
    var_f1_scores: list[float] = []
    rel_acc_scores: list[float] = []
    gold_matched: set[int] = set()

    for pred_sub in pred_subs:
        best_gold_idx = -1
        best_pair_score = -1.0
        best_var_f1 = 0.0
        best_rel_acc = 0.0

        for gi, gold_sub in enumerate(gold_subs):
            if gi in gold_matched:
                continue

            # Check context match
            ctx_match = _check_context_match(
                gold_sub.context, pred_sub.context, client, model
            )
            if not ctx_match:
                continue

            # Score variables
            vf1 = _compute_variable_f1(
                gold_sub.variables, pred_sub.variables, client, model
            )

            # Score relationship
            racc = _compute_relationship_acc(
                gold_sub.relationship, pred_sub.relationship, client, model
            )

            pair_score = (vf1 + racc) / 2.0
            if pair_score > best_pair_score:
                best_pair_score = pair_score
                best_gold_idx = gi
                best_var_f1 = vf1
                best_rel_acc = racc

        if best_gold_idx >= 0:
            gold_matched.add(best_gold_idx)
            matched_count += 1
            var_f1_scores.append(best_var_f1)
            rel_acc_scores.append(best_rel_acc)

    # Step 3: Compute final score
    # context_recall = fraction of gold sub-hypotheses that were matched
    context_recall = matched_count / len(gold_subs) if gold_subs else 0.0
    # context_precision = fraction of pred sub-hypotheses that matched
    context_precision = matched_count / len(pred_subs) if pred_subs else 0.0
    # context F1
    if context_recall + context_precision > 0:
        context_f1 = (
            2 * context_recall * context_precision
            / (context_recall + context_precision)
        )
    else:
        context_f1 = 0.0

    mean_vf1 = sum(var_f1_scores) / len(var_f1_scores) if var_f1_scores else 0.0
    mean_racc = sum(rel_acc_scores) / len(rel_acc_scores) if rel_acc_scores else 0.0
    mean_pair_score = (mean_vf1 + mean_racc) / 2.0 if var_f1_scores else 0.0

    # Final HMS = context_f1 * mean_pair_score
    final_score = context_f1 * mean_pair_score

    return HMSDetail(
        gold_subs=gold_subs,
        pred_subs=pred_subs,
        matched_pairs=matched_count,
        context_f1=context_f1,
        mean_var_f1=mean_vf1,
        mean_rel_acc=mean_racc,
        score=final_score,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _llm_call(
    prompt: str,
    client: ModelClient,
    model: str | None,
) -> str:
    """Make a single LLM call and return the text response."""
    messages = [Message(role=MessageRole.USER, content=prompt)]
    try:
        response: ChatResponse = client.chat(
            messages=messages,
            model=model,
            max_tokens=500,
        )
        return response.message.content or ""
    except Exception as e:
        logger.warning(f"HMS LLM call failed: {e}")
        return ""


def _parse_json(text: str) -> Any:
    """Extract JSON from LLM response, handling markdown fences."""
    text = text.strip()
    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON array or object in the text
        for start_char, end_char in [("[", "]"), ("{", "}")]:
            start = text.find(start_char)
            end = text.rfind(end_char)
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    continue
        logger.warning(f"Failed to parse JSON from: {text[:200]}")
        return None


def _decompose(
    hypothesis: str,
    client: ModelClient,
    model: str | None,
) -> list[SubHypothesis]:
    """Decompose a hypothesis into sub-hypotheses via LLM."""
    prompt = DECOMPOSE_PROMPT.format(hypothesis=hypothesis)
    raw = _llm_call(prompt, client, model)
    parsed = _parse_json(raw)

    if not parsed or not isinstance(parsed, list):
        # Fallback: treat the whole hypothesis as a single sub-hypothesis
        return [
            SubHypothesis(
                text=hypothesis,
                context="general",
                variables=[],
                relationship=hypothesis,
            )
        ]

    subs = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        subs.append(
            SubHypothesis(
                text=item.get("text", ""),
                context=item.get("context", "general"),
                variables=item.get("variables", []),
                relationship=item.get("relationship", ""),
            )
        )
    return subs if subs else [
        SubHypothesis(
            text=hypothesis,
            context="general",
            variables=[],
            relationship=hypothesis,
        )
    ]


def _check_context_match(
    ctx_gold: str,
    ctx_pred: str,
    client: ModelClient,
    model: str | None,
) -> bool:
    """Check if two contexts are semantically equivalent."""
    # Quick check for trivial matches
    g = ctx_gold.strip().lower()
    p = ctx_pred.strip().lower()
    if g == p or (g == "general" and p == "general"):
        return True
    if g == "general" or p == "general":
        # "general" matches everything (no specific scope)
        return True

    prompt = CONTEXT_MATCH_PROMPT.format(context_a=ctx_gold, context_b=ctx_pred)
    raw = _llm_call(prompt, client, model)
    parsed = _parse_json(raw)

    if parsed and isinstance(parsed, dict):
        return bool(parsed.get("match", False))
    return False


def _compute_variable_f1(
    gold_vars: list[str],
    pred_vars: list[str],
    client: ModelClient,
    model: str | None,
) -> float:
    """Compute F1 score for variable overlap (fuzzy matching via LLM)."""
    if not gold_vars and not pred_vars:
        return 1.0  # Both empty = perfect match
    if not gold_vars or not pred_vars:
        return 0.0

    # For small sets, try LLM-based fuzzy matching
    prompt = VARIABLE_OVERLAP_PROMPT.format(
        vars_a=json.dumps(gold_vars),
        vars_b=json.dumps(pred_vars),
    )
    raw = _llm_call(prompt, client, model)
    parsed = _parse_json(raw)

    if parsed and isinstance(parsed, dict):
        size_a = parsed.get("size_a", len(gold_vars))
        size_b = parsed.get("size_b", len(pred_vars))
        intersection = parsed.get("intersection", 0)

        if size_a == 0 and size_b == 0:
            return 1.0

        precision = intersection / size_b if size_b > 0 else 0.0
        recall = intersection / size_a if size_a > 0 else 0.0

        if precision + recall > 0:
            return 2 * precision * recall / (precision + recall)
    return 0.0


def _compute_relationship_acc(
    gold_rel: str,
    pred_rel: str,
    client: ModelClient,
    model: str | None,
) -> float:
    """Compute relationship accuracy (0, 0.5, or 1.0)."""
    if not gold_rel and not pred_rel:
        return 1.0
    if not gold_rel or not pred_rel:
        return 0.0

    prompt = RELATIONSHIP_PROMPT.format(rel_a=gold_rel, rel_b=pred_rel)
    raw = _llm_call(prompt, client, model)
    parsed = _parse_json(raw)

    if parsed and isinstance(parsed, dict):
        score = parsed.get("score", 0)
        return float(score) / 100.0  # Normalize to [0, 1]
    return 0.0
