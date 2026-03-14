"""Tests for QRData benchmark adapter (no real API calls)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sreg.benchmarks.qrdata.adapter import (
    QRDataAdapter,
    QRDataResult,
    _check_multiple_choice,
    _check_numerical,
    _extract_number,
)
from sreg.inference.protocol import ChatResponse, FinishReason, Message, MessageRole, Usage

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_QRDATA = [
    {
        "data_description": "A dataset about ice thickness measurements.",
        "question": "What is the correlation coefficient between temp and thickness?",
        "answer": "0.85",
        "data_files": ["ice.csv"],
        "meta_data": {
            "keywords": ["Statistics"],
            "question_type": "numerical",
            "reference": "Test textbook",
        },
    },
    {
        "data_description": "Treatment effect study on blood pressure.",
        "question": "Which group has lower mean blood pressure?",
        "answer": "B",
        "data_files": ["bp.csv"],
        "meta_data": {
            "keywords": ["Causality", "Observational data"],
            "question_type": "multiple_choice",
            "reference": "Test paper",
            "multiple_choices": ["treatment group", "control group", "no difference"],
        },
    },
    {
        "data_description": "Causal graph discovery dataset.",
        "question": "What is the ATE of X on Y?",
        "answer": "-0.026",
        "data_files": ["causal.csv"],
        "meta_data": {
            "keywords": ["Causality"],
            "question_type": "numerical",
            "reference": "Test book",
        },
    },
    {
        "data_description": "Survey about education and income.",
        "question": "Is the relationship between education and income significant?",
        "answer": "yes",
        "data_files": ["survey.csv"],
        "meta_data": {
            "keywords": ["Statistics"],
            "question_type": "multiple_choice",
            "reference": "Test book",
            "multiple_choices": ["yes", "no"],
        },
    },
]


@pytest.fixture
def qrdata_json(tmp_path: Path) -> Path:
    """Write sample QRData to a temp JSON file."""
    path = tmp_path / "QRData.json"
    path.write_text(json.dumps(SAMPLE_QRDATA), encoding="utf-8")
    # Create dummy CSV files
    csv_dir = tmp_path / "csvs"
    csv_dir.mkdir()
    for name in ["ice.csv", "bp.csv", "causal.csv", "survey.csv"]:
        (csv_dir / name).write_text("col1,col2\n1,2\n3,4\n", encoding="utf-8")
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
# Tests: _extract_number
# ---------------------------------------------------------------------------


class TestExtractNumber:
    @pytest.mark.parametrize(
        "text, expected",
        [
            ("0.85", 0.85),
            ("-0.026", -0.026),
            ("5.36%", 0.0536),
            ("42", 42.0),
            ("The value is 3.14", 3.14),
            ("-12.5%", -0.125),
        ],
    )
    def test_extracts_number(self, text: str, expected: float):
        assert _extract_number(text) == pytest.approx(expected)

    def test_returns_none_for_no_number(self):
        assert _extract_number("no numbers here") is None

    def test_returns_none_for_empty(self):
        assert _extract_number("") is None


# ---------------------------------------------------------------------------
# Tests: _check_numerical
# ---------------------------------------------------------------------------


class TestCheckNumerical:
    def test_exact_match(self):
        assert _check_numerical("0.85", "0.85") is True

    def test_within_tolerance(self):
        # 0.85 * 0.97 = 0.8245, 0.85 * 1.03 = 0.8755
        assert _check_numerical("0.84", "0.85") is True
        assert _check_numerical("0.87", "0.85") is True

    def test_outside_tolerance(self):
        assert _check_numerical("0.80", "0.85") is False
        assert _check_numerical("0.90", "0.85") is False

    def test_negative_values(self):
        # -0.026: bounds are (-0.02678, -0.02522) after swap
        assert _check_numerical("-0.026", "-0.026") is True
        assert _check_numerical("-0.0265", "-0.026") is True  # within 3%
        assert _check_numerical("-0.025", "-0.026") is False  # outside (> -0.02522)
        assert _check_numerical("-0.03", "-0.026") is False  # outside (< -0.02678)

    def test_percentage(self):
        assert _check_numerical("5.36%", "5.36%") is True

    def test_zero_gold(self):
        assert _check_numerical("0", "0") is True
        assert _check_numerical("0.001", "0") is False

    def test_unparseable(self):
        assert _check_numerical("abc", "0.85") is False
        assert _check_numerical("0.85", "abc") is False


# ---------------------------------------------------------------------------
# Tests: _check_multiple_choice
# ---------------------------------------------------------------------------


class TestCheckMultipleChoice:
    def test_exact_match(self):
        assert _check_multiple_choice("B", "B") is True

    def test_case_insensitive(self):
        assert _check_multiple_choice("b", "B") is True
        assert _check_multiple_choice("B", "b") is True

    def test_prefix_match(self):
        assert _check_multiple_choice("treatment group with extras", "treatment group") is True

    def test_mismatch(self):
        assert _check_multiple_choice("A", "B") is False

    def test_word_answer(self):
        assert _check_multiple_choice("yes", "yes") is True
        assert _check_multiple_choice("Yes", "yes") is True
        assert _check_multiple_choice("no", "yes") is False


# ---------------------------------------------------------------------------
# Tests: load
# ---------------------------------------------------------------------------


class TestLoad:
    def test_load_all(self, qrdata_json: Path):
        adapter = QRDataAdapter(data_path=qrdata_json, csv_dir=qrdata_json.parent / "csvs")
        examples = adapter.load(subset="all")
        assert len(examples) == 4

    def test_load_causal_subset(self, qrdata_json: Path):
        adapter = QRDataAdapter(data_path=qrdata_json, csv_dir=qrdata_json.parent / "csvs")
        examples = adapter.load(subset="causal")
        assert len(examples) == 2
        assert all(e.is_causal for e in examples)

    def test_load_statistical_subset(self, qrdata_json: Path):
        adapter = QRDataAdapter(data_path=qrdata_json, csv_dir=qrdata_json.parent / "csvs")
        examples = adapter.load(subset="statistical")
        assert len(examples) == 2
        assert all(not e.is_causal for e in examples)

    def test_load_parses_fields(self, qrdata_json: Path):
        adapter = QRDataAdapter(data_path=qrdata_json, csv_dir=qrdata_json.parent / "csvs")
        examples = adapter.load()
        ex = examples[1]  # the MC causal one
        assert ex.question_type == "multiple_choice"
        assert ex.is_causal is True
        assert ex.multiple_choices is not None
        assert len(ex.multiple_choices) == 3

    def test_load_dev_subset(self, qrdata_json: Path):
        adapter = QRDataAdapter(data_path=qrdata_json, csv_dir=qrdata_json.parent / "csvs")
        examples = adapter.load(subset="dev", dev_count=2)
        assert len(examples) == 2

    def test_load_dev_is_deterministic(self, qrdata_json: Path):
        adapter = QRDataAdapter(data_path=qrdata_json, csv_dir=qrdata_json.parent / "csvs")
        ex1 = adapter.load(subset="dev", seed=42, dev_count=2)
        ex2 = adapter.load(subset="dev", seed=42, dev_count=2)
        assert [e.index for e in ex1] == [e.index for e in ex2]


# ---------------------------------------------------------------------------
# Tests: parse_answer
# ---------------------------------------------------------------------------


class TestParseAnswer:
    @pytest.mark.parametrize(
        "raw, qtype, expected",
        [
            ("Final answer: 0.85", "numerical", "0.85"),
            ("Final answer: B", "multiple_choice", "B"),
            ("Final answer: yes", "multiple_choice", "yes"),
            ("The answer is B.", "multiple_choice", "B"),
            ("... therefore B", "multiple_choice", "B"),
            ("Calculation gives 3.14", "numerical", "3.14"),
            ("Result: -0.026", "numerical", "-0.026"),
        ],
    )
    def test_parses_answer(self, raw: str, qtype: str, expected: str):
        assert QRDataAdapter._parse_answer(raw, qtype) == expected

    def test_unparseable(self):
        assert QRDataAdapter._parse_answer("I don't know", "multiple_choice") is None


# ---------------------------------------------------------------------------
# Tests: prompt composition
# ---------------------------------------------------------------------------


class TestPrompt:
    def test_includes_data(self, qrdata_json: Path):
        adapter = QRDataAdapter(data_path=qrdata_json, csv_dir=qrdata_json.parent / "csvs")
        examples = adapter.load()
        prompt = adapter._compose_prompt(examples[0])
        assert "Dataset description:" in prompt
        assert "col1,col2" in prompt  # CSV header
        assert "Final answer:" in prompt

    def test_includes_choices_for_mc(self, qrdata_json: Path):
        adapter = QRDataAdapter(data_path=qrdata_json, csv_dir=qrdata_json.parent / "csvs")
        examples = adapter.load()
        mc_ex = examples[1]
        prompt = adapter._compose_prompt(mc_ex)
        assert "A." in prompt
        assert "B." in prompt


# ---------------------------------------------------------------------------
# Tests: run
# ---------------------------------------------------------------------------


class TestRun:
    def test_run_correct_answers(self, qrdata_json: Path):
        adapter = QRDataAdapter(data_path=qrdata_json, csv_dir=qrdata_json.parent / "csvs")
        examples = adapter.load()

        answers = [
            "Final answer: 0.85",
            "Final answer: B",
            "Final answer: -0.026",
            "Final answer: yes",
        ]
        client = _make_mock_client(answers)
        results = adapter.run(client, examples)

        assert len(results) == 4
        assert all(r.correct for r in results)

    def test_run_error_tracking(self, qrdata_json: Path):
        adapter = QRDataAdapter(data_path=qrdata_json, csv_dir=qrdata_json.parent / "csvs")
        examples = adapter.load()[:1]

        client = MagicMock()
        client.chat.side_effect = RuntimeError("API down")
        results = adapter.run(client, examples, max_consecutive_errors=5)

        assert results[0].error is True
        assert results[0].correct is False

    def test_run_aborts_on_consecutive_errors(self, qrdata_json: Path):
        adapter = QRDataAdapter(data_path=qrdata_json, csv_dir=qrdata_json.parent / "csvs")
        examples = adapter.load()

        client = MagicMock()
        client.chat.side_effect = RuntimeError("API down")

        with pytest.raises(RuntimeError, match="consecutive API errors"):
            adapter.run(client, examples, max_consecutive_errors=3)


# ---------------------------------------------------------------------------
# Tests: score
# ---------------------------------------------------------------------------


class TestScore:
    def test_score_separates_causal_and_statistical(self):
        results = [
            QRDataResult(
                index=0, question_type="numerical", is_causal=False,
                gold="0.85", predicted="0.85", correct=True,
            ),
            QRDataResult(
                index=1, question_type="multiple_choice", is_causal=True,
                gold="B", predicted="A", correct=False,
            ),
            QRDataResult(
                index=2, question_type="numerical", is_causal=True,
                gold="-0.026", predicted="-0.025", correct=True,
            ),
        ]
        adapter = QRDataAdapter(data_path="dummy.json")
        bench = adapter.score(results, model_name="test")

        assert bench.metric_value == pytest.approx(2 / 3)
        assert bench.summary["causal_accuracy"] == pytest.approx(0.5)
        assert bench.summary["statistical_accuracy"] == pytest.approx(1.0)
        assert bench.summary["causal_count"] == 2
        assert bench.summary["statistical_count"] == 1

    def test_score_tracks_errors(self):
        results = [
            QRDataResult(
                index=0, question_type="numerical", is_causal=False,
                gold="1.0", predicted=None, correct=False, error=True,
            ),
            QRDataResult(
                index=1, question_type="numerical", is_causal=False,
                gold="1.0", predicted=None, correct=False, error=False,
            ),
        ]
        adapter = QRDataAdapter(data_path="dummy.json")
        bench = adapter.score(results, model_name="test")

        assert bench.summary["errors"] == 1
        assert bench.summary["unparseable"] == 1
        assert bench.summary["answered"] == 1

    def test_score_empty(self):
        adapter = QRDataAdapter(data_path="dummy.json")
        bench = adapter.score([], model_name="test")
        assert bench.metric_value == 0.0


# ---------------------------------------------------------------------------
# Tests: save_results
# ---------------------------------------------------------------------------


class TestSaveResults:
    def test_save_jsonl(self, tmp_path: Path):
        results = [
            QRDataResult(
                index=0, question_type="numerical", is_causal=True,
                gold="0.85", predicted="0.85", correct=True,
            ),
        ]
        output = tmp_path / "results.jsonl"
        adapter = QRDataAdapter(data_path="dummy.json")
        adapter.save_results(results, output)

        lines = output.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["correct"] is True
        assert parsed["is_causal"] is True
