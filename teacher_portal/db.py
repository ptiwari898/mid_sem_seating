from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from teacher_portal.models import Assignment, MarkEntry, Teacher

DB_PATH = Path(__file__).resolve().parent.parent / "portal.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS teachers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                email       TEXT UNIQUE NOT NULL,
                code_hash   TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS assignments (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id   INTEGER NOT NULL REFERENCES teachers(id),
                exam_session TEXT NOT NULL,
                class_name   TEXT NOT NULL,
                subject      TEXT NOT NULL,
                subject_code TEXT NOT NULL,
                max_marks    INTEGER DEFAULT 30,
                created_at   TEXT DEFAULT (datetime('now')),
                UNIQUE(teacher_id, exam_session, class_name, subject_code)
            );

            CREATE TABLE IF NOT EXISTS marks (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id  INTEGER NOT NULL REFERENCES assignments(id),
                roll_no        TEXT NOT NULL,
                student_name   TEXT NOT NULL,
                mid_sem_marks  REAL,
                is_absent      INTEGER DEFAULT 0,
                submitted_at   TEXT DEFAULT (datetime('now')),
                updated_at     TEXT DEFAULT (datetime('now')),
                UNIQUE(assignment_id, roll_no)
            );
            """
        )


def add_teacher(name: str, email: str, code_hash: str) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO teachers (name, email, code_hash) VALUES (?, ?, ?)",
            (name.strip(), email.strip().lower(), code_hash),
        )
        return int(cursor.lastrowid)


def get_all_teachers() -> list[Teacher]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, name, email FROM teachers ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [Teacher(id=row[0], name=row[1], email=row[2]) for row in rows]


def get_teacher_by_id(teacher_id: int) -> Teacher | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, name, email FROM teachers WHERE id = ?",
            (teacher_id,),
        ).fetchone()
    if row is None:
        return None
    return Teacher(id=row[0], name=row[1], email=row[2])


def get_all_teachers_with_hashes() -> list[tuple[int, str]]:
    with _connect() as conn:
        rows = conn.execute("SELECT id, code_hash FROM teachers").fetchall()
    return [(row[0], row[1]) for row in rows]


def add_assignment(
    teacher_id: int,
    exam_session: str,
    class_name: str,
    subject: str,
    subject_code: str,
    max_marks: int = 30,
) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO assignments (teacher_id, exam_session, class_name, subject, subject_code, max_marks)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                teacher_id,
                exam_session.strip(),
                class_name.strip(),
                subject.strip(),
                subject_code.strip(),
                int(max_marks),
            ),
        )
        return int(cursor.lastrowid)


def _row_to_assignment(row: tuple[object, ...]) -> Assignment:
    return Assignment(
        id=int(row[0]),
        teacher_id=int(row[1]),
        exam_session=str(row[2]),
        class_name=str(row[3]),
        subject=str(row[4]),
        subject_code=str(row[5]),
        max_marks=int(row[6]),
    )


def get_all_assignments() -> list[Assignment]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, teacher_id, exam_session, class_name, subject, subject_code, max_marks
            FROM assignments
            ORDER BY exam_session DESC, class_name COLLATE NOCASE, subject COLLATE NOCASE
            """
        ).fetchall()
    return [_row_to_assignment(row) for row in rows]


def get_assignments_for_teacher(teacher_id: int) -> list[Assignment]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, teacher_id, exam_session, class_name, subject, subject_code, max_marks
            FROM assignments
            WHERE teacher_id = ?
            ORDER BY exam_session DESC, class_name COLLATE NOCASE, subject COLLATE NOCASE
            """,
            (teacher_id,),
        ).fetchall()
    return [_row_to_assignment(row) for row in rows]


def submit_marks(marks: list[MarkEntry]) -> None:
    if not marks:
        return

    payload = []
    for mark in marks:
        is_absent = int(mark.is_absent)
        mid_sem_marks = 0.0 if mark.is_absent else mark.mid_sem_marks
        payload.append(
            (
                mark.assignment_id,
                mark.roll_no.strip(),
                mark.student_name.strip(),
                mid_sem_marks,
                is_absent,
            )
        )

    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO marks (assignment_id, roll_no, student_name, mid_sem_marks, is_absent)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(assignment_id, roll_no) DO UPDATE SET
                student_name = excluded.student_name,
                mid_sem_marks = excluded.mid_sem_marks,
                is_absent = excluded.is_absent,
                updated_at = datetime('now')
            """,
            payload,
        )


def get_marks_for_assignment(assignment_id: int) -> pd.DataFrame:
    with _connect() as conn:
        return pd.read_sql_query(
            """
            SELECT roll_no, student_name, mid_sem_marks, is_absent, submitted_at, updated_at
            FROM marks
            WHERE assignment_id = ?
            ORDER BY roll_no
            """,
            conn,
            params=(assignment_id,),
        )


def get_all_marks_summary(exam_session: str | None = None) -> pd.DataFrame:
    query = """
        SELECT
            a.exam_session,
            a.class_name,
            a.subject,
            a.subject_code,
            a.max_marks,
            t.name AS teacher_name,
            t.email AS teacher_email,
            m.roll_no,
            m.student_name,
            m.mid_sem_marks,
            m.is_absent,
            m.submitted_at,
            m.updated_at
        FROM marks m
        JOIN assignments a ON a.id = m.assignment_id
        JOIN teachers t ON t.id = a.teacher_id
    """
    params: tuple[object, ...] = ()
    if exam_session and exam_session != "All":
        query += " WHERE a.exam_session = ?"
        params = (exam_session,)
    query += " ORDER BY a.exam_session DESC, a.class_name COLLATE NOCASE, a.subject COLLATE NOCASE, m.roll_no"

    with _connect() as conn:
        return pd.read_sql_query(query, conn, params=params)
