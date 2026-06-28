import argparse
import csv
import sys
from pathlib import Path

from tqdm import tqdm

from executor import execute_notebook
from evaluator import evaluate_notebook


def parse_args():
    parser = argparse.ArgumentParser(description="Automatically grade Jupyter notebooks.")
    parser.add_argument("--notebooks", required=True, help="Folder containing .ipynb files")
    parser.add_argument("--rubric", required=True, help="Path to rubric.txt")
    parser.add_argument("--output", default="grades.csv", help="Output CSV file (default: grades.csv)")
    return parser.parse_args()


def main():
    args = parse_args()

    notebooks_dir = Path(args.notebooks)
    if not notebooks_dir.is_dir():
        print(f"Error: '{args.notebooks}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    rubric_path = Path(args.rubric)
    if not rubric_path.is_file():
        print(f"Error: rubric file '{args.rubric}' not found.", file=sys.stderr)
        sys.exit(1)

    rubric = rubric_path.read_text().strip()
    notebooks = sorted(notebooks_dir.glob("*.ipynb"))

    if not notebooks:
        print(f"No .ipynb files found in '{args.notebooks}'.")
        sys.exit(0)

    results = []
    errors = 0

    with open(args.output, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["filename", "grade", "comment"])
        writer.writeheader()

        for notebook_path in tqdm(notebooks, desc="Grading", unit="notebook"):
            filename = notebook_path.name
            try:
                execution = execute_notebook(str(notebook_path))
                evaluation = evaluate_notebook(
                    notebook_content=execution["content"],
                    rubric=rubric,
                    error_type=execution["error_type"],
                )
                row = {
                    "filename": filename,
                    "grade": evaluation["grade"],
                    "comment": evaluation["comment"],
                }
            except Exception as e:
                errors += 1
                row = {
                    "filename": filename,
                    "grade": 0,
                    "comment": f"Grading failed: {type(e).__name__}: {e}",
                }

            writer.writerow(row)
            results.append(row)

    _print_summary(results, errors, args.output)


def _print_summary(results, errors, output_path):
    total = len(results)
    graded = [r for r in results if isinstance(r["grade"], int)]
    avg = sum(r["grade"] for r in graded) / len(graded) if graded else 0
    passed = sum(1 for r in graded if r["grade"] >= 6)

    print(f"\n--- Grading Summary ---")
    print(f"Notebooks graded : {total}")
    print(f"Average grade    : {avg:.1f} / 10")
    print(f"Passed (>=6)     : {passed} / {total}")
    print(f"Errors           : {errors}")
    print(f"Results saved to : {output_path}")


if __name__ == "__main__":
    main()
