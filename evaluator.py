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

Corrige cada ejercicio individualmente asignándole los puntos que indica la rúbrica.

Para cada ejercicio, indica los puntos obtenidos sobre el total (e.g. "1.25/1.5 pts") y sigue estas pautas:
- Si la solución es correcta: una frase breve confirmándolo, sin más detalle.
- Si tiene errores: explica con precisión qué está mal (error de sintaxis, lógica incorrecta, variable mal nombrada, método incorrecto, resultado erróneo, etc.) y cómo corregirlo. Aquí sí sé exhaustivo.

No calcules ni escribas tú la nota final del notebook (ni una suma total) en ningún sitio: el sistema la calculará automáticamente sumando los puntos que indiques por ejercicio. Limítate a puntuar cada ejercicio individualmente.

Dirígete al estudiante directamente en español, con un tono cercano y motivador.

Responde exactamente en este formato (sin texto adicional):
SCORES: <puntos obtenidos en cada ejercicio, en el mismo orden que aparecen en la rúbrica, separados por punto y coma, e.g. "1.5; 1.0; 1.5; 2.0; 2.0; 1.5">
COMMENT: <comentario detallado en español, ejercicio por ejercicio con puntos obtenidos, errores concretos y sugerencias de mejora. No incluyas una nota final ni un total sumado.>"""

    message = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    return _parse_response(message.content[0].text)


def _parse_response(text):
    scores_match = re.search(r"SCORES:\s*(.+)", text)
    comment_match = re.search(r"COMMENT:\s*(.+)", text, re.DOTALL)

    if scores_match:
        scores = [
            float(s.strip().replace(",", "."))
            for s in scores_match.group(1).split(";")
            if s.strip()
        ]
        grade = round(sum(scores), 2)
    else:
        grade = 0.0
    grade = max(0.0, min(10.0, grade))

    comment = comment_match.group(1).strip() if comment_match else text.strip()
    comment = re.sub(r"\n*\**\s*Nota final[^\n]*\**\s*$", "", comment, flags=re.IGNORECASE).strip()
    comment = f"{comment}\n\n**Nota final: {grade:.2f}/10**"

    return {"grade": grade, "comment": comment}
