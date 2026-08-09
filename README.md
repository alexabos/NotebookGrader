# NotebookGrader

A CLI tool that automatically grades Jupyter notebook submissions against an
instructor-written rubric — executing each notebook, using an LLM only for
semantic judgment, and computing the final grade in Python from a validated,
structured assessment.

## Problem

Manually grading Python/Jupyter assignments at class scale is:

- **Time-consuming** — running each notebook, reading the code, and writing
  individualized feedback per exercise takes real time per student.
- **Difficult to standardize** — the same mistake can get graded differently
  depending on when in the pile it was reached.
- **Difficult to reproduce** — there's no record of *why* a grade was what it
  was beyond whatever got written in the margin.

## Solution

NotebookGrader automates notebook execution and rubric-based assessment,
using an LLM only for the part that genuinely requires judgment — reading a
student's code and deciding whether it satisfies an exercise — while keeping
the grade itself a deterministic, auditable calculation performed in Python.

## Architecture

```
                    ┌────────────────┐
                    │    Notebook    │
                    └───────┬────────┘
                            ↓
                    ┌────────────────┐
                    │    Executor    │   nbclient runs every cell,
                    │  (executor.py) │   captures outputs and errors
                    └───────┬────────┘
                            ↓
                 ┌────────────────────────┐
                 │  Deterministic checks  │   timeout / missing-import
                 │   (execution status)   │   detection
                 └────────────┬───────────┘
                              ↓
                    ┌────────────────┐
                    │  LLM Evaluator │   Claude grades each exercise
                    │ (evaluator.py) │   against the rubric, in Spanish
                    └───────┬────────┘
                            ↓
                  Structured JSON assessment
                 (per-exercise score + feedback)
                            ↓
                     Schema validation
              (types, score ranges, ids, required
                 fields — rejects malformed output)
                            ↓
                     Python scoring
             (sum validated per-exercise scores,
           clamp to [0,10], rubric max_score wins)
                            ↓
                    ┌────────────────┐
                    │   grades.csv   │
                    │  (grader.py)   │
                    └────────────────┘
```

Each notebook flows through this pipeline independently; a failure at any
stage is caught, logged, and recorded for that submission without stopping
the batch.

## Key Design Principles

- **Deterministic execution** — every notebook actually runs; grading is
  based on real outputs, not a static read of the code.
- **Rubric-based assessment** — the instructor's `rubric.txt` is the source
  of truth for what each exercise is worth.
- **LLM-assisted semantic evaluation** — the LLM is used for what it's good
  at (reading code, judging correctness, writing feedback), not arithmetic.
- **Structured, validated outputs** — the LLM must respond in a strict JSON
  schema; malformed or out-of-range responses are rejected, not silently
  accepted.
- **Python-computed final grade** — the score a student receives is always
  computed and clamped by Python from validated per-exercise data, never
  trusted verbatim from the LLM.
- **Fault-tolerant batch processing** — one corrupted notebook, timeout, or
  malformed LLM response never stops the rest of the batch.
- **Reproducible environment** — dependencies are pinned via `uv.lock`.

## How It Works

1. **Execute** — `executor.py` runs the notebook with `nbclient`
   (`allow_errors=True`, so one broken cell doesn't stop the rest) and
   flattens code, outputs, and markdown into plain text.
2. **Detect systemic failures** — timeouts and missing-import errors are
   flagged deterministically, without needing the LLM to guess why a
   notebook didn't run.
3. **Evaluate semantically** — `evaluator.py` sends the rubric and the
   flattened notebook to Claude, asking for a structured JSON assessment:
   one object per exercise with `id`, `score`, `max_score`, `feedback`, and
   `issues`.
4. **Validate** — the response is checked for valid JSON, required fields,
   unexpected fields, numeric types, exercise-id/count match against the
   rubric, and in-range scores. Where `rubric.txt` follows the
   `### Ejercicio N ... (X points)` heading convention, the rubric's own
   point values override whatever `max_score` the LLM reported, so grading
   weights are never solely LLM-controlled.
5. **Score** — Python sums the validated per-exercise scores and clamps the
   total to `[0, 10]`. This number is never taken directly from the LLM.
6. **Report** — `grader.py` writes one row per notebook to `grades.csv`
   (`filename, grade, comment`) and prints a batch summary.

## Example

Given a rubric exercise:

```
### Ejercicio 1 — Variables (1 point)
- a) Numeric variable `a = 2` (0.5 pts)
- b) List of 3 fruits (0.5 pts)
```

and a student cell:

```python
a = 2
frutas = ["manzana", "pera"]
print(a, frutas)
```

the LLM's structured response for that exercise looks like:

```json
{
  "id": "ejercicio_1",
  "title": "Variables",
  "score": 0.5,
  "max_score": 1.0,
  "feedback": "La variable numérica está bien definida. La lista de frutas debía tener 3 elementos y solo tiene 2.",
  "issues": ["La lista `frutas` tiene 2 elementos en vez de 3"]
}
```

which Python turns into the corresponding `grades.csv` row:

```
filename,grade,comment
ejemplo.ipynb,0.5,"**Variables — 0.50/1.00 pts**

La variable numérica está bien definida. La lista de frutas debía tener 3 elementos y solo tiene 2.

- La lista `frutas` tiene 2 elementos en vez de 3

**Nota final: 0.50/10**"
```

(A real rubric has several exercises; the final grade is the sum of all of
their validated scores.)

## Design Decisions

**Deterministic checks happen before the LLM is asked anything.** Timeouts
and missing imports are unambiguous, cheap to detect, and don't benefit from
a judgment call — checking for them first avoids spending an LLM call
diagnosing something Python already knows for certain.

**The LLM is used only for semantic evaluation.** Deciding whether a
particular approach satisfies an exercise, giving partial credit, and
writing specific feedback all require reading and understanding code the way
a human grader would — that's a judgment call, not a fixed rule, which is
exactly what an LLM is suited for and a hand-written checker isn't.

**The final score is always calculated in Python, not trusted from the
LLM.** LLMs are not reliable arithmetic engines, and a grade is a number a
student's outcome depends on — it needs to be reproducible and auditable
independent of any single model response. The LLM proposes a score and
justification per exercise; Python validates, applies the rubric's real
point values, and computes the total.

**Batch failures are isolated per notebook.** Grading runs unattended over
an entire class's submissions; one corrupted file, one execution timeout, or
one malformed LLM response must not block grading for the other 29 students.
Every notebook goes through the pipeline independently, and a failure is
recorded against that submission alone.

## Limitations

- **LLM variability** — semantic grading can vary slightly between runs or
  across model versions; it is not bit-for-bit reproducible the way a unit
  test is.
- **Rubric ambiguity** — `rubric.txt` is free text sent verbatim to the LLM.
  Underspecified exercises rely on the LLM's interpretation, even with
  explicit "don't penalize X" notes in the rubric.
- **Best-effort rubric weight cross-checking** — Python only overrides the
  LLM's self-reported `max_score` when `rubric.txt` follows the
  `### Ejercicio N ... (X points)` heading convention. A differently
  formatted rubric falls back to trusting the LLM's reported `max_score`.
- **No formal human-vs-automated agreement measurement yet** — see
  Evaluation below.
- **Cases that likely need human review**: borderline pass/fail grades,
  unconventional-but-correct solutions, and exercises the rubric itself
  flags as ambiguous.

## Evaluation

A formal comparison between automated and human-assigned grades is planned
as a **future milestone (v1.1)**, once a representative, anonymized dataset
of student submissions with human-assigned grades has been collected. At
that point the plan is to build a held-out evaluation dataset, compute mean
absolute error and agreement/correlation between human and automated grades,
analyze systematic failure modes, and publish the results here.

This version intentionally contains no evaluation metrics — none have been
measured yet, and none are fabricated.

## Reproducibility

### Setup

```bash
uv sync
.venv/bin/python -m ipykernel install --user --name python3
cp .env.example .env   # then edit .env and set your ANTHROPIC_API_KEY
```

Dependencies are pinned in `uv.lock`; `uv sync` reproduces the exact
environment on any machine. `.env` is gitignored and loaded automatically
via `python-dotenv`.

### Folder structure

Organise work by course and assignment:

```
courses/
└── intro_python/
│   ├── unidad2/
│   │   ├── rubric.txt       ← grading criteria
│   │   ├── submissions/     ← student .ipynb files go here
│   │   └── grades.csv       ← output (auto-generated)
│   └── unidad3/
│       ├── rubric.txt
│       └── submissions/
└── exploratory_analysis/
    └── unidad1/
        ├── rubric.txt
        └── submissions/
```

### Usage

**Grade a full assignment** (recommended):
```bash
uv run grader.py --assignment ./courses/intro_python/unidad2
```
Automatically reads `rubric.txt` and `submissions/` from the folder, and
writes `grades.csv` there.

**Grade a single notebook:**
```bash
uv run grader.py --file ./courses/intro_python/unidad2/submissions/student.ipynb --rubric ./courses/intro_python/unidad2/rubric.txt
```

**Grade a folder manually:**
```bash
uv run grader.py --notebooks ./submissions --rubric ./rubric.txt --output grades.csv
```

Output:
```
Grading: 100%|██████████| 30/30 [02:14<00:00,  4.5s/notebook]

--- Grading Summary ---
Notebooks graded : 30
Average grade    : 7.43 / 10
Passed (>=6)     : 24 / 30
Errors           : 1
Results saved to : courses/intro_python/unidad2/grades.csv
```

`grades.csv` columns: `filename`, `grade`, `comment`.

### Error handling

| Situation | Behaviour |
|---|---|
| Cell times out | Flagged as `timeout`; notebook still graded on its written code |
| Missing import | Flagged as `import_error`; noted for the LLM, not auto-failed |
| Notebook fails to execute / is corrupted | Error caught, logged, and recorded in the CSV; pipeline continues |
| Malformed or invalid LLM response | Rejected by schema validation (`LLMResponseError`), logged, and recorded in the CSV; pipeline continues |

### Testing

```bash
uv run pytest
```

Tests cover the critical paths and failure modes of each module — notebook
execution (valid notebooks, runtime errors, timeouts, missing imports),
LLM response validation (malformed/incomplete/out-of-range responses), and
end-to-end batch grading (including that one failing notebook doesn't stop
the rest). They don't call the real Anthropic API — `evaluate_notebook`
accepts an injectable `LLMEvaluator`, and tests use a fake one.

### Customising the rubric

Edit `rubric.txt` with your assignment criteria. The rubric is sent verbatim
to Claude. Use the `### Ejercicio N — Title (X points)` heading format so
NotebookGrader can also verify the LLM's response against your point values
directly. Point values should sum to 10.

## Project structure

```
grader.py       # CLI entry point, batch orchestration, CSV output
executor.py     # Notebook execution via nbclient
evaluator.py    # LLM prompt, structured response validation, Python scoring
tests/          # pytest suite for executor, evaluator, grader, edge cases
courses/        # One folder per course, one subfolder per assignment
```

## Future Improvements

- Retry logic for transient LLM API errors.
- CLI flags for model name and execution timeout (currently constants).
- A richer batch summary that breaks down failures by stage (execution vs.
  LLM validation) instead of one aggregate error count.
- The human-vs-automated evaluation milestone described above.
