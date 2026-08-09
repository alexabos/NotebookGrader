import json

import nbformat
import pytest
from nbformat.v4 import new_markdown_cell, new_notebook

from evaluator import LLMEvaluator, LLMResponseError, evaluate_notebook
from executor import execute_notebook


class FakeEvaluator(LLMEvaluator):
    def __init__(self, response_text):
        self.response_text = response_text

    def get_response(self, prompt):
        return self.response_text


def test_empty_notebook_executes_without_crashing(tmp_path):
    path = tmp_path / "empty.ipynb"
    nbformat.write(new_notebook(cells=[]), path)

    result = execute_notebook(str(path))

    assert result["error_type"] is None
    assert result["content"] == ""


def test_notebook_with_only_markdown_has_no_code_cells(tmp_path):
    path = tmp_path / "markdown_only.ipynb"
    nbformat.write(new_notebook(cells=[new_markdown_cell("# Incomplete submission, no code written")]), path)

    result = execute_notebook(str(path))

    assert result["error_type"] is None
    assert "Incomplete submission" in result["content"]


def test_corrupted_notebook_file_raises_instead_of_hanging(tmp_path):
    path = tmp_path / "corrupted.ipynb"
    path.write_text("{not valid json")

    with pytest.raises(Exception):
        execute_notebook(str(path))


def test_notebook_missing_required_nbformat_fields_raises(tmp_path):
    path = tmp_path / "malformed.ipynb"
    path.write_text(json.dumps({"nbformat": 4, "nbformat_minor": 5}))  # no "cells" key

    with pytest.raises(Exception):
        execute_notebook(str(path))


RUBRIC = "### Ejercicio 1 — X (1 point)\nDo X.\n"


def test_evaluator_rejects_empty_exercises_list():
    with pytest.raises(LLMResponseError):
        evaluate_notebook("", RUBRIC, evaluator=FakeEvaluator(json.dumps({"exercises": []})))


def test_evaluator_rejects_non_object_response():
    with pytest.raises(LLMResponseError):
        evaluate_notebook("", RUBRIC, evaluator=FakeEvaluator(json.dumps(["not", "an", "object"])))


def test_evaluator_rejects_response_missing_exercises_key():
    with pytest.raises(LLMResponseError):
        evaluate_notebook("", RUBRIC, evaluator=FakeEvaluator(json.dumps({"grade": 10})))
