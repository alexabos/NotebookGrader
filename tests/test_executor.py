import nbformat
from nbformat.v4 import new_code_cell, new_notebook

from executor import execute_notebook


def _write_notebook(path, cells):
    nbformat.write(new_notebook(cells=cells), path)


def test_valid_notebook_executes_and_captures_output(tmp_path):
    path = tmp_path / "valid.ipynb"
    _write_notebook(path, [new_code_cell("print('hello')")])

    result = execute_notebook(str(path))

    assert result["error_type"] is None
    assert "hello" in result["content"]
    assert "Cell 1 (code)" in result["content"]


def test_notebook_with_runtime_error_is_not_flagged_as_system_error(tmp_path):
    path = tmp_path / "runtime_error.ipynb"
    _write_notebook(path, [new_code_cell("1 / 0")])

    result = execute_notebook(str(path))

    # allow_errors=True: a normal wrong-answer runtime error is just notebook content
    # for the LLM to grade, not a pipeline-level failure.
    assert result["error_type"] is None
    assert "ZeroDivisionError" in result["content"]


def test_notebook_with_missing_import_is_flagged(tmp_path):
    path = tmp_path / "import_error.ipynb"
    _write_notebook(path, [new_code_cell("import this_module_does_not_exist_xyz")])

    result = execute_notebook(str(path))

    assert result["error_type"] == "import_error"


def test_notebook_timeout_is_flagged(tmp_path):
    path = tmp_path / "timeout.ipynb"
    _write_notebook(path, [new_code_cell("import time; time.sleep(5)")])

    result = execute_notebook(str(path), timeout=1)

    assert result["error_type"] == "timeout"


def test_markdown_cells_are_included_in_content(tmp_path):
    path = tmp_path / "markdown.ipynb"
    _write_notebook(
        path,
        [nbformat.v4.new_markdown_cell("# Exercise 1"), new_code_cell("x = 1")],
    )

    result = execute_notebook(str(path))

    assert "Exercise 1" in result["content"]
