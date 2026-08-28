from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellTimeoutError


def execute_notebook(notebook_path, timeout=30):
    with open(notebook_path) as f:
        nb = nbformat.read(f, as_version=4)

    client = NotebookClient(
        nb,
        timeout=timeout,
        kernel_name="python3",
        allow_errors=True,
    )

    error_type = None
    try:
        client.execute(cwd=str(Path(notebook_path).resolve().parent))
    except CellTimeoutError:
        error_type = "timeout"
    except Exception as e:
        error_type = f"execution_error: {type(e).__name__}"

    if error_type != "timeout":
        for cell in nb.cells:
            for output in getattr(cell, "outputs", []):
                if output.get("output_type") == "error" and output.get("ename") in (
                    "ModuleNotFoundError",
                    "ImportError",
                ):
                    error_type = "import_error"
                    break

    content = _format_notebook(nb)
    return {"content": content, "error_type": error_type}


def _format_notebook(nb):
    parts = []
    for i, cell in enumerate(nb.cells):
        if cell.cell_type == "code":
            parts.append(f"### Cell {i + 1} (code)")
            parts.append(cell.source)
            outputs = _format_outputs(cell)
            if outputs:
                parts.append("#### Output")
                parts.append(outputs)
        elif cell.cell_type == "markdown":
            parts.append(f"### Cell {i + 1} (markdown)")
            parts.append(cell.source)
    return "\n\n".join(parts)


def _format_outputs(cell):
    lines = []
    for output in getattr(cell, "outputs", []):
        otype = output.get("output_type")
        if otype == "stream":
            lines.append(output.get("text", ""))
        elif otype in ("display_data", "execute_result"):
            data = output.get("data", {})
            if "text/plain" in data:
                lines.append(data["text/plain"])
        elif otype == "error":
            lines.append(f"ERROR: {output.get('ename')}: {output.get('evalue')}")
    return "\n".join(lines).strip()
