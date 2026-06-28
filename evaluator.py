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

    prompt = f"""You are a programming instructor grading a student's Jupyter notebook submission.

## Grading Rubric
{rubric}

## Student Notebook
{notebook_content}
{error_note}

Grade this submission on a scale of 0–10 based on the rubric. Be fair, encouraging, and specific.

Respond in exactly this format (no extra text):
GRADE: <integer 0-10>
COMMENT: <2-4 sentences addressed directly to the student, friendly and constructive>"""

    message = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
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
