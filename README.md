# NotebookGrader

A CLI tool that automatically grades Jupyter notebook submissions using Claude AI.

## How it works

1. Executes each `.ipynb` notebook using `nbclient`, capturing cell outputs and errors
2. Sends the code and outputs to Claude along with your rubric
3. Writes a `grades.csv` with a 0–10 score and a personalized comment per student

## Setup

```bash
uv venv .venv --python 3.11
uv pip install nbclient nbformat anthropic tqdm ipykernel --python .venv/bin/python3.11
.venv/bin/python3.11 -m ipykernel install --user --name python3
export ANTHROPIC_API_KEY=your-key-here
```

## Usage

```bash
.venv/bin/python3.11 grader.py --notebooks ./submissions --rubric ./rubric.txt --output grades.csv
```

Place student notebooks in `./submissions/` and provide a plain-text rubric in `rubric.txt`.

### Output

```
Grading: 100%|██████████| 30/30 [02:14<00:00,  4.5s/notebook]

--- Grading Summary ---
Notebooks graded : 30
Average grade    : 7.4 / 10
Passed (>=6)     : 24 / 30
Errors           : 1
Results saved to : grades.csv
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
grader.py          # CLI entry point
executor.py        # Notebook execution via nbclient
evaluator.py       # Claude API call and response parsing
rubric.txt         # Example rubric (edit for your assignment)
sample_submission.ipynb  # Sample notebook for testing
```

## Customising the rubric

Edit `rubric.txt` with your assignment criteria. The rubric is sent verbatim to Claude, so plain English works well. See the included example for a lists/loops/functions Python assignment.
