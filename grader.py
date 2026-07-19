import argparse
import csv
import sys
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

from executor import execute_notebook
from evaluator import evaluate_notebook

load_dotenv()


def parse_args():
    parser = argparse.ArgumentParser(description="Automatically grade Jupyter notebooks.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--assignment", help="Assignment folder containing rubric.txt and submissions/")
    source.add_argument("--notebooks", help="Folder containing .ipynb files")
    source.add_argument("--file", help="Single .ipynb file to grade")
    parser.add_argument("--rubric", help="Path to rubric.txt (required with --notebooks or --file)")
    parser.add_argument("--output", help="Output CSV file (default: grades.csv or <assignment>/grades.csv)")
    return parser.parse_args()


def resolve_paths(args):
    if args.assignment:
        assignment = Path(args.assignment)
        if not assignment.is_dir():
            print(f"Error: assignment folder '{args.assignment}' not found.", file=sys.stderr)
            sys.exit(1)
        rubric_path = assignment / "rubric.txt"
        notebooks_dir = assignment / "submissions"
        output = Path(args.output) if args.output else assignment / "grades.csv"
        notebooks = None
    elif args.file:
        rubric_path = Path(args.rubric) if args.rubric else None
        notebooks_dir = None
        notebooks = [Path(args.file)]
        output = Path(args.output) if args.output else Path("grades.csv")
    else:
        rubric_path = Path(args.rubric) if args.rubric else None
        notebooks_dir = Path(args.notebooks)
        notebooks = None
        output = Path(args.output) if args.output else Path("grades.csv")

    if rubric_path is None:
        print("Error: --rubric is required when using --notebooks or --file.", file=sys.stderr)
        sys.exit(1)
    if not rubric_path.is_file():
        print(f"Error: rubric file '{rubric_path}' not found.", file=sys.stderr)
        sys.exit(1)

    if notebooks is None:
        if not notebooks_dir.is_dir():
            print(f"Error: submissions folder '{notebooks_dir}' not found.", file=sys.stderr)
            sys.exit(1)
        notebooks = sorted(notebooks_dir.glob("*.ipynb"))

    if not notebooks:
        print(f"No .ipynb files found in '{notebooks_dir}'.")
        sys.exit(0)

    return notebooks, rubric_path, output


def main():
    args = parse_args()
    notebooks, rubric_path, output = resolve_paths(args)
    rubric = rubric_path.read_text().strip()

    results = []
    errors = 0

    with open(output, "w", newline="") as csvfile:
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

    _print_summary(results, errors, output)


def _print_summary(results, errors, output_path):
    total = len(results)
    graded = [r for r in results if isinstance(r["grade"], (int, float))]
    avg = sum(r["grade"] for r in graded) / len(graded) if graded else 0
    passed = sum(1 for r in graded if r["grade"] >= 6)

    print(f"\n--- Grading Summary ---")
    print(f"Notebooks graded : {total}")
    print(f"Average grade    : {avg:.2f} / 10")
    print(f"Passed (>=6)     : {passed} / {total}")
    print(f"Errors           : {errors}")
    print(f"Results saved to : {output_path}")


if __name__ == "__main__":
    main()
