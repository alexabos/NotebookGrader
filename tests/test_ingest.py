import csv
from pathlib import Path

from ingest import ingest, load_roster


def _make_submission_folder(source_dir, name, moodle_id, notebook_names=("Unidad_ejercicios_entrega.ipynb",)):
    folder = source_dir / f"{name}_{moodle_id}_assignsubmission_file"
    folder.mkdir(parents=True)
    for notebook_name in notebook_names:
        (folder / notebook_name).write_text('{"cells": [], "nbformat": 4, "nbformat_minor": 5}')
    return folder


def _make_course(tmp_path, course="intro_python", unit="unidad2", with_rubric=True):
    unit_dir = tmp_path / "courses" / course / unit
    unit_dir.mkdir(parents=True)
    if with_rubric:
        (unit_dir / "rubric.txt").write_text("### Ejercicio 1 — X (1 point)\n")
    return tmp_path / "courses"


def test_fresh_roster_creates_ids_and_copies_notebooks(tmp_path):
    source = tmp_path / "moodle_export"
    _make_submission_folder(source, "Ana Perez", "635842")
    courses_root = _make_course(tmp_path)

    result = ingest(source, "intro_python", "unidad2", courses_root=courses_root)

    assert len(result["processed"]) == 1
    entry = result["processed"][0]
    assert entry["student_id"] == "S001"
    assert entry["name"] == "Ana Perez"

    dest = courses_root / "intro_python" / "unidad2" / "submissions" / "S001.ipynb"
    assert dest.is_file()

    roster = load_roster(courses_root / "intro_python" / "roster.csv")
    assert roster == [{"student_id": "S001", "name": "Ana Perez"}]


def test_existing_roster_entry_is_reused(tmp_path):
    courses_root = _make_course(tmp_path)
    roster_path = courses_root / "intro_python" / "roster.csv"
    roster_path.write_text("student_id,name\nS001,Ana Perez\n")

    source = tmp_path / "moodle_export"
    _make_submission_folder(source, "Ana Perez", "999999")

    result = ingest(source, "intro_python", "unidad2", courses_root=courses_root)

    assert result["processed"][0]["student_id"] == "S001"
    assert result["new_roster_entries"] == []


def test_new_name_gets_next_sequential_id(tmp_path):
    courses_root = _make_course(tmp_path)
    (courses_root / "intro_python").mkdir(exist_ok=True)
    (courses_root / "intro_python" / "roster.csv").write_text("student_id,name\nS001,Ana Perez\n")

    source = tmp_path / "moodle_export"
    _make_submission_folder(source, "Bruno Diaz", "111111")

    result = ingest(source, "intro_python", "unidad2", courses_root=courses_root)

    assert result["processed"][0]["student_id"] == "S002"


def test_folder_with_no_notebook_is_skipped(tmp_path):
    source = tmp_path / "moodle_export"
    folder = source / "Ana Perez_635842_assignsubmission_file"
    folder.mkdir(parents=True)
    (folder / "readme.txt").write_text("not a notebook")
    courses_root = _make_course(tmp_path)

    result = ingest(source, "intro_python", "unidad2", courses_root=courses_root)

    assert result["processed"] == []
    assert len(result["skipped"]) == 1
    assert "no .ipynb" in result["skipped"][0]["reason"]


def test_folder_with_multiple_notebooks_is_skipped(tmp_path):
    source = tmp_path / "moodle_export"
    _make_submission_folder(source, "Ana Perez", "635842", notebook_names=("a.ipynb", "b.ipynb"))
    courses_root = _make_course(tmp_path)

    result = ingest(source, "intro_python", "unidad2", courses_root=courses_root)

    assert result["processed"] == []
    assert len(result["skipped"]) == 1
    assert "multiple" in result["skipped"][0]["reason"]


def test_folder_not_matching_moodle_naming_is_ignored(tmp_path):
    source = tmp_path / "moodle_export"
    source.mkdir(parents=True)
    stray = source / "some_other_folder"
    stray.mkdir()
    (stray / "notes.ipynb").write_text("{}")
    courses_root = _make_course(tmp_path)

    result = ingest(source, "intro_python", "unidad2", courses_root=courses_root)

    assert result["processed"] == []
    assert result["skipped"] == []


def test_near_duplicate_name_is_flagged_not_merged(tmp_path):
    courses_root = _make_course(tmp_path)
    (courses_root / "intro_python").mkdir(exist_ok=True)
    (courses_root / "intro_python" / "roster.csv").write_text("student_id,name\nS001,José Pérez\n")

    source = tmp_path / "moodle_export"
    _make_submission_folder(source, "Jose Perez", "222222")

    result = ingest(source, "intro_python", "unidad2", courses_root=courses_root)

    assert len(result["duplicate_warnings"]) == 1
    assert result["duplicate_warnings"][0]["similar_to"] == "José Pérez"
    # still gets its own new id rather than being silently merged into S001
    assert result["processed"][0]["student_id"] == "S002"
    assert len(result["new_roster_entries"]) == 1


def test_reingesting_same_source_reuses_ids_and_overwrites(tmp_path):
    source = tmp_path / "moodle_export"
    _make_submission_folder(source, "Ana Perez", "635842")
    courses_root = _make_course(tmp_path)

    first = ingest(source, "intro_python", "unidad2", courses_root=courses_root)
    second = ingest(source, "intro_python", "unidad2", courses_root=courses_root)

    assert first["processed"][0]["student_id"] == second["processed"][0]["student_id"]
    assert second["new_roster_entries"] == []
    assert second["processed"][0]["overwritten"] is True

    roster = load_roster(courses_root / "intro_python" / "roster.csv")
    assert len(roster) == 1


def test_missing_rubric_produces_warning_but_still_ingests(tmp_path):
    source = tmp_path / "moodle_export"
    _make_submission_folder(source, "Ana Perez", "635842")
    courses_root = _make_course(tmp_path, with_rubric=False)

    result = ingest(source, "intro_python", "unidad2", courses_root=courses_root)

    assert len(result["processed"]) == 1
    assert any("rubric.txt not found" in w for w in result["warnings"])


def test_roster_is_shared_across_units_in_same_course(tmp_path):
    courses_root = _make_course(tmp_path, unit="unidad2")
    _make_course(tmp_path, unit="unidad3")

    source2 = tmp_path / "moodle_export_u2"
    _make_submission_folder(source2, "Ana Perez", "111111")
    result2 = ingest(source2, "intro_python", "unidad2", courses_root=courses_root)

    source3 = tmp_path / "moodle_export_u3"
    _make_submission_folder(source3, "Ana Perez", "222222")
    result3 = ingest(source3, "intro_python", "unidad3", courses_root=courses_root)

    assert result2["processed"][0]["student_id"] == result3["processed"][0]["student_id"]
    assert result3["new_roster_entries"] == []
