import json
import logging
import re
from abc import ABC, abstractmethod

import anthropic

logger = logging.getLogger(__name__)

REQUIRED_EXERCISE_FIELDS = {"id", "score", "max_score", "feedback"}
ALLOWED_EXERCISE_FIELDS = REQUIRED_EXERCISE_FIELDS | {"title", "issues"}

_RUBRIC_HEADING_RE = re.compile(
    r"^#{1,4}\s*Ejercicio\s+(\d+).*?\(\s*(\d+(?:[.,]\d+)?)\s*points?\s*\)",
    re.IGNORECASE | re.MULTILINE,
)
_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class LLMResponseError(Exception):
    """Raised when the LLM response is missing, malformed, or fails schema validation."""


class LLMEvaluator(ABC):
    @abstractmethod
    def get_response(self, prompt: str) -> str:
        """Send prompt to the LLM and return its raw text response."""


class AnthropicEvaluator(LLMEvaluator):
    def __init__(self, model="claude-sonnet-4-6", max_tokens=4096):
        self._client = None
        self._model = model
        self._max_tokens = max_tokens

    def _get_client(self):
        if self._client is None:
            self._client = anthropic.Anthropic()
        return self._client

    def get_response(self, prompt: str) -> str:
        message = self._get_client().messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text


_default_evaluator = None


def _get_default_evaluator():
    global _default_evaluator
    if _default_evaluator is None:
        _default_evaluator = AnthropicEvaluator()
    return _default_evaluator


def evaluate_notebook(notebook_content, rubric, error_type=None, evaluator: LLMEvaluator = None):
    evaluator = evaluator or _get_default_evaluator()

    expected_exercises = _parse_rubric_exercises(rubric)
    prompt = _build_prompt(notebook_content, rubric, _build_error_note(error_type))

    raw_response = evaluator.get_response(prompt)
    data = _parse_json_response(raw_response)
    exercises = _validate_response(data, expected_exercises)

    return _score_and_format(exercises)


def _build_error_note(error_type):
    if error_type == "timeout":
        return "\nNote: This notebook timed out during execution — some cells did not finish."
    if error_type == "import_error":
        return "\nNote: This notebook raised an ImportError or ModuleNotFoundError — a required package was missing."
    if error_type and error_type.startswith("execution_error"):
        return f"\nNote: Execution failed with {error_type}."
    return ""


def _build_prompt(notebook_content, rubric, error_note):
    return f"""Eres un profesor de programación corrigiendo la entrega de un estudiante en un Jupyter notebook.

## Rúbrica de evaluación
{rubric}

## Notebook del estudiante
{notebook_content}
{error_note}

Corrige cada ejercicio individualmente asignándole los puntos que indica la rúbrica.

Para cada ejercicio, sigue estas pautas:
- Si la solución es correcta: una frase breve confirmándolo, sin más detalle.
- Si tiene errores: explica con precisión qué está mal (error de sintaxis, lógica incorrecta,
  variable mal nombrada, método incorrecto, resultado erróneo, etc.) y cómo corregirlo. Aquí sí sé exhaustivo.

No calcules ni menciones la nota final del notebook en ningún sitio: el sistema la calculará
automáticamente sumando los puntos que indiques por ejercicio.

Dirígete al estudiante directamente en español, con un tono cercano y motivador.

Responde EXCLUSIVAMENTE con un objeto JSON (sin texto adicional, sin bloques de código markdown,
sin explicaciones fuera del JSON) con esta forma exacta:

{{
  "exercises": [
    {{
      "id": "ejercicio_1",
      "title": "<título breve del ejercicio>",
      "score": <puntos obtenidos, número>,
      "max_score": <puntos máximos de este ejercicio según la rúbrica, número>,
      "feedback": "<comentario en español para este ejercicio>",
      "issues": ["<problema concreto detectado>", "..."]
    }}
  ]
}}

Reglas:
- Incluye un objeto por cada ejercicio de la rúbrica, en el mismo orden, con id "ejercicio_1",
  "ejercicio_2", etc.
- "max_score" debe coincidir exactamente con los puntos indicados en la rúbrica para ese ejercicio.
- "score" nunca puede ser negativo ni superar "max_score".
- "issues" es una lista (puede ir vacía: []) con problemas concretos detectados; no repitas el
  contenido de "feedback" ahí."""


def _parse_rubric_exercises(rubric_text):
    """Best-effort extraction of {exercise_id: max_score} from '### Ejercicio N ... (X points)'
    headings. Returns None if the rubric doesn't follow that convention, in which case the LLM's
    self-reported max_score is trusted instead (loose validation)."""
    exercises = {}
    for match in _RUBRIC_HEADING_RE.finditer(rubric_text):
        number, max_score = match.groups()
        exercises[f"ejercicio_{number}"] = float(max_score.replace(",", "."))
    return exercises or None


def _parse_json_response(text):
    cleaned = _JSON_FENCE_RE.sub("", text).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise LLMResponseError(f"LLM response is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise LLMResponseError("LLM response JSON must be an object")
    return data


def _validate_response(data, expected_exercises):
    exercises = data.get("exercises")
    if not isinstance(exercises, list) or not exercises:
        raise LLMResponseError("LLM response is missing a non-empty 'exercises' list")

    if expected_exercises is not None and len(exercises) != len(expected_exercises):
        raise LLMResponseError(
            f"Expected {len(expected_exercises)} exercises per rubric, got {len(exercises)}"
        )

    validated = []
    seen_ids = set()
    for i, ex in enumerate(exercises):
        if not isinstance(ex, dict):
            raise LLMResponseError(f"Exercise at index {i} is not a JSON object")

        missing = REQUIRED_EXERCISE_FIELDS - ex.keys()
        if missing:
            raise LLMResponseError(f"Exercise at index {i} is missing fields: {sorted(missing)}")

        unexpected = ex.keys() - ALLOWED_EXERCISE_FIELDS
        if unexpected:
            raise LLMResponseError(f"Exercise at index {i} has unexpected fields: {sorted(unexpected)}")

        exercise_id = ex["id"]
        if not isinstance(exercise_id, str) or not exercise_id.strip():
            raise LLMResponseError(f"Exercise at index {i} has an invalid id")
        if exercise_id in seen_ids:
            raise LLMResponseError(f"Duplicate exercise id: '{exercise_id}'")
        seen_ids.add(exercise_id)

        if expected_exercises is not None and exercise_id not in expected_exercises:
            raise LLMResponseError(f"Exercise id '{exercise_id}' does not match any exercise in the rubric")

        score, max_score = ex["score"], ex["max_score"]
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise LLMResponseError(f"Exercise '{exercise_id}' has a non-numeric score")
        if isinstance(max_score, bool) or not isinstance(max_score, (int, float)):
            raise LLMResponseError(f"Exercise '{exercise_id}' has a non-numeric max_score")

        if expected_exercises is not None:
            rubric_max = expected_exercises[exercise_id]
            if abs(rubric_max - max_score) > 0.01:
                logger.warning(
                    "Exercise '%s': LLM-reported max_score %.2f differs from rubric max_score %.2f; using rubric value",
                    exercise_id, max_score, rubric_max,
                )
            max_score = rubric_max

        if max_score <= 0:
            raise LLMResponseError(f"Exercise '{exercise_id}' has a non-positive max_score")
        if score < -0.01 or score > max_score + 0.01:
            raise LLMResponseError(
                f"Exercise '{exercise_id}' score {score} is outside allowed range [0, {max_score}]"
            )
        score = max(0.0, min(score, max_score))

        feedback = ex["feedback"]
        if not isinstance(feedback, str) or not feedback.strip():
            raise LLMResponseError(f"Exercise '{exercise_id}' has invalid feedback")

        issues = ex.get("issues", [])
        if not isinstance(issues, list) or not all(isinstance(issue, str) for issue in issues):
            raise LLMResponseError(f"Exercise '{exercise_id}' has an invalid 'issues' field")

        validated.append(
            {
                "id": exercise_id,
                "title": ex.get("title"),
                "score": float(score),
                "max_score": float(max_score),
                "feedback": feedback.strip(),
                "issues": issues,
            }
        )

    return validated


def _score_and_format(exercises):
    total = round(sum(ex["score"] for ex in exercises), 2)
    total = max(0.0, min(10.0, total))

    parts = []
    for ex in exercises:
        header = ex["title"] or ex["id"].replace("_", " ").capitalize()
        block = f"**{header} — {ex['score']:.2f}/{ex['max_score']:.2f} pts**\n\n{ex['feedback']}"
        if ex["issues"]:
            bullets = "\n".join(f"- {issue}" for issue in ex["issues"])
            block += f"\n\n{bullets}"
        parts.append(block)

    comment = "\n\n---\n\n".join(parts)
    comment = f"{comment}\n\n**Nota final: {total:.2f}/10**"

    return {"grade": total, "comment": comment, "exercises": exercises}
