import argparse
import csv
import re
import shutil
import sys
import unicodedata
from pathlib import Path

_SUBMISSION_FOLDER_RE = re.compile(r"^(?P<name>.+)_(?P<moodle_id>\d+)_assignsubmission_(?P<subtype>\w+)$")
_ID_RE = re.compile(r"^S(\d+)$")


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Ingest a Moodle bulk-download of assignment submissions into "
            "courses/<course>/<unit>/submissions/, replacing student names with "
            "stable anonymized IDs tracked in courses/<course>/roster.csv."
        )
    )
    parser.add_argument(
        "--source", required=True, help="Moodle bulk-download folder (one subfolder per student submission)"
    )
    parser.add_argument("--course", required=True, help="Course folder name under courses/, e.g. intro_python")
    parser.add_argument("--unit", required=True, help="Unit folder name under courses/<course>/, e.g. unidad2")
    return parser.parse_args()


def main():
    args = parse_args()
    source_dir = Path(args.source)
    if not source_dir.is_dir():
        print(f"Error: source folder '{args.source}' not found.", file=sys.stderr)
        sys.exit(1)

    result = ingest(source_dir, args.course, args.unit)
    _print_summary(result)


def ingest(source_dir, course, unit, courses_root=Path("courses"), copy_fn=shutil.copy2):
    unit_dir = courses_root / course / unit
    submissions_dir = unit_dir / "submissions"
    roster_path = courses_root / course / "roster.csv"

    warnings = []
    if not (unit_dir / "rubric.txt").is_file():
        warnings.append(f"rubric.txt not found at {unit_dir / 'rubric.txt'} (continuing anyway)")

    roster_rows = load_roster(roster_path)
    name_to_id = {row["name"]: row["student_id"] for row in roster_rows}
    folded_to_name = {}
    for row in roster_rows:
        folded_to_name.setdefault(_normalize_name_key(row["name"]), row["name"])

    processed = []
    skipped = []
    new_entries = []
    duplicate_warnings = []

    submissions_dir.mkdir(parents=True, exist_ok=True)

    for folder, name, moodle_id in _iter_submission_folders(source_dir):
        notebooks = [p for p in sorted(folder.iterdir()) if p.suffix.lower() == ".ipynb"]

        if len(notebooks) == 0:
            skipped.append({"folder": folder.name, "reason": "no .ipynb file found"})
            continue
        if len(notebooks) > 1:
            skipped.append(
                {
                    "folder": folder.name,
                    "reason": f"multiple .ipynb files found: {[p.name for p in notebooks]}",
                }
            )
            continue

        if name in name_to_id:
            student_id = name_to_id[name]
        else:
            folded = _normalize_name_key(name)
            if folded in folded_to_name:
                duplicate_warnings.append({"name": name, "similar_to": folded_to_name[folded]})
            student_id = _next_student_id(name_to_id.values())
            name_to_id[name] = student_id
            folded_to_name.setdefault(folded, name)
            roster_rows.append({"student_id": student_id, "name": name})
            new_entries.append({"student_id": student_id, "name": name})

        dest = submissions_dir / f"{student_id}.ipynb"
        overwritten = dest.exists()
        copy_fn(notebooks[0], dest)

        processed.append(
            {
                "student_id": student_id,
                "name": name,
                "moodle_id": moodle_id,
                "source": str(notebooks[0]),
                "dest": str(dest),
                "overwritten": overwritten,
            }
        )

    save_roster(roster_path, roster_rows)

    return {
        "processed": processed,
        "skipped": skipped,
        "new_roster_entries": new_entries,
        "duplicate_warnings": duplicate_warnings,
        "warnings": warnings,
        "roster_path": str(roster_path),
        "submissions_dir": str(submissions_dir),
    }


def _iter_submission_folders(source_dir):
    for entry in sorted(source_dir.iterdir()):
        if not entry.is_dir():
            continue
        match = _SUBMISSION_FOLDER_RE.match(entry.name)
        if match:
            yield entry, match.group("name").strip(), match.group("moodle_id")


def _normalize_name_key(name):
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return " ".join(folded.lower().split())


def _next_student_id(existing_ids):
    max_n = 0
    for student_id in existing_ids:
        match = _ID_RE.match(student_id)
        if match:
            max_n = max(max_n, int(match.group(1)))
    return f"S{max_n + 1:03d}"


def load_roster(roster_path):
    if not roster_path.is_file():
        return []
    with roster_path.open(newline="") as f:
        return list(csv.DictReader(f))


def save_roster(roster_path, rows):
    roster_path.parent.mkdir(parents=True, exist_ok=True)
    with roster_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["student_id", "name"])
        writer.writeheader()
        for row in sorted(rows, key=lambda r: r["student_id"]):
            writer.writerow(row)


def _print_summary(result):
    print("\n--- Ingest Summary ---")
    print(f"Notebooks copied   : {len(result['processed'])}")
    print(f"New roster entries : {len(result['new_roster_entries'])}")
    print(f"Skipped folders    : {len(result['skipped'])}")
    print(f"Roster file        : {result['roster_path']}")
    print(f"Submissions folder : {result['submissions_dir']}")

    if result["new_roster_entries"]:
        print("\nNew roster entries:")
        for entry in result["new_roster_entries"]:
            print(f"  {entry['student_id']}  <-  {entry['name']}")

    if result["duplicate_warnings"]:
        print("\nPossible duplicate names (review before trusting the roster):")
        for w in result["duplicate_warnings"]:
            print(f"  '{w['name']}' looks similar to existing roster entry '{w['similar_to']}'")

    if result["skipped"]:
        print("\nSkipped (needs manual review):")
        for s in result["skipped"]:
            print(f"  {s['folder']}: {s['reason']}")

    if result["warnings"]:
        print("\nWarnings:")
        for w in result["warnings"]:
            print(f"  {w}")

    overwritten = [p for p in result["processed"] if p["overwritten"]]
    if overwritten:
        print(f"\nOverwrote {len(overwritten)} existing submission file(s) (re-ingest of an already-processed export?):")
        for p in overwritten:
            print(f"  {p['dest']}")


if __name__ == "__main__":
    main()
