import csv
import sys

import grader


def _write_rubric(assignment_dir, text="### Ejercicio 1 — X (1 point)\nDo X.\n"):
    (assignment_dir / "rubric.txt").write_text(text)


def _write_fake_notebook(path):
    path.write_text('{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}')


def _make_assignment(tmp_path, notebook_names):
    assignment = tmp_path / "assignment"
    submissions = assignment / "submissions"
    submissions.mkdir(parents=True)
    _write_rubric(assignment)
    for name in notebook_names:
        _write_fake_notebook(submissions / name)
    return assignment


def test_end_to_end_grading_writes_csv(tmp_path, monkeypatch):
    assignment = _make_assignment(tmp_path, ["student.ipynb"])

    monkeypatch.setattr(grader, "execute_notebook", lambda path, **kw: {"content": "code", "error_type": None})
    monkeypatch.setattr(
        grader, "evaluate_notebook", lambda **kwargs: {"grade": 9.5, "comment": "Great job", "exercises": []}
    )
    monkeypatch.setattr(sys, "argv", ["grader.py", "--assignment", str(assignment)])

    grader.main()

    rows = list(csv.DictReader((assignment / "grades.csv").open()))
    assert len(rows) == 1
    assert rows[0]["filename"] == "student.ipynb"
    assert rows[0]["grade"] == "9.5"
    assert rows[0]["comment"] == "Great job"


def test_batch_continues_after_one_notebook_fails(tmp_path, monkeypatch):
    assignment = _make_assignment(tmp_path, ["a_broken.ipynb", "b_ok.ipynb"])

    def fake_execute(path, **kwargs):
        if "broken" in path:
            raise RuntimeError("corrupted notebook")
        return {"content": "code", "error_type": None}

    monkeypatch.setattr(grader, "execute_notebook", fake_execute)
    monkeypatch.setattr(
        grader, "evaluate_notebook", lambda **kwargs: {"grade": 7.0, "comment": "ok", "exercises": []}
    )
    monkeypatch.setattr(sys, "argv", ["grader.py", "--assignment", str(assignment)])

    grader.main()

    rows = {row["filename"]: row for row in csv.DictReader((assignment / "grades.csv").open())}
    assert len(rows) == 2
    assert "Grading failed" in rows["a_broken.ipynb"]["comment"]
    assert rows["a_broken.ipynb"]["grade"] == "0"
    assert rows["b_ok.ipynb"]["grade"] == "7.0"


def test_llm_validation_failure_is_isolated_like_any_other_error(tmp_path, monkeypatch):
    from evaluator import LLMResponseError

    assignment = _make_assignment(tmp_path, ["student.ipynb"])

    monkeypatch.setattr(grader, "execute_notebook", lambda path, **kw: {"content": "code", "error_type": None})

    def fake_evaluate(**kwargs):
        raise LLMResponseError("LLM response is not valid JSON")

    monkeypatch.setattr(grader, "evaluate_notebook", fake_evaluate)
    monkeypatch.setattr(sys, "argv", ["grader.py", "--assignment", str(assignment)])

    grader.main()

    rows = list(csv.DictReader((assignment / "grades.csv").open()))
    assert len(rows) == 1
    assert "LLMResponseError" in rows[0]["comment"]


def test_output_csv_has_expected_columns(tmp_path, monkeypatch):
    assignment = _make_assignment(tmp_path, ["student.ipynb"])

    monkeypatch.setattr(grader, "execute_notebook", lambda path, **kw: {"content": "code", "error_type": None})
    monkeypatch.setattr(
        grader, "evaluate_notebook", lambda **kwargs: {"grade": 5.0, "comment": "meh", "exercises": []}
    )
    monkeypatch.setattr(sys, "argv", ["grader.py", "--assignment", str(assignment)])

    grader.main()

    with (assignment / "grades.csv").open() as f:
        header = next(csv.reader(f))
    assert header == ["filename", "grade", "comment"]
