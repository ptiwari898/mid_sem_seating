"""Shared SQLite store for marks entry.

A coordinator opens a session from the eligible students of a seating run and gets
a PIN. Any teacher with the PIN can open the session, pick a subject and enter
marks. Data lives in a file so every browser session of the app sees the same rows.
"""
from __future__ import annotations

import os
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

DB_PATH = Path(os.environ.get("MARKS_DB_PATH", "marks_sessions.db"))
SESSION_DAYS = 7
# Wrong PINs allowed per window across ALL browsers, so new sessions cannot reset the count.
MAX_FAILED_PINS = 30
FAILED_PIN_WINDOW_MINUTES = 15
_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class MarksError(ValueError):
    """Raised for bad input; the message is safe to show to the user."""


@dataclass(frozen=True)
class MarksSession:
    id: int
    exam_title: str
    max_marks: float


@dataclass(frozen=True)
class SessionSummary:
    id: int
    pin: str
    exam_title: str
    created_at: str
    expired: bool
    locked: bool
    entries: int  # marks or absences saved, across all subjects
    slots: int  # students x subjects


@dataclass(frozen=True)
class Subject:
    id: int
    name: str


@contextmanager
def _connect():
    """Open the database, commit on success, roll back on error, always close."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            pin        TEXT NOT NULL UNIQUE,
            exam_title TEXT NOT NULL,
            max_marks  REAL NOT NULL,
            created_at TEXT NOT NULL,
            locked     INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS subjects (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            name       TEXT NOT NULL,
            UNIQUE(session_id, name)
        );
        CREATE TABLE IF NOT EXISTS students (
            session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            roll_no    TEXT NOT NULL,
            name       TEXT NOT NULL,
            section    TEXT NOT NULL DEFAULT '',
            branch     TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (session_id, roll_no)
        );
        CREATE TABLE IF NOT EXISTS failed_pins (at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS marks_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
            roll_no    TEXT NOT NULL,
            old_marks  REAL,
            old_absent INTEGER NOT NULL,
            new_marks  REAL,
            new_absent INTEGER NOT NULL,
            entered_by TEXT NOT NULL,
            at         TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS marks (
            subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
            roll_no    TEXT NOT NULL,
            marks      REAL,
            is_absent  INTEGER NOT NULL DEFAULT 0,
            entered_by TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (subject_id, roll_no)
        );
        """
    )
    # Databases made by older versions are missing some columns.
    for table, column, ddl in (
        ("students", "section", "TEXT NOT NULL DEFAULT ''"),
        ("students", "branch", "TEXT NOT NULL DEFAULT ''"),
        ("sessions", "locked", "INTEGER NOT NULL DEFAULT 0"),
    ):
        have = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in have:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> datetime:
    return datetime.now()


def create_session(
    exam_title: str,
    subjects: list[str],
    students: pd.DataFrame,
    max_marks: float = 30,
) -> tuple[str, MarksSession]:
    """Create a session and return its new 6-digit PIN."""
    subject_names = list(dict.fromkeys(s.strip() for s in subjects if s.strip()))
    if not subject_names:
        raise MarksError("Add at least one subject first.")
    if students.empty:
        raise MarksError("There are no eligible students.")
    if max_marks <= 0:
        raise MarksError("Maximum marks must be above 0.")

    def text(row: pd.Series, column: str) -> str:
        value = row.get(column)
        return "" if value is None or pd.isna(value) else str(value).strip()

    roster = [
        (text(r, "Roll Number"), text(r, "Name"), text(r, "Section"), text(r, "Branch"))
        for _, r in students.iterrows()
    ]
    with _connect() as conn:
        pin = _new_pin(conn)
        cursor = conn.execute(
            "INSERT INTO sessions (pin, exam_title, max_marks, created_at) VALUES (?, ?, ?, ?)",
            (pin, exam_title.strip(), float(max_marks), _now().strftime(_TIME_FORMAT)),
        )
        session_id = int(cursor.lastrowid)
        conn.executemany(
            "INSERT INTO subjects (session_id, name) VALUES (?, ?)",
            [(session_id, name) for name in subject_names],
        )
        conn.executemany(
            "INSERT OR IGNORE INTO students (session_id, roll_no, name, section, branch) "
            "VALUES (?, ?, ?, ?, ?)",
            [(session_id, roll, name, section, branch) for roll, name, section, branch in roster],
        )
    return pin, MarksSession(session_id, exam_title.strip(), float(max_marks))


def _new_pin(conn: sqlite3.Connection) -> str:
    in_use = {row[0] for row in conn.execute("SELECT pin FROM sessions")}
    while True:
        pin = f"{secrets.randbelow(1_000_000):06d}"
        if pin not in in_use:
            return pin


def find_session(pin: str) -> MarksSession | None:
    """Return the session for a PIN, or None if unknown or older than SESSION_DAYS.

    Raises MarksError once too many wrong PINs were tried recently, from any browser.
    """
    now = _now()
    oldest = (now - timedelta(days=SESSION_DAYS)).strftime(_TIME_FORMAT)
    window = (now - timedelta(minutes=FAILED_PIN_WINDOW_MINUTES)).strftime(_TIME_FORMAT)
    with _connect() as conn:
        conn.execute("DELETE FROM failed_pins WHERE at < ?", (window,))
        failures = conn.execute("SELECT COUNT(*) FROM failed_pins").fetchone()[0]
        if failures >= MAX_FAILED_PINS:
            raise MarksError(
                f"Too many wrong PINs were tried. Wait {FAILED_PIN_WINDOW_MINUTES} minutes and retry."
            )
        row = conn.execute(
            "SELECT id, exam_title, max_marks FROM sessions WHERE pin = ? AND created_at >= ?",
            (pin.strip(), oldest),
        ).fetchone()
        if row is None:
            conn.execute("INSERT INTO failed_pins (at) VALUES (?)", (now.strftime(_TIME_FORMAT),))
    return None if row is None else MarksSession(row[0], row[1], row[2])


def list_sessions() -> list[SessionSummary]:
    """Every session, newest first, with how much marks entry is done. For the coordinator."""
    oldest = (_now() - timedelta(days=SESSION_DAYS)).strftime(_TIME_FORMAT)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.pin, s.exam_title, s.created_at,
                   s.locked,
                   (SELECT COUNT(*) FROM marks m JOIN subjects u ON u.id = m.subject_id
                     WHERE u.session_id = s.id AND (m.marks IS NOT NULL OR m.is_absent = 1)),
                   (SELECT COUNT(*) FROM students t WHERE t.session_id = s.id)
                   * (SELECT COUNT(*) FROM subjects u WHERE u.session_id = s.id)
            FROM sessions s ORDER BY s.id DESC
            """
        ).fetchall()
    return [
        SessionSummary(r[0], r[1], r[2], r[3], r[3] < oldest, bool(r[4]), r[5], r[6]) for r in rows
    ]


def is_locked(session_id: int) -> bool:
    with _connect() as conn:
        row = conn.execute("SELECT locked FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return bool(row and row[0])


def set_locked(session_id: int, locked: bool) -> None:
    """Finalise (or reopen) a session: while locked, no marks can be saved."""
    with _connect() as conn:
        conn.execute("UPDATE sessions SET locked = ? WHERE id = ?", (int(locked), session_id))


def export_history(session_id: int) -> pd.DataFrame:
    """Every change to a mark in the session, oldest first."""
    with _connect() as conn:
        return pd.read_sql_query(
            """
            SELECT l.at AS "When", u.name AS "Subject", l.roll_no AS "Roll Number",
                   l.old_marks AS "Old Marks", l.old_absent AS "Old Absent",
                   l.new_marks AS "New Marks", l.new_absent AS "New Absent",
                   l.entered_by AS "Entered By"
            FROM marks_log l JOIN subjects u ON u.id = l.subject_id
            WHERE u.session_id = ? ORDER BY l.id
            """,
            conn,
            params=(session_id,),
        )


def delete_session(session_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def list_subjects(session_id: int) -> list[Subject]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, name FROM subjects WHERE session_id = ? ORDER BY id", (session_id,)
        ).fetchall()
    return [Subject(r[0], r[1]) for r in rows]


def get_marks_table(session_id: int, subject_id: int, section: str | None = None) -> pd.DataFrame:
    """Students of the session (optionally one section) with marks already saved for the subject."""
    with _connect() as conn:
        return pd.read_sql_query(
            """
            SELECT s.roll_no AS "Roll Number", s.name AS "Name",
                   s.branch AS "Branch", s.section AS "Section",
                   m.marks AS "Marks", COALESCE(m.is_absent, 0) AS "Absent"
            FROM students s
            LEFT JOIN marks m ON m.roll_no = s.roll_no AND m.subject_id = ?
            WHERE s.session_id = ? AND (? IS NULL OR s.section = ?)
            ORDER BY s.roll_no
            """,
            conn,
            params=(subject_id, session_id, section, section),
        ).astype({"Absent": bool})


def list_sections(session_id: int) -> list[str]:
    """Distinct non-empty sections in the roster, for the teacher's filter."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT section FROM students WHERE session_id = ? AND section != '' ORDER BY section",
            (session_id,),
        ).fetchall()
    return [r[0] for r in rows]


def _cell(row: pd.Series) -> tuple[float | None, bool]:
    absent = bool(row["Absent"])
    return (None if absent or pd.isna(row["Marks"]) else float(row["Marks"])), absent


def save_marks(
    session: MarksSession,
    subject_id: int,
    table: pd.DataFrame,
    entered_by: str,
    original: pd.DataFrame | None = None,
) -> int:
    """Save the edited table. Absent students keep no marks. Returns rows saved.

    Pass the table the teacher started from as `original`: only rows that differ
    from it are written, so a stale table cannot blank marks another teacher saved.
    """
    before = {} if original is None else {
        str(r["Roll Number"]): _cell(r) for _, r in original.iterrows()
    }
    rows = []
    for _, r in table.iterrows():
        if before.get(str(r["Roll Number"])) == _cell(r):
            continue
        absent = bool(r["Absent"])
        value = None if absent or pd.isna(r["Marks"]) else float(r["Marks"])
        if value is not None and not 0 <= value <= session.max_marks:
            raise MarksError(
                f"Marks for {r['Roll Number']} must be between 0 and {session.max_marks:g}."
            )
        rows.append(
            (subject_id, str(r["Roll Number"]), value, int(absent), entered_by.strip(),
             _now().strftime(_TIME_FORMAT))
        )
    if not rows:
        return 0
    with _connect() as conn:
        # The subject must belong to this session, so a PIN cannot write to another one.
        owner = conn.execute(
            "SELECT session_id FROM subjects WHERE id = ?", (subject_id,)
        ).fetchone()
        if owner is None or owner[0] != session.id:
            raise MarksError("Unknown subject for this session.")
        locked = conn.execute("SELECT locked FROM sessions WHERE id = ?", (session.id,)).fetchone()
        if locked and locked[0]:
            raise MarksError("Marks entry is locked by the coordinator.")
        for subject, roll, value, absent, who, when in rows:
            old = conn.execute(
                "SELECT marks, is_absent FROM marks WHERE subject_id = ? AND roll_no = ?",
                (subject, roll),
            ).fetchone() or (None, 0)
            conn.execute(
                "INSERT INTO marks_log (subject_id, roll_no, old_marks, old_absent, new_marks, "
                "new_absent, entered_by, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (subject, roll, old[0], old[1], value, absent, who, when),
            )
        conn.executemany(
            """
            INSERT INTO marks (subject_id, roll_no, marks, is_absent, entered_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(subject_id, roll_no) DO UPDATE SET
                marks = excluded.marks, is_absent = excluded.is_absent,
                entered_by = excluded.entered_by, updated_at = excluded.updated_at
            """,
            rows,
        )
    return len(rows)


def export_marks(session_id: int) -> pd.DataFrame:
    """One row per student, one column per subject ("AB" for absent, blank if not entered)."""
    with _connect() as conn:
        students = pd.read_sql_query(
            'SELECT roll_no AS "Roll Number", name AS "Name" FROM students '
            "WHERE session_id = ? ORDER BY roll_no",
            conn, params=(session_id,),
        )
        marks = pd.read_sql_query(
            """
            SELECT s.name AS subject, m.roll_no, m.marks, m.is_absent
            FROM marks m JOIN subjects s ON s.id = m.subject_id
            WHERE s.session_id = ?
            """,
            conn, params=(session_id,),
        )
        subject_names = [s.name for s in list_subjects(session_id)]
    for name in subject_names:
        students[name] = ""
    for _, r in marks.iterrows():
        cell = "AB" if r["is_absent"] else ("" if pd.isna(r["marks"]) else f"{r['marks']:g}")
        students.loc[students["Roll Number"] == r["roll_no"], r["subject"]] = cell
    return students
