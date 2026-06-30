# NotebookGrader

A CLI tool that automatically grades Jupyter notebook submissions using Claude AI.

## How it works

1. Executes each `.ipynb` notebook using `nbclient`, capturing cell outputs and errors
2. Sends the code and outputs to Claude along with your rubric
3. Writes a `grades.csv` with scores and per-exercise comments in Spanish

## Setup

```bash
uv venv .venv --python 3.11
uv pip install nbclient nbformat anthropic tqdm ipykernel --python .venv/bin/python3.11
.venv/bin/python3.11 -m ipykernel install --user --name python3
export ANTHROPIC_API_KEY=your-key-here
```

## Folder structure

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

## Usage

**Grade a full assignment** (recommended):
```bash
.venv/bin/python3.11 grader.py --assignment ./courses/intro_python/unidad2
```
Automatically reads `rubric.txt` and `submissions/` from the folder, and writes `grades.csv` there.

**Grade a single notebook:**
```bash
.venv/bin/python3.11 grader.py --file ./courses/intro_python/unidad2/submissions/student.ipynb --rubric ./courses/intro_python/unidad2/rubric.txt
```

**Grade a folder manually:**
```bash
.venv/bin/python3.11 grader.py --notebooks ./submissions --rubric ./rubric.txt --output grades.csv
```

### Output

```
Grading: 100%|██████████| 30/30 [02:14<00:00,  4.5s/notebook]

--- Grading Summary ---
Notebooks graded : 30
Average grade    : 7.43 / 10
Passed (>=6)     : 24 / 30
Errors           : 1
Results saved to : courses/intro_python/unidad2/grades.csv
```

`grades.csv` columns: `filename`, `grade`, `comment`

## Error handling

| Situation | Behaviour |
|---|---|
| Cell times out (>30s) | Noted in prompt; notebook still graded |
| Missing import | Flagged as `import_error`; grade deducted per rubric |
| Notebook fails to execute | Error recorded in CSV; pipeline continues |

## Project structure

```
grader.py      # CLI entry point
executor.py    # Notebook execution via nbclient
evaluator.py   # Claude API call and response parsing
courses/       # One folder per course, one subfolder per assignment
```

## Customising the rubric

Edit `rubric.txt` with your assignment criteria. The rubric is sent verbatim to Claude.
Include point values per exercise so the final grade is computed as their sum (max 10).
