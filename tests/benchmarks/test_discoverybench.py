"""Tests for DiscoveryBench adapter and HMS scorer."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from sreg.benchmarks.discoverybench.adapter import (
    DiscoveryBenchAdapter,
    DiscoveryBenchResult,
)
from sreg.benchmarks.discoverybench.hms import (
    _check_context_match,
    _compute_relationship_acc,
    _compute_variable_f1,
    _decompose,
    _parse_json,
    compute_hms,
)
from sreg.inference.protocol import ChatResponse, FinishReason, Message, MessageRole

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(responses: list[str]) -> MagicMock:
    """Create a mock ModelClient that returns a sequence of responses."""
    client = MagicMock()
    call_count = 0

    def chat_side_effect(**kwargs):
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        call_count += 1
        return ChatResponse(
            message=Message(role=MessageRole.ASSISTANT, content=responses[idx]),
            tool_calls=[],
            finish_reason=FinishReason.STOP,
        )

    client.chat.side_effect = chat_side_effect
    return client


def _make_csv(tmp_path: Path, rows: list[dict]) -> Path:
    """Create a fake DiscoveryBench CSV file."""
    import csv

    path = tmp_path / "test_db.csv"
    fieldnames = ["domain", "workflow_tags", "domain_knowledge", "datasets", "queries"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


SAMPLE_DATASETS = json.dumps([{
    "name": "test_data.csv",
    "description": "Test dataset about BMI and exercise",
    "columns": {
        "raw": [
            {"name": "BMI", "description": "Body mass index"},
            {"name": "exercise_hours", "description": "Weekly exercise hours"},
            {"name": "age", "description": "Age in years"},
        ]
    },
}])

SAMPLE_QUERIES = json.dumps([{
    "question": "What factors are associated with higher BMI?",
    "question_type": "variables",
    "true_hypothesis": "Higher exercise hours are associated with lower BMI.",
}])


# ---------------------------------------------------------------------------
# HMS: _parse_json
# ---------------------------------------------------------------------------


class TestParseJson:
    def test_plain_json_object(self):
        assert _parse_json('{"match": true}') == {"match": True}

    def test_plain_json_array(self):
        assert _parse_json('[{"text": "a"}]') == [{"text": "a"}]

    def test_markdown_fences(self):
        text = '```json\n{"score": 50}\n```'
        assert _parse_json(text) == {"score": 50}

    def test_json_embedded_in_text(self):
        text = 'Here is the result: {"match": false} end.'
        assert _parse_json(text) == {"match": False}

    def test_invalid_json(self):
        assert _parse_json("not json at all") is None

    def test_empty_string(self):
        assert _parse_json("") is None


# ---------------------------------------------------------------------------
# HMS: _decompose
# ---------------------------------------------------------------------------


class TestDecompose:
    def test_valid_decomposition(self):
        response = json.dumps([{
            "text": "BMI decreases with exercise",
            "context": "for adults",
            "variables": ["BMI", "exercise"],
            "relationship": "negative correlation",
        }])
        client = _make_client([response])
        subs = _decompose("BMI decreases with exercise", client, None)
        assert len(subs) == 1
        assert subs[0].context == "for adults"
        assert subs[0].variables == ["BMI", "exercise"]

    def test_invalid_response_falls_back(self):
        client = _make_client(["not json"])
        subs = _decompose("some hypothesis", client, None)
        assert len(subs) == 1
        assert subs[0].text == "some hypothesis"
        assert subs[0].context == "general"

    def test_multiple_sub_hypotheses(self):
        response = json.dumps([
            {"text": "a", "context": "c1", "variables": ["x"], "relationship": "r1"},
            {"text": "b", "context": "c2", "variables": ["y"], "relationship": "r2"},
        ])
        client = _make_client([response])
        subs = _decompose("complex hypothesis", client, None)
        assert len(subs) == 2


# ---------------------------------------------------------------------------
# HMS: context matching
# ---------------------------------------------------------------------------


class TestContextMatch:
    def test_identical_contexts(self):
        client = _make_client([])  # Should not be called
        assert _check_context_match("general", "general", client, None) is True

    def test_general_matches_anything(self):
        client = _make_client([])
        assert _check_context_match("general", "for adults", client, None) is True
        assert _check_context_match("for 1989 data", "general", client, None) is True

    def test_llm_match(self):
        client = _make_client(['{"match": true}'])
        assert _check_context_match("for 1989", "in 1989 data", client, None) is True

    def test_llm_no_match(self):
        client = _make_client(['{"match": false}'])
        assert _check_context_match("for men", "for women", client, None) is False


# ---------------------------------------------------------------------------
# HMS: variable F1
# ---------------------------------------------------------------------------


class TestVariableF1:
    def test_both_empty(self):
        client = _make_client([])
        assert _compute_variable_f1([], [], client, None) == 1.0

    def test_one_empty(self):
        client = _make_client([])
        assert _compute_variable_f1(["x"], [], client, None) == 0.0

    def test_perfect_overlap(self):
        response = json.dumps({"size_a": 2, "size_b": 2, "intersection": 2})
        client = _make_client([response])
        f1 = _compute_variable_f1(["x", "y"], ["x", "y"], client, None)
        assert f1 == 1.0

    def test_partial_overlap(self):
        response = json.dumps({"size_a": 2, "size_b": 3, "intersection": 1})
        client = _make_client([response])
        f1 = _compute_variable_f1(["x", "y"], ["x", "z", "w"], client, None)
        # precision = 1/3, recall = 1/2, F1 = 2*(1/3*1/2)/(1/3+1/2) = 0.4
        assert abs(f1 - 0.4) < 0.01


# ---------------------------------------------------------------------------
# HMS: relationship accuracy
# ---------------------------------------------------------------------------


class TestRelationshipAcc:
    def test_both_empty(self):
        client = _make_client([])
        assert _compute_relationship_acc("", "", client, None) == 1.0

    def test_one_empty(self):
        client = _make_client([])
        assert _compute_relationship_acc("pos corr", "", client, None) == 0.0

    def test_exact_match(self):
        client = _make_client(['{"score": 100}'])
        assert _compute_relationship_acc("pos", "pos", client, None) == 1.0

    def test_broader_match(self):
        client = _make_client(['{"score": 50}'])
        assert _compute_relationship_acc("pos corr", "corr", client, None) == 0.5

    def test_mismatch(self):
        client = _make_client(['{"score": 0}'])
        assert _compute_relationship_acc("pos", "neg", client, None) == 0.0


# ---------------------------------------------------------------------------
# HMS: compute_hms (full pipeline)
# ---------------------------------------------------------------------------


class TestComputeHMS:
    def test_empty_prediction(self):
        client = _make_client([])
        hms = compute_hms("gold", "", client)
        assert hms.score == 0.0

    def test_perfect_match(self):
        """One sub-hypothesis each, perfect match on all dimensions."""
        # decompose gold, decompose pred, context match, variable overlap, rel acc
        responses = [
            # Gold decomposition
            json.dumps([{
                "text": "BMI decreases",
                "context": "general",
                "variables": ["BMI", "exercise"],
                "relationship": "negative correlation",
            }]),
            # Pred decomposition
            json.dumps([{
                "text": "BMI decreases",
                "context": "general",
                "variables": ["BMI", "exercise"],
                "relationship": "negative correlation",
            }]),
            # Variable F1
            json.dumps({"size_a": 2, "size_b": 2, "intersection": 2}),
            # Relationship accuracy
            json.dumps({"score": 100}),
        ]
        client = _make_client(responses)
        hms = compute_hms("BMI decreases with exercise", "BMI decreases with exercise", client)
        assert hms.score > 0.8
        assert hms.matched_pairs == 1


# ---------------------------------------------------------------------------
# Adapter: load
# ---------------------------------------------------------------------------


class TestLoad:
    def test_load_all(self, tmp_path):
        csv_path = _make_csv(tmp_path, [
            {
                "domain": "biology",
                "workflow_tags": "regression",
                "domain_knowledge": "BK",
                "datasets": SAMPLE_DATASETS,
                "queries": SAMPLE_QUERIES,
            },
            {
                "domain": "sociology",
                "workflow_tags": "data_cleaning,regression",
                "domain_knowledge": "SK",
                "datasets": SAMPLE_DATASETS,
                "queries": SAMPLE_QUERIES,
            },
        ])
        adapter = DiscoveryBenchAdapter(data_path=csv_path)
        examples = adapter.load(subset="all")
        assert len(examples) == 2
        assert examples[0].domain == "biology"
        assert examples[1].domain == "sociology"

    def test_load_parses_fields(self, tmp_path):
        csv_path = _make_csv(tmp_path, [{
            "domain": "engineering",
            "workflow_tags": '["feature_engineering"]',
            "domain_knowledge": "Some knowledge",
            "datasets": SAMPLE_DATASETS,
            "queries": SAMPLE_QUERIES,
        }])
        adapter = DiscoveryBenchAdapter(data_path=csv_path)
        examples = adapter.load()
        ex = examples[0]
        assert ex.domain == "engineering"
        assert ex.workflow_tags == ["feature_engineering"]
        assert ex.question == "What factors are associated with higher BMI?"
        assert "exercise" in ex.gold_hypothesis.lower()
        assert len(ex.datasets) == 1
        assert ex.datasets[0]["name"] == "test_data.csv"

    def test_load_dev_subset(self, tmp_path):
        rows = [
            {
                "domain": d,
                "workflow_tags": "regression",
                "domain_knowledge": "",
                "datasets": SAMPLE_DATASETS,
                "queries": SAMPLE_QUERIES,
            }
            for d in ["biology"] * 5 + ["sociology"] * 5 + ["economics"] * 5
        ]
        csv_path = _make_csv(tmp_path, rows)
        adapter = DiscoveryBenchAdapter(data_path=csv_path)
        examples = adapter.load(subset="dev", dev_count=6)
        assert len(examples) == 6
        # Should have samples from each domain
        domains = {ex.domain for ex in examples}
        assert len(domains) == 3


# ---------------------------------------------------------------------------
# Adapter: prompt composition
# ---------------------------------------------------------------------------


class TestPrompt:
    def test_includes_domain_and_question(self, tmp_path):
        csv_path = _make_csv(tmp_path, [{
            "domain": "biology",
            "workflow_tags": "regression",
            "domain_knowledge": "BMI context",
            "datasets": SAMPLE_DATASETS,
            "queries": SAMPLE_QUERIES,
        }])
        adapter = DiscoveryBenchAdapter(data_path=csv_path)
        examples = adapter.load()
        prompt = adapter._compose_prompt(examples[0])
        assert "biology" in prompt.lower()
        assert "BMI" in prompt
        assert "exercise_hours" in prompt
        assert "What factors" in prompt

    def test_includes_columns(self, tmp_path):
        csv_path = _make_csv(tmp_path, [{
            "domain": "test",
            "workflow_tags": "",
            "domain_knowledge": "",
            "datasets": SAMPLE_DATASETS,
            "queries": SAMPLE_QUERIES,
        }])
        adapter = DiscoveryBenchAdapter(data_path=csv_path)
        examples = adapter.load()
        prompt = adapter._compose_prompt(examples[0])
        assert "BMI" in prompt
        assert "exercise_hours" in prompt
        assert "age" in prompt


# ---------------------------------------------------------------------------
# Adapter: extract hypothesis
# ---------------------------------------------------------------------------


class TestExtractHypothesis:
    def test_plain_text(self):
        assert DiscoveryBenchAdapter._extract_hypothesis("Higher BMI...") == "Higher BMI..."

    def test_with_prefix(self):
        raw = "Hypothesis: Higher BMI correlates with less exercise."
        result = DiscoveryBenchAdapter._extract_hypothesis(raw)
        assert result == "Higher BMI correlates with less exercise."

    def test_with_markdown_prefix(self):
        raw = "**Hypothesis:** Exercise reduces BMI."
        result = DiscoveryBenchAdapter._extract_hypothesis(raw)
        assert result == "Exercise reduces BMI."

    def test_with_quotes(self):
        raw = '"Higher exercise lowers BMI."'
        result = DiscoveryBenchAdapter._extract_hypothesis(raw)
        assert result == "Higher exercise lowers BMI."

    def test_empty(self):
        assert DiscoveryBenchAdapter._extract_hypothesis("") == ""


# ---------------------------------------------------------------------------
# Adapter: run
# ---------------------------------------------------------------------------


class TestRun:
    def test_run_collects_responses(self, tmp_path):
        csv_path = _make_csv(tmp_path, [{
            "domain": "biology",
            "workflow_tags": "regression",
            "domain_knowledge": "",
            "datasets": SAMPLE_DATASETS,
            "queries": SAMPLE_QUERIES,
        }])
        adapter = DiscoveryBenchAdapter(data_path=csv_path)
        examples = adapter.load()

        client = _make_client(["Exercise reduces BMI significantly."])
        results = adapter.run(client, examples)

        assert len(results) == 1
        assert results[0].predicted_hypothesis == "Exercise reduces BMI significantly."
        assert not results[0].error

    def test_run_error_tracking(self, tmp_path):
        csv_path = _make_csv(tmp_path, [{
            "domain": "biology",
            "workflow_tags": "",
            "domain_knowledge": "",
            "datasets": SAMPLE_DATASETS,
            "queries": SAMPLE_QUERIES,
        }])
        adapter = DiscoveryBenchAdapter(data_path=csv_path)
        examples = adapter.load()

        client = MagicMock()
        client.chat.side_effect = RuntimeError("API failed")

        results = adapter.run(client, examples)
        assert len(results) == 1
        assert results[0].error is True
        assert results[0].predicted_hypothesis == ""


# ---------------------------------------------------------------------------
# Adapter: score
# ---------------------------------------------------------------------------


class TestScore:
    def test_score_aggregates(self):
        results = [
            DiscoveryBenchResult(
                index=0,
                domain="biology",
                question_type="variables",
                gold_hypothesis="Exercise lowers BMI",
                predicted_hypothesis="More exercise means lower BMI",
                hms_score=0.8,
            ),
            DiscoveryBenchResult(
                index=1,
                domain="sociology",
                question_type="relationship",
                gold_hypothesis="Income correlates with education",
                predicted_hypothesis="Education predicts income",
                hms_score=0.4,
            ),
        ]
        # Mock client for score() — won't be called since hms_score is already set
        # But score() calls compute_hms internally, so we need real mocking
        # Instead, pre-set the scores and call score with pre-scored results

        # Actually score() re-scores. Let's test with a mock that returns known HMS
        adapter = DiscoveryBenchAdapter(data_path="dummy")

        # Patch compute_hms calls
        decomp_response = json.dumps([{
            "text": "t", "context": "general",
            "variables": ["x"], "relationship": "r",
        }])
        var_response = json.dumps({"size_a": 1, "size_b": 1, "intersection": 1})
        rel_response = json.dumps({"score": 100})
        responses = [decomp_response, decomp_response, var_response, rel_response] * 2
        client = _make_client(responses)

        benchmark = adapter.score(results, client, model_name="test-model")
        assert benchmark.benchmark == "discoverybench"
        assert benchmark.metric_name == "hms"
        assert benchmark.model_name == "test-model"
        assert benchmark.num_examples == 2

    def test_score_with_errors(self):
        results = [
            DiscoveryBenchResult(
                index=0,
                domain="biology",
                question_type="variables",
                gold_hypothesis="Gold",
                predicted_hypothesis="",
                error=True,
            ),
        ]
        adapter = DiscoveryBenchAdapter(data_path="dummy")
        client = _make_client([])
        benchmark = adapter.score(results, client, model_name="test")
        assert benchmark.summary["errors"] == 1
        assert benchmark.summary["answered"] == 0


# ---------------------------------------------------------------------------
# Adapter: save results
# ---------------------------------------------------------------------------


class TestSaveResults:
    def test_save_jsonl(self, tmp_path):
        results = [
            DiscoveryBenchResult(
                index=0,
                domain="biology",
                question_type="variables",
                gold_hypothesis="Gold hypothesis",
                predicted_hypothesis="Predicted hypothesis",
                hms_score=0.75,
            ),
        ]
        adapter = DiscoveryBenchAdapter(data_path="dummy")
        out = tmp_path / "results.jsonl"
        adapter.save_results(results, out)

        lines = out.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["domain"] == "biology"
        assert data["hms_score"] == 0.75
        assert "hms_detail" not in data  # Excluded from JSONL
