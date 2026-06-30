import re
import anthropic

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def evaluate_notebook(notebook_content, rubric, error_type=None):
    error_note = ""
    if error_type == "timeout":
        error_note = "\nNote: This notebook timed out during execution — some cells did not finish."
    elif error_type == "import_error":
        error_note = "\nNote: This notebook raised an ImportError or ModuleNotFoundError — a required package was missing."
    elif error_type and error_type.startswith("execution_error"):
        error_note = f"\nNote: Execution failed with {error_type}."

    prompt = f"""Eres un profesor de programación corrigiendo la entrega de un estudiante en un Jupyter notebook.

## Rúbrica de evaluación
{rubric}

## Notebook del estudiante
{notebook_content}
{error_note}

Evalúa la entrega con una nota de 0 a 10 siguiendo la rúbrica. Sé justo, detallado y constructivo.

Para cada ejercicio, indica:
- Si la solución es correcta o incorrecta
- Qué errores concretos tiene (si los hay): errores de sintaxis, lógica incorrecta, nombre de variable incorrecto, método mal utilizado, resultado erróneo, etc.
- Una breve sugerencia de mejora cuando corresponda

Dirígete al estudiante directamente en español, con un tono cercano y motivador.

Responde exactamente en este formato (sin texto adicional):
GRADE: <entero 0-10>
COMMENT: <comentario detallado en español, ejercicio por ejercicio, explicando errores concretos y sugerencias de mejora>"""

    message = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    return _parse_response(message.content[0].text)


def _parse_response(text):
    grade_match = re.search(r"GRADE:\s*(\d+)", text)
    comment_match = re.search(r"COMMENT:\s*(.+)", text, re.DOTALL)

    grade = int(grade_match.group(1)) if grade_match else 0
    grade = max(0, min(10, grade))

    comment = comment_match.group(1).strip() if comment_match else text.strip()

    return {"grade": grade, "comment": comment}
