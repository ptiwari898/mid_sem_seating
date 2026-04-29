from __future__ import annotations

import argparse

from exam_seating.io_utils import DataValidationError
from exam_seating.service import SeatingConfig, run_seating_system


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Automatic exam seating arrangement system"
    )
    parser.add_argument("--students", required=True, help="Path to student CSV/Excel file")
    parser.add_argument("--rooms", required=True, help="Path to room CSV/Excel file")
    parser.add_argument(
        "--attendance-cutoff",
        type=float,
        default=40.0,
        help="Minimum attendance percentage for eligibility",
    )
    parser.add_argument(
        "--output-dir", default="output", help="Folder to save generated reports"
    )
    parser.add_argument(
        "--shuffle",
        action="store_true",
        help="Shuffle eligible students before allocation",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed used when --shuffle is enabled",
    )
    parser.add_argument(
        "--alternate-seats",
        action="store_true",
        help="Allocate students on alternate seats only",
    )
    parser.add_argument(
        "--export-pdf",
        action="store_true",
        help="Export room-wise seating plan to PDF (requires reportlab)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = SeatingConfig(
        students_file=args.students,
        rooms_file=args.rooms,
        attendance_cutoff=args.attendance_cutoff,
        output_dir=args.output_dir,
        shuffle_students=args.shuffle,
        random_seed=args.seed,
        alternate_seats=args.alternate_seats,
        export_pdf_file=args.export_pdf,
    )

    try:
        result = run_seating_system(config)
    except (FileNotFoundError, DataValidationError) as exc:
        print(f"Error: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"Unexpected error: {exc}")
        return 1

    print("Exam seating arrangement generated successfully.")
    print("Summary:")
    print(f"  Total students      : {result.summary.total_students}")
    print(f"  Eligible students   : {result.summary.eligible_students}")
    print(f"  Not eligible        : {result.summary.not_eligible_students}")
    print(f"  Allocated students  : {result.summary.allocated_students}")
    print(f"  Unallocated students: {result.summary.unallocated_students}")
    print(f"  Total capacity      : {result.summary.total_capacity}")
    print(f"  Effective capacity  : {result.summary.effective_capacity}")
    print("Generated files:")
    for path in result.generated_files:
        print(f"  - {path}")

    if config.export_pdf_file and not result.pdf_generated:
        print("PDF export was requested, but reportlab is not installed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
