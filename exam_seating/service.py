from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .allocator import allocate_students_to_rooms, split_eligibility
from .exporters import (
    collect_generated_files,
    export_attendance_text,
    export_excel,
    export_not_eligible_text,
    export_pdf,
    export_roomwise_text,
    export_summary_text,
)
from .io_utils import DataValidationError, load_rooms, load_students
from .models import SeatingSummary


@dataclass(frozen=True)
class SeatingConfig:
    students_file: str
    rooms_file: str
    attendance_cutoff: float = 40.0
    output_dir: str = "output"
    shuffle_students: bool = False
    random_seed: int | None = None
    alternate_seats: bool = False
    export_pdf_file: bool = False


@dataclass(frozen=True)
class SeatingRunResult:
    summary: SeatingSummary
    generated_files: list[str]
    pdf_generated: bool


def run_seating_system(config: SeatingConfig) -> SeatingRunResult:
    if config.attendance_cutoff < 0 or config.attendance_cutoff > 100:
        raise DataValidationError("Attendance cutoff must be between 0 and 100.")

    students = load_students(config.students_file)
    rooms = load_rooms(config.rooms_file)

    eligible, not_eligible = split_eligibility(students, config.attendance_cutoff)

    room_allocations, unallocated, allocation_order, effective_capacity = allocate_students_to_rooms(
        eligible_students=eligible,
        rooms=rooms,
        alternate_seats=config.alternate_seats,
        shuffle=config.shuffle_students,
        random_seed=config.random_seed,
    )

    summary = SeatingSummary(
        total_students=len(students),
        eligible_students=len(eligible),
        not_eligible_students=len(not_eligible),
        allocated_students=len(allocation_order) - len(unallocated),
        unallocated_students=len(unallocated),
        room_count=len(rooms),
        total_capacity=int(rooms["Capacity"].sum()),
        effective_capacity=effective_capacity,
    )

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    roomwise_text = export_roomwise_text(room_allocations, output_dir)
    not_eligible_text = export_not_eligible_text(not_eligible, output_dir)
    attendance_text = export_attendance_text(room_allocations, output_dir)
    summary_text = export_summary_text(summary, output_dir)
    excel_file = export_excel(room_allocations, not_eligible, summary, output_dir)

    pdf_file = None
    if config.export_pdf_file:
        pdf_file = export_pdf(room_allocations, output_dir)

    generated = collect_generated_files(
        [roomwise_text, not_eligible_text, attendance_text, summary_text, excel_file, pdf_file]
    )

    return SeatingRunResult(
        summary=summary,
        generated_files=generated,
        pdf_generated=pdf_file is not None,
    )
