import json

import pytest

from evaluator import LLMEvaluator, LLMResponseError, evaluate_notebook

RUBRIC = """### Ejercicio 1 — Variables (1 point)
Do a thing.

### Ejercicio 2 — Loops (1 point)
Do another thing.
"""


class FakeEvaluator(LLMEvaluator):
    def __init__(self, response_text):
        self.response_text = response_text
        self.last_prompt = None

    def get_response(self, prompt):
        self.last_prompt = prompt
        return self.response_text


def _response(score1=1.0, max1=1.0, score2=0.5, max2=1.0):
    return json.dumps(
        {
            "exercises": [
                {
                    "id": "ejercicio_1",
                    "title": "Variables",
                    "score": score1,
                    "max_score": max1,
                    "feedback": "Bien hecho.",
                    "issues": [],
                },
                {
                    "id": "ejercicio_2",
                    "title": "Loops",
                    "score": score2,
                    "max_score": max2,
                    "feedback": "Falta el bucle.",
                    "issues": ["No usa un bucle"],
                },
            ]
        }
    )


def test_valid_response_is_scored_by_python():
    result = evaluate_notebook("notebook", RUBRIC, evaluator=FakeEvaluator(_response()))

    assert result["grade"] == 1.5
    assert "Nota final: 1.50/10" in result["comment"]
    assert "No usa un bucle" in result["comment"]


def test_response_wrapped_in_markdown_fence_is_parsed():
    fenced = f"```json\n{_response()}\n```"

    result = evaluate_notebook("notebook", RUBRIC, evaluator=FakeEvaluator(fenced))

    assert result["grade"] == 1.5


def test_malformed_json_raises():
    with pytest.raises(LLMResponseError):
        evaluate_notebook("notebook", RUBRIC, evaluator=FakeEvaluator("not json at all"))


def test_missing_fields_raises():
    bad = json.dumps({"exercises": [{"id": "ejercicio_1", "score": 1.0}]})

    with pytest.raises(LLMResponseError):
        evaluate_notebook("notebook", RUBRIC, evaluator=FakeEvaluator(bad))


def test_non_numeric_score_raises():
    bad = json.dumps(
        {
            "exercises": [
                {"id": "ejercicio_1", "score": "a lot", "max_score": 1.0, "feedback": "x", "issues": []},
                {"id": "ejercicio_2", "score": 1.0, "max_score": 1.0, "feedback": "x", "issues": []},
            ]
        }
    )

    with pytest.raises(LLMResponseError):
        evaluate_notebook("notebook", RUBRIC, evaluator=FakeEvaluator(bad))


def test_score_outside_range_raises():
    bad = json.dumps(
        {
            "exercises": [
                {"id": "ejercicio_1", "score": 5.0, "max_score": 1.0, "feedback": "x", "issues": []},
                {"id": "ejercicio_2", "score": 1.0, "max_score": 1.0, "feedback": "x", "issues": []},
            ]
        }
    )

    with pytest.raises(LLMResponseError):
        evaluate_notebook("notebook", RUBRIC, evaluator=FakeEvaluator(bad))


def test_exercise_count_mismatch_raises():
    bad = json.dumps(
        {"exercises": [{"id": "ejercicio_1", "score": 1.0, "max_score": 1.0, "feedback": "x", "issues": []}]}
    )

    with pytest.raises(LLMResponseError):
        evaluate_notebook("notebook", RUBRIC, evaluator=FakeEvaluator(bad))


def test_unknown_exercise_id_raises():
    bad = json.dumps(
        {
            "exercises": [
                {"id": "ejercicio_1", "score": 1.0, "max_score": 1.0, "feedback": "x", "issues": []},
                {"id": "ejercicio_99", "score": 1.0, "max_score": 1.0, "feedback": "x", "issues": []},
            ]
        }
    )

    with pytest.raises(LLMResponseError):
        evaluate_notebook("notebook", RUBRIC, evaluator=FakeEvaluator(bad))


def test_duplicate_exercise_id_raises():
    bad = json.dumps(
        {
            "exercises": [
                {"id": "ejercicio_1", "score": 1.0, "max_score": 1.0, "feedback": "x", "issues": []},
                {"id": "ejercicio_1", "score": 1.0, "max_score": 1.0, "feedback": "x", "issues": []},
            ]
        }
    )

    with pytest.raises(LLMResponseError):
        evaluate_notebook("notebook", RUBRIC, evaluator=FakeEvaluator(bad))


def test_unexpected_field_raises():
    bad = json.dumps(
        {
            "exercises": [
                {
                    "id": "ejercicio_1",
                    "score": 1.0,
                    "max_score": 1.0,
                    "feedback": "x",
                    "issues": [],
                    "confidence": 0.9,
                },
                {"id": "ejercicio_2", "score": 1.0, "max_score": 1.0, "feedback": "x", "issues": []},
            ]
        }
    )

    with pytest.raises(LLMResponseError):
        evaluate_notebook("notebook", RUBRIC, evaluator=FakeEvaluator(bad))


def test_rubric_derived_max_score_overrides_llm_reported_value():
    # LLM misreports max_score for exercise 2 (2.0) vs. the rubric's true value (1.0).
    # A score that fits within the rubric's real max should still be accepted and clamped to it.
    result = evaluate_notebook(
        "notebook", RUBRIC, evaluator=FakeEvaluator(_response(score2=0.9, max2=2.0))
    )

    assert result["grade"] == 1.9


def test_freeform_rubric_without_headings_trusts_llm_max_score():
    freeform_rubric = "Grade the student's understanding of loops and variables generously."
    payload = json.dumps(
        {"exercises": [{"id": "ejercicio_1", "score": 3.0, "max_score": 5.0, "feedback": "x", "issues": []}]}
    )

    result = evaluate_notebook("notebook", freeform_rubric, evaluator=FakeEvaluator(payload))

    assert result["grade"] == 3.0
