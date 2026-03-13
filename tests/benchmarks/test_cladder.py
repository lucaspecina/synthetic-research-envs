"""Tests for CLadder benchmark adapter (no real API calls)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sreg.benchmarks.cladder.adapter import CLadderAdapter, CLadderExample, CLadderResult
from sreg.inference.protocol import ChatResponse, FinishReason, Message, MessageRole, Usage
from sreg.models.benchmark import BenchmarkResult, BenchmarkStatus

# ---------------------------------------------------------------------------
# Fixtures: fabricated CLadder data
# ---------------------------------------------------------------------------

SAMPLE_CLADDER_DATA = [
    {
        "question_id": "q001",
        "background": "Imagine a self-contained world with the variables X, Y, Z.",
        "given_info": "The probability of X is 0.3. The probability of Y given X is 0.8.",
        "question": "If we intervene on X, will Y increase?",
        "answer": "yes",
        "sensical": 1,
        "meta": {"query": {"rung": 2, "query_type": "ate"}},
    },
    {
        "question_id": "q002",
        "background": "Consider a world with A, B, C.",
        "given_info": "P(A) = 0.5. P(B|A) = 0.9.",
        "question": "Is A correlated with B?",
        "answer": "yes",
        "sensical": 1,
        "meta": {"query": {"rung": 1, "query_type": "correlation"}},
    },
    {
        "question_id": "q003",
        "background": "In a world with D, E, F.",
        "given_info": "P(D) = 0.2.",
        "question": "Had D been different, would E change?",
        "answer": "no",
        "sensical": 0,
        "meta": {"query": {"rung": 3, "query_type": "ett"}},
    },
    {
        "question_id": "q004",
        "background": "Variables G, H exist.",
        "given_info": "P(G) = 0.7.",
        "question": "Does G cause H?",
        "answer": "no",
        "sensical": -1,
        "meta": {"query": {"rung": 2, "query_type": "backdoor"}},
    },
]


@pytest.fixture
def cladder_json(tmp_path: Path) -> Path:
    """Write sample CLadder data to a temp JSON file."""
    path = tmp_path / "cladder-v1-balanced.json"
    path.write_text(json.dumps(SAMPLE_CLADDER_DATA), encoding="utf-8")
    return path


def _make_mock_client(answers: list[str]) -> MagicMock:
    """Create a mock ModelClient that returns pre-defined answers."""
    client = MagicMock()
    responses = []
    for ans in answers:
        responses.append(
            ChatResponse(
                message=Message(role=MessageRole.ASSISTANT, content=ans),
                finish_reason=FinishReason.STOP,
                tool_calls=[],
                usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15),
            )
        )
    client.chat.side_effect = responses
    return client


# ---------------------------------------------------------------------------
# Tests: load
# ---------------------------------------------------------------------------


class TestLoad:
    def test_load_all(self, cladder_json: Path):
        adapter = CLadderAdapter(data_path=cladder_json)
        examples = adapter.load(subset="all")
        assert len(examples) == 4
        assert all(isinstance(e, CLadderExample) for e in examples)

    def test_load_parses_fields(self, cladder_json: Path):
        adapter = CLadderAdapter(data_path=cladder_json)
        examples = adapter.load()
        ex = next(e for e in examples if e.question_id == "q001")
        assert ex.rung == 2
        assert ex.query_type == "ate"
        assert ex.answer == "yes"
        assert ex.sensical == 1

    def test_load_dev_subsample(self, cladder_json: Path):
        adapter = CLadderAdapter(data_path=cladder_json)
        # With per_type=1 and 4 different types, we get 4 examples (all of them)
        examples = adapter.load(subset="dev", dev_per_type=1)
        assert len(examples) == 4  # one per type, but we only have 4

    def test_load_dev_subsample_limits(self, cladder_json: Path):
        # Create data with many examples of same type
        data = []
        for i in range(20):
            data.append({
                "question_id": f"q{i:03d}",
                "background": "bg",
                "given_info": "info",
                "question": "q?",
                "answer": "yes",
                "sensical": 1,
                "meta": {"query": {"rung": 1, "query_type": "ate"}},
            })
        path = cladder_json.parent / "many.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        adapter = CLadderAdapter(data_path=path)
        examples = adapter.load(subset="dev", dev_per_type=5)
        assert len(examples) == 5  # only 1 type, capped at 5

    def test_load_dev_is_deterministic(self, cladder_json: Path):
        adapter = CLadderAdapter(data_path=cladder_json)
        ex1 = adapter.load(subset="dev", seed=42)
        ex2 = adapter.load(subset="dev", seed=42)
        assert [e.question_id for e in ex1] == [e.question_id for e in ex2]


# ---------------------------------------------------------------------------
# Tests: prompt composition
# ---------------------------------------------------------------------------


class TestPrompt:
    def test_compose_prompt_includes_all_parts(self):
        ex = CLadderExample(
            question_id="q1",
            background="BG here.",
            given_info="INFO here.",
            question="Is X true?",
            answer="yes",
            rung=1,
            query_type="marginal",
            sensical=1,
        )
        prompt = CLadderAdapter._compose_prompt(ex)
        assert "BG here." in prompt
        assert "INFO here." in prompt
        assert "Is X true?" in prompt
        assert '"Yes" or "No"' in prompt

    def test_compose_prompt_handles_empty_parts(self):
        ex = CLadderExample(
            question_id="q1",
            background="",
            given_info="",
            question="Question?",
            answer="no",
            rung=1,
            query_type="marginal",
            sensical=1,
        )
        prompt = CLadderAdapter._compose_prompt(ex)
        assert "Question?" in prompt


# ---------------------------------------------------------------------------
# Tests: answer parsing
# ---------------------------------------------------------------------------


class TestParseAnswer:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("Yes, because...", "yes"),
            ("yes", "yes"),
            ("YES!", "yes"),
            ("No, the evidence...", "no"),
            ("no", "no"),
            ("NO.", "no"),
            ("  Yes  ", "yes"),
            ("  No  ", "no"),
            # Markdown formatting
            ("**Yes**, because...", "yes"),
            ("**No**.", "no"),
            ("*Yes*", "yes"),
            ("# Yes", "yes"),
            # "Answer:" patterns (Codex fix)
            ("Answer: Yes", "yes"),
            ("Answer: No", "no"),
            ("The answer is yes.", "yes"),
            ("The answer is no.", "no"),
            ("answer: YES", "yes"),
        ],
    )
    def test_valid_answers(self, raw: str, expected: str):
        assert CLadderAdapter._parse_answer(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "The probability is 0.7",
            "Maybe",
            "",
            "It depends",
            "I think so",
        ],
    )
    def test_unparseable_answers(self, raw: str):
        assert CLadderAdapter._parse_answer(raw) is None


# ---------------------------------------------------------------------------
# Tests: run
# ---------------------------------------------------------------------------


class TestRun:
    def test_run_correct_answers(self, cladder_json: Path):
        adapter = CLadderAdapter(data_path=cladder_json)
        examples = adapter.load()

        # Mock returns correct answers
        answers = [ex.answer.capitalize() for ex in examples]
        client = _make_mock_client(answers)

        results = adapter.run(client, examples)
        assert len(results) == 4
        assert all(r.correct for r in results)
        assert all(isinstance(r, CLadderResult) for r in results)

    def test_run_wrong_answers(self, cladder_json: Path):
        adapter = CLadderAdapter(data_path=cladder_json)
        examples = adapter.load()

        # Mock returns wrong answers (flip yes/no)
        answers = ["No" if ex.answer == "yes" else "Yes" for ex in examples]
        client = _make_mock_client(answers)

        results = adapter.run(client, examples)
        assert all(not r.correct for r in results)

    def test_run_handles_api_error(self, cladder_json: Path):
        adapter = CLadderAdapter(data_path=cladder_json)
        examples = adapter.load()[:1]  # just one

        client = MagicMock()
        client.chat.side_effect = RuntimeError("API down")

        results = adapter.run(client, examples, max_consecutive_errors=5)
        assert len(results) == 1
        assert not results[0].correct
        assert results[0].predicted is None
        assert results[0].error is True
        assert "ERROR" in results[0].raw_response

    def test_run_error_flag_not_set_on_success(self, cladder_json: Path):
        adapter = CLadderAdapter(data_path=cladder_json)
        examples = adapter.load()[:1]
        client = _make_mock_client(["Yes"])
        results = adapter.run(client, examples)
        assert results[0].error is False

    def test_run_aborts_on_consecutive_errors(self, cladder_json: Path):
        adapter = CLadderAdapter(data_path=cladder_json)
        examples = adapter.load()  # 4 examples

        client = MagicMock()
        client.chat.side_effect = RuntimeError("API down")

        with pytest.raises(RuntimeError, match="consecutive API errors"):
            adapter.run(client, examples, max_consecutive_errors=3)

    def test_run_resets_error_counter_on_success(self, cladder_json: Path):
        adapter = CLadderAdapter(data_path=cladder_json)
        examples = adapter.load()  # 4 examples

        # error, success, error, error -> should NOT abort (max=3)
        client = MagicMock()
        client.chat.side_effect = [
            RuntimeError("err1"),
            ChatResponse(
                message=Message(role=MessageRole.ASSISTANT, content="Yes"),
                finish_reason=FinishReason.STOP,
                tool_calls=[],
                usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15),
            ),
            RuntimeError("err2"),
            RuntimeError("err3"),
        ]
        results = adapter.run(client, examples, max_consecutive_errors=3)
        assert len(results) == 4
        assert sum(r.error for r in results) == 3

    def test_run_unparseable_response(self, cladder_json: Path):
        adapter = CLadderAdapter(data_path=cladder_json)
        examples = adapter.load()[:1]

        client = _make_mock_client(["I think the answer might be affirmative"])
        results = adapter.run(client, examples)
        assert results[0].predicted is None
        assert not results[0].correct
        assert results[0].error is False  # not an API error, just unparseable


# ---------------------------------------------------------------------------
# Tests: score
# ---------------------------------------------------------------------------


class TestScore:
    def test_score_perfect(self):
        results = [
            CLadderResult(
                question_id="q1", rung=1, query_type="marginal", sensical=1,
                gold="yes", predicted="yes", correct=True,
            ),
            CLadderResult(
                question_id="q2", rung=2, query_type="ate", sensical=1,
                gold="no", predicted="no", correct=True,
            ),
        ]
        adapter = CLadderAdapter(data_path="dummy.json")
        bench = adapter.score(results, model_name="test-model")

        assert isinstance(bench, BenchmarkResult)
        assert bench.benchmark == "cladder"
        assert bench.metric_value == 1.0
        assert bench.num_examples == 2
        assert bench.num_correct == 2
        assert bench.status == BenchmarkStatus.SUCCESS

    def test_score_partial(self):
        results = [
            CLadderResult(
                question_id="q1", rung=1, query_type="marginal", sensical=1,
                gold="yes", predicted="yes", correct=True,
            ),
            CLadderResult(
                question_id="q2", rung=2, query_type="ate", sensical=0,
                gold="no", predicted="yes", correct=False,
            ),
            CLadderResult(
                question_id="q3", rung=3, query_type="ett", sensical=-1,
                gold="yes", predicted=None, correct=False,
            ),
        ]
        adapter = CLadderAdapter(data_path="dummy.json")
        bench = adapter.score(results, model_name="test-model")

        assert bench.metric_value == pytest.approx(1 / 3)
        assert bench.num_correct == 1
        assert bench.summary["unparseable"] == 1
        assert bench.summary["by_rung"]["rung_1"] == 1.0
        assert bench.summary["by_rung"]["rung_2"] == 0.0
        assert bench.summary["by_sensical"]["nonsense"] == 0.0
        assert bench.summary["by_sensical"]["commonsense"] == 1.0

    def test_score_separates_errors_from_unparseable(self):
        results = [
            CLadderResult(
                question_id="q1", rung=1, query_type="marginal", sensical=1,
                gold="yes", predicted="yes", correct=True,
            ),
            CLadderResult(
                question_id="q2", rung=2, query_type="ate", sensical=1,
                gold="no", predicted=None, correct=False, error=True,
            ),
            CLadderResult(
                question_id="q3", rung=3, query_type="ett", sensical=0,
                gold="yes", predicted=None, correct=False, error=False,
            ),
        ]
        adapter = CLadderAdapter(data_path="dummy.json")
        bench = adapter.score(results, model_name="test-model")

        assert bench.summary["errors"] == 1
        assert bench.summary["unparseable"] == 1  # only q3, not q2
        assert bench.summary["answered"] == 2  # total - errors

    def test_score_empty(self):
        adapter = CLadderAdapter(data_path="dummy.json")
        bench = adapter.score([], model_name="test")
        assert bench.metric_value == 0.0
        assert bench.num_examples == 0


# ---------------------------------------------------------------------------
# Tests: save_results
# ---------------------------------------------------------------------------


class TestSaveResults:
    def test_save_jsonl(self, tmp_path: Path):
        results = [
            CLadderResult(
                question_id="q1", rung=1, query_type="marginal", sensical=1,
                gold="yes", predicted="yes", raw_response="Yes.", correct=True,
            ),
        ]
        output = tmp_path / "results.jsonl"
        adapter = CLadderAdapter(data_path="dummy.json")
        adapter.save_results(results, output)

        lines = output.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["question_id"] == "q1"
        assert parsed["correct"] is True
