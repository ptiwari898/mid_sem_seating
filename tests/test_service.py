from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from exam_seating.allocator import allocate_students_to_rooms
from exam_seating.service import SeatingConfig, run_seating_system


@pytest.fixture
def sample_students_rooms() -> tuple[pd.DataFrame, pd.DataFrame]:
    students = pd.DataFrame(
        [
            {
                "Roll Number": f"0133CI231{i:03d}",
                "Name": f"Student {i}",
                "Attendance Percentage": 75.0,
            }
            for i in range(1, 31)
        ]
    )
    rooms = pd.DataFrame(
        [
            {"Room Number": "F-307", "Capacity": 15},
            {"Room Number": "F-308", "Capacity": 15},
        ]
    )
    return students, rooms


def _write_inputs(tmp_path: Path, students: pd.DataFrame, rooms: pd.DataFrame) -> tuple[Path, Path, Path]:
    students_path = tmp_path / "students.csv"
    rooms_path = tmp_path / "rooms.csv"
    output_dir = tmp_path / "out"

    students.to_csv(students_path, index=False)
    rooms.to_csv(rooms_path, index=False)

    return students_path, rooms_path, output_dir


def test_all_students_eligible(sample_students_rooms, tmp_path: Path) -> None:
    students, rooms = sample_students_rooms
    students_path, rooms_path, output_dir = _write_inputs(tmp_path, students, rooms)

    result = run_seating_system(
        SeatingConfig(
            students_file=str(students_path),
            rooms_file=str(rooms_path),
            attendance_cutoff=40.0,
            output_dir=str(output_dir),
        )
    )

    assert result.summary.total_students == 30
    assert result.summary.eligible_students == 30
    assert result.summary.not_eligible_students == 0
    assert result.summary.allocated_students == 30
    assert result.summary.unallocated_students == 0


def test_none_students_eligible(sample_students_rooms, tmp_path: Path) -> None:
    students, rooms = sample_students_rooms
    students["Attendance Percentage"] = 10.0
    students_path, rooms_path, output_dir = _write_inputs(tmp_path, students, rooms)

    result = run_seating_system(
        SeatingConfig(
            students_file=str(students_path),
            rooms_file=str(rooms_path),
            attendance_cutoff=40.0,
            output_dir=str(output_dir),
        )
    )

    assert result.summary.total_students == 30
    assert result.summary.eligible_students == 0
    assert result.summary.not_eligible_students == 30
    assert result.summary.allocated_students == 0
    assert result.summary.unallocated_students == 0


def test_more_students_than_capacity(sample_students_rooms, tmp_path: Path) -> None:
    students, _ = sample_students_rooms
    rooms = pd.DataFrame([
        {"Room Number": "F-307", "Capacity": 10},
        {"Room Number": "F-308", "Capacity": 10},
    ])
    students_path, rooms_path, output_dir = _write_inputs(tmp_path, students, rooms)

    result = run_seating_system(
        SeatingConfig(
            students_file=str(students_path),
            rooms_file=str(rooms_path),
            attendance_cutoff=40.0,
            output_dir=str(output_dir),
        )
    )

    assert result.summary.eligible_students == 30
    assert result.summary.allocated_students == 20
    assert result.summary.unallocated_students == 10


def test_alternate_seats_mode(sample_students_rooms, tmp_path: Path) -> None:
    students, _ = sample_students_rooms
    rooms = pd.DataFrame([
        {"Room Number": "F-307", "Capacity": 10},
        {"Room Number": "F-308", "Capacity": 10},
    ])
    students_path, rooms_path, output_dir = _write_inputs(tmp_path, students, rooms)

    result = run_seating_system(
        SeatingConfig(
            students_file=str(students_path),
            rooms_file=str(rooms_path),
            attendance_cutoff=40.0,
            output_dir=str(output_dir),
            alternate_seats=True,
        )
    )

    assert result.summary.total_capacity == 20
    assert result.summary.effective_capacity == 10
    assert result.summary.allocated_students == 10
    assert result.summary.unallocated_students == 20


def test_shuffle_reproducibility(sample_students_rooms) -> None:
    students, rooms = sample_students_rooms

    alloc_a, _, order_a, _ = allocate_students_to_rooms(
        eligible_students=students,
        rooms=rooms,
        shuffle=True,
        random_seed=123,
    )
    alloc_b, _, order_b, _ = allocate_students_to_rooms(
        eligible_students=students,
        rooms=rooms,
        shuffle=True,
        random_seed=123,
    )
    alloc_c, _, order_c, _ = allocate_students_to_rooms(
        eligible_students=students,
        rooms=rooms,
        shuffle=True,
        random_seed=999,
    )

    assert order_a["Roll Number"].tolist() == order_b["Roll Number"].tolist()
    assert order_a["Roll Number"].tolist() != order_c["Roll Number"].tolist()
    assert set(alloc_a.keys()) == {"F-307", "F-308"}


def test_generates_documented_text_outputs(sample_students_rooms, tmp_path: Path) -> None:
    students, rooms = sample_students_rooms
    students_path, rooms_path, output_dir = _write_inputs(tmp_path, students, rooms)

    result = run_seating_system(
        SeatingConfig(
            students_file=str(students_path),
            rooms_file=str(rooms_path),
            attendance_cutoff=40.0,
            output_dir=str(output_dir),
        )
    )

    expected = {
        "room_wise_seating_plan.txt",
        "not_eligible_students.txt",
        "attendance_sheet.txt",
        "summary.txt",
        "exam_seating_output.xlsx",
    }

    generated_names = {Path(path).name for path in result.generated_files}
    assert expected.issubset(generated_names)

    for name in expected:
        assert (output_dir / name).exists()
