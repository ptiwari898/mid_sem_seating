from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Dict

import pandas as pd


class DataValidationError(ValueError):
    """Raised when input files are missing required columns or valid values."""


def _normalized_key(value: str) -> str:
    return "".join(ch for ch in str(value).strip().lower() if ch.isalnum())


def _split_sqlite_spec(file_path: str | Path) -> tuple[Path, str | None]:
    """Support SQLite spec in the form: path/to/file.db::table_name."""
    text = str(file_path)
    if "::" not in text:
        return Path(text), None

    db_path, table_name = text.split("::", 1)
    table_name = table_name.strip() or None
    return Path(db_path), table_name


def _read_sqlite_table(db_path: Path, table_name: str) -> pd.DataFrame:
    try:
        with sqlite3.connect(db_path) as conn:
            tables = pd.read_sql_query(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name", conn
            )
            available_tables = tables["name"].astype(str).tolist()
            if table_name not in available_tables:
                raise DataValidationError(
                    f"Table '{table_name}' not found in {db_path.name}. "
                    f"Available tables: {available_tables or 'none'}"
                )
            # Use proper identifier escaping for SQLite (double quotes are escaped by doubling them)
            escaped_table_name = table_name.replace('"', '""')
            return pd.read_sql_query(f'SELECT * FROM "{escaped_table_name}"', conn)
    except sqlite3.Error as exc:
        raise DataValidationError(f"Failed to read SQLite database {db_path}: {exc}") from exc


def _read_table(file_path: str | Path, default_sqlite_table: str | None = None) -> pd.DataFrame:
    path, sqlite_table = _split_sqlite_spec(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()
    if sqlite_table and suffix not in {".db", ".sqlite", ".sqlite3"}:
        raise DataValidationError(
            f"Table specifier is only supported for SQLite files: {path.name}"
        )

    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix in {".db", ".sqlite", ".sqlite3"}:
        table_name = sqlite_table or default_sqlite_table
        if not table_name:
            raise DataValidationError(
                "SQLite input requires a table name. "
                "Use path::table_name or provide a default table."
            )
        return _read_sqlite_table(path, table_name)

    raise DataValidationError(
        f"Unsupported file format for {path.name}. "
        "Use CSV, Excel (.xlsx/.xls), or SQLite (.db/.sqlite/.sqlite3)."
    )


def _rename_columns(df: pd.DataFrame, expected_map: Dict[str, str]) -> pd.DataFrame:
    normalized_to_real = {_normalized_key(col): col for col in df.columns}
    rename_map: Dict[str, str] = {}

    for normalized_expected, canonical_name in expected_map.items():
        if normalized_expected not in normalized_to_real:
            raise DataValidationError(
                f"Missing required column '{canonical_name}'. Found columns: {list(df.columns)}"
            )
        rename_map[normalized_to_real[normalized_expected]] = canonical_name

    return df.rename(columns=rename_map)


def load_students(file_path: str | Path) -> pd.DataFrame:
    raw = _read_table(file_path, default_sqlite_table="students")
    expected = {
        _normalized_key("Roll Number"): "Roll Number",
        _normalized_key("Name"): "Name",
        _normalized_key("Attendance Percentage"): "Attendance Percentage",
    }
    students = _rename_columns(raw, expected)[
        ["Roll Number", "Name", "Attendance Percentage"]
    ].copy()

    students["Roll Number"] = students["Roll Number"].astype(str).str.strip()
    students["Name"] = students["Name"].astype(str).str.strip()

    attendance_text = (
        students["Attendance Percentage"].astype(str).str.replace("%", "", regex=False).str.strip()
    )
    students["Attendance Percentage"] = pd.to_numeric(attendance_text, errors="coerce")

    missing_roll = students["Roll Number"].eq("")
    missing_name = students["Name"].eq("")
    invalid_attendance = students["Attendance Percentage"].isna()

    invalid_rows = missing_roll | missing_name | invalid_attendance
    if invalid_rows.any():
        bad = students[invalid_rows].copy()
        bad["Issue"] = ""
        bad.loc[missing_roll, "Issue"] += "Missing Roll Number; "
        bad.loc[missing_name, "Issue"] += "Missing Name; "
        bad.loc[invalid_attendance, "Issue"] += "Invalid Attendance Percentage; "
        preview = bad[["Roll Number", "Name", "Attendance Percentage", "Issue"]].head(10)
        raise DataValidationError(
            "Invalid student data in one or more rows. Example rows:\n"
            f"{preview.to_string(index=False)}"
        )

    out_of_range = (students["Attendance Percentage"] < 0) | (
        students["Attendance Percentage"] > 100
    )
    if out_of_range.any():
        preview = students.loc[out_of_range, ["Roll Number", "Name", "Attendance Percentage"]].head(10)
        raise DataValidationError(
            "Attendance Percentage must be between 0 and 100. Example rows:\n"
            f"{preview.to_string(index=False)}"
        )

    return students


def load_rooms(file_path: str | Path) -> pd.DataFrame:
    raw = _read_table(file_path, default_sqlite_table="rooms")
    expected = {
        _normalized_key("Room Number"): "Room Number",
        _normalized_key("Capacity"): "Capacity",
    }
    rooms = _rename_columns(raw, expected)[["Room Number", "Capacity"]].copy()

    rooms["Room Number"] = rooms["Room Number"].astype(str).str.strip()
    rooms["Capacity"] = pd.to_numeric(rooms["Capacity"], errors="coerce")

    missing_room = rooms["Room Number"].eq("")
    invalid_capacity = rooms["Capacity"].isna()
    non_positive = rooms["Capacity"] <= 0

    invalid_rows = missing_room | invalid_capacity | non_positive
    if invalid_rows.any():
        bad = rooms[invalid_rows].copy()
        bad["Issue"] = ""
        bad.loc[missing_room, "Issue"] += "Missing Room Number; "
        bad.loc[invalid_capacity, "Issue"] += "Invalid Capacity; "
        bad.loc[non_positive, "Issue"] += "Capacity must be > 0; "
        preview = bad[["Room Number", "Capacity", "Issue"]].head(10)
        raise DataValidationError(
            "Invalid room data in one or more rows. Example rows:\n"
            f"{preview.to_string(index=False)}"
        )

    rooms["Capacity"] = rooms["Capacity"].astype(int)
    if rooms["Room Number"].duplicated().any():
        duplicates = rooms.loc[rooms["Room Number"].duplicated(), "Room Number"].tolist()
        raise DataValidationError(
            f"Duplicate Room Number values found: {duplicates}. Room numbers must be unique."
        )

    return rooms
