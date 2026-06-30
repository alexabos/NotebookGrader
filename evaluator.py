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

Corrige cada ejercicio individualmente asignándole los puntos que indica la rúbrica. La nota final es la suma exacta de los puntos obtenidos en cada ejercicio (máximo 10, con dos decimales).

Para cada ejercicio, indica los puntos obtenidos sobre el total (e.g. "1.25/1.5 pts") y sigue estas pautas:
- Si la solución es correcta: una frase breve confirmándolo, sin más detalle.
- Si tiene errores: explica con precisión qué está mal (error de sintaxis, lógica incorrecta, variable mal nombrada, método incorrecto, resultado erróneo, etc.) y cómo corregirlo. Aquí sí sé exhaustivo.

Al final, suma los puntos de todos los ejercicios para obtener la nota final con dos decimales.

Dirígete al estudiante directamente en español, con un tono cercano y motivador.

Responde exactamente en este formato (sin texto adicional):
GRADE: <suma total con dos decimales, entre 0.00 y 10.00>
COMMENT: <comentario detallado en español, ejercicio por ejercicio con puntos obtenidos, errores concretos y sugerencias de mejora>"""

    message = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    return _parse_response(message.content[0].text)


def _parse_response(text):
    grade_match = re.search(r"GRADE:\s*([\d]+(?:[.,]\d+)?)", text)
    comment_match = re.search(r"COMMENT:\s*(.+)", text, re.DOTALL)

    grade = round(float(grade_match.group(1).replace(",", ".")), 2) if grade_match else 0.0
    grade = max(0.0, min(10.0, grade))

    comment = comment_match.group(1).strip() if comment_match else text.strip()

    return {"grade": grade, "comment": comment}
