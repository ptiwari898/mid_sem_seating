from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from exam_seating.io_utils import DataValidationError, _split_sqlite_spec, load_rooms, load_students


def test_split_sqlite_spec_parses_table_name() -> None:
    db_path, table = _split_sqlite_spec("sample.db::students")
    assert db_path == Path("sample.db")
    assert table == "students"


def test_split_sqlite_spec_without_table() -> None:
    db_path, table = _split_sqlite_spec("sample.db")
    assert db_path == Path("sample.db")
    assert table is None


def test_load_students_sqlite_missing_table_raises(tmp_path: Path) -> None:
    db_file = tmp_path / "input.db"
    with sqlite3.connect(db_file) as conn:
        conn.execute("CREATE TABLE rooms (Room Number TEXT, Capacity INTEGER)")
        conn.commit()

    with pytest.raises(DataValidationError, match="Table 'students' not found"):
        load_students(str(db_file))


def test_non_sqlite_file_with_table_spec_raises(tmp_path: Path) -> None:
    csv_file = tmp_path / "students.csv"
    csv_file.write_text("Roll Number,Name,Attendance Percentage\n1,Alice,75\n", encoding="utf-8")

    with pytest.raises(DataValidationError, match="Table specifier is only supported for SQLite files"):
        load_students(f"{csv_file}::students")


def test_load_rooms_sqlite_duplicate_room_numbers_raises(tmp_path: Path) -> None:
    db_file = tmp_path / "rooms.db"
    with sqlite3.connect(db_file) as conn:
        conn.execute('CREATE TABLE rooms ("Room Number" TEXT, "Capacity" INTEGER)')
        conn.execute('INSERT INTO rooms ("Room Number", "Capacity") VALUES (?, ?)', ("F-307", 30))
        conn.execute('INSERT INTO rooms ("Room Number", "Capacity") VALUES (?, ?)', ("F-307", 40))
        conn.commit()

    with pytest.raises(DataValidationError, match="Duplicate Room Number values found"):
        load_rooms(str(db_file))
