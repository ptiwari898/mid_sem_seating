"""
SQLite persistence layer for exam seating runs.

Schema
------
runs              – one row per seating generation run
run_summary       – SeatingSummary fields for each run
seat_allocations  – individual student↔seat assignments
debarred_students – students not eligible for the exam
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

import pandas as pd

DB_PATH = Path("seating_runs.db")

_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           TEXT    NOT NULL UNIQUE,
    created_at       TEXT    NOT NULL,
    institute        TEXT,
    department       TEXT,
    exam_title       TEXT,
    semester         TEXT,
    attendance_cutoff REAL   NOT NULL DEFAULT 40.0,
    shuffle          INTEGER NOT NULL DEFAULT 0,
    alternate_seats  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS run_summary (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                TEXT    NOT NULL UNIQUE,
    total_students        INTEGER NOT NULL,
    eligible_students     INTEGER NOT NULL,
    not_eligible_students INTEGER NOT NULL,
    allocated_students    INTEGER NOT NULL,
    unallocated_students  INTEGER NOT NULL,
    room_count            INTEGER NOT NULL,
    total_capacity        INTEGER NOT NULL,
    effective_capacity    INTEGER NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs (run_id)
);

CREATE TABLE IF NOT EXISTS seat_allocations (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                TEXT    NOT NULL,
    room_number           TEXT    NOT NULL,
    seat_number           INTEGER NOT NULL,
    roll_number           TEXT    NOT NULL,
    student_name          TEXT,
    attendance_percentage REAL,
    section               TEXT,
    branch                TEXT,
    FOREIGN KEY (run_id) REFERENCES runs (run_id)
);

CREATE TABLE IF NOT EXISTS debarred_students (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                TEXT    NOT NULL,
    roll_number           TEXT    NOT NULL,
    student_name          TEXT,
    attendance_percentage REAL,
    section               TEXT,
    branch                TEXT,
    FOREIGN KEY (run_id) REFERENCES runs (run_id)
);
"""


@contextmanager
def _connect() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't exist yet."""
    with _connect() as conn:
        conn.executescript(_DDL)


def save_run(
    run_id: str,
    summary,  # SeatingSummary
    room_allocations: dict[str, pd.DataFrame],
    not_eligible_df: pd.DataFrame,
    *,
    institute: str = "",
    department: str = "",
    exam_title: str = "",
    semester: str = "",
    attendance_cutoff: float = 40.0,
    shuffle: bool = False,
    alternate_seats: bool = False,
) -> None:
    """Persist a completed seating run to the database."""
    init_db()

    with _connect() as conn:
        # runs
        conn.execute(
            """
            INSERT OR REPLACE INTO runs
                (run_id, created_at, institute, department, exam_title, semester,
                 attendance_cutoff, shuffle, alternate_seats)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                datetime.now().isoformat(timespec="seconds"),
                institute,
                department,
                exam_title,
                semester,
                attendance_cutoff,
                int(shuffle),
                int(alternate_seats),
            ),
        )

        # run_summary
        conn.execute(
            """
            INSERT OR REPLACE INTO run_summary
                (run_id, total_students, eligible_students, not_eligible_students,
                 allocated_students, unallocated_students, room_count,
                 total_capacity, effective_capacity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                summary.total_students,
                summary.eligible_students,
                summary.not_eligible_students,
                summary.allocated_students,
                summary.unallocated_students,
                summary.room_count,
                summary.total_capacity,
                summary.effective_capacity,
            ),
        )

        # seat_allocations – delete old rows first (handles OR REPLACE on runs)
        conn.execute("DELETE FROM seat_allocations WHERE run_id = ?", (run_id,))
        for room_number, df in room_allocations.items():
            for _, row in df.iterrows():
                conn.execute(
                    """
                    INSERT INTO seat_allocations
                        (run_id, room_number, seat_number, roll_number,
                         student_name, attendance_percentage, section, branch)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        room_number,
                        int(row.get("Seat Number", 0)),
                        str(row.get("Roll Number", "")),
                        str(row.get("Name", "")),
                        float(row.get("Attendance Percentage", 0.0)),
                        str(row.get("Section", "")) if "Section" in row else None,
                        str(row.get("Branch", ""))  if "Branch"  in row else None,
                    ),
                )

        # debarred_students
        conn.execute("DELETE FROM debarred_students WHERE run_id = ?", (run_id,))
        for _, row in not_eligible_df.iterrows():
            conn.execute(
                """
                INSERT INTO debarred_students
                    (run_id, roll_number, student_name, attendance_percentage, section, branch)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    str(row.get("Roll Number", "")),
                    str(row.get("Name", "")),
                    float(row.get("Attendance Percentage", 0.0)),
                    str(row.get("Section", "")) if "Section" in row else None,
                    str(row.get("Branch", ""))  if "Branch"  in row else None,
                ),
            )


# ── Read helpers ─────────────────────────────────────────────────────────────

def get_run_history() -> pd.DataFrame:
    """Return all runs joined with their summary, newest first."""
    init_db()
    with _connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT
                r.run_id,
                r.created_at,
                r.institute,
                r.exam_title,
                r.semester,
                r.attendance_cutoff,
                r.shuffle,
                r.alternate_seats,
                s.total_students,
                s.eligible_students,
                s.not_eligible_students,
                s.allocated_students,
                s.room_count
            FROM runs r
            LEFT JOIN run_summary s ON r.run_id = s.run_id
            ORDER BY r.created_at DESC
            """,
            conn,
        )
    return df


def get_run_allocations(run_id: str) -> pd.DataFrame:
    """Return all seat allocations for a given run."""
    init_db()
    with _connect() as conn:
        return pd.read_sql_query(
            "SELECT * FROM seat_allocations WHERE run_id = ? ORDER BY room_number, seat_number",
            conn,
            params=(run_id,),
        )


def get_run_debarred(run_id: str) -> pd.DataFrame:
    """Return all debarred students for a given run."""
    init_db()
    with _connect() as conn:
        return pd.read_sql_query(
            "SELECT * FROM debarred_students WHERE run_id = ?",
            conn,
            params=(run_id,),
        )


def delete_run(run_id: str) -> None:
    """Remove a run and all its associated rows."""
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM seat_allocations    WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM debarred_students   WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM run_summary         WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM runs                WHERE run_id = ?", (run_id,))
