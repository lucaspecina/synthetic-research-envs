#!/bin/bash
# P0.5 Canonical Batch — frozen baseline for rescore validation
# Generates 12 diverse cases with score_inputs_v2 persistence (P0).
#
# Purpose: provides a stable, frozen E2E baseline used for:
#   - rescore --reaggregate (verify backward compat, delta 0.0000)
#   - rescore --recompile / --rejudge (measure code change effects)
#   - smoke-validation of grammar extensions (P1, P1.5, future)
#
# Seeds cover diverse research types per investigation_scenarios_rubric.md:
# system_mapping, causal_simple, confounding, descriptive, epistemological,
# heterogeneity, optimization, selection_bias, mechanism, multi_outcome,
# policy_tradeoff, methodology.
#
# Expected runtime: ~1.5-2 hours (LLM-bound on Azure gpt-5.4 / gpt-5.2-codex).

set -e

OUTDIR="results/p05_canonical_batch"
mkdir -p "$OUTDIR"

SEEDS=(
    "microbiome_system_mapping.md:microbiome:system_mapping"
    "poverty_reduction_china.md:poverty:causal_simple"
    "confounding_by_indication.md:confounding:confounding"
    "coral_reef_bleaching.md:coral_bleach:descriptive"
    "identifiability_pollution.md:identifiability:epistemological"
    "treatment_heterogeneity.md:heterogeneity:heterogeneity"
    "chemical_formulation.md:chemical:optimization"
    "selection_bias_police.md:selection_bias:selection_bias"
    "competing_mechanisms.md:competing_mech:causal_mechanism"
    "methodology_missing_data.md:missing_data:epistemological_method"
    "policy_equity_tradeoff.md:policy_equity:policy_tradeoff"
    "immunotherapy_tradeoff.md:immunotherapy:multi_outcome"
)

echo "=== P0.5 Canonical Batch ==="
echo "  Seeds: ${#SEEDS[@]}"
echo "  Output: $OUTDIR"
echo "  Started: $(date)"
echo ""

SUCCESSES=0
FAILURES=0

for entry in "${SEEDS[@]}"; do
    IFS=':' read -r seed name type <<< "$entry"
    casedir="$OUTDIR/$name"
    echo "--- [$name] ($type) ---"

    if python scripts/generate_src.py \
        --seed-file "seeds/$seed" \
        -o "$casedir" \
        --oi --inspect 2>&1 | tee "$casedir.log"; then
        SUCCESSES=$((SUCCESSES + 1))
        echo "  OK: $name"
    else
        FAILURES=$((FAILURES + 1))
        echo "  FAIL: $name"
    fi
    echo ""
done

echo "=== Summary ==="
echo "  Success: $SUCCESSES / ${#SEEDS[@]}"
echo "  Failed:  $FAILURES"
echo "  Finished: $(date)"
