"""
Result Analysis System using SQLite.

Handles:
- Storing student results, attendance, and marks
- Querying and analyzing results
- Filtering absent students
- Generating pass/fail statistics by faculty, subject, section
"""

import sqlite3
from pathlib import Path
from typing import Optional, Dict, List, Any
import pandas as pd
from datetime import datetime


class ResultDatabase:
    """SQLite database for result analysis."""

    def __init__(self, db_path: str = "result_analysis.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self.connection is None:
            self.connection = sqlite3.connect(str(self.db_path))
            self.connection.row_factory = sqlite3.Row
        return self.connection

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Faculties table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faculties (
                faculty_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                branch TEXT
            )
        """)

        # Subjects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                faculty_id INTEGER,
                FOREIGN KEY (faculty_id) REFERENCES faculties(faculty_id)
            )
        """)

        # Students table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_number TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                section TEXT,
                semester TEXT
            )
        """)

        # Results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                marks REAL,
                status TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (subject_id) REFERENCES subjects(subject_id),
                UNIQUE(student_id, subject_id)
            )
        """)

        # Attendance table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER UNIQUE NOT NULL,
                status TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        """)

        # Analysis sessions (for tracking runs)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_name TEXT,
                created_at TIMESTAMP,
                pass_threshold REAL,
                total_students INTEGER,
                present_students INTEGER,
                passed_students INTEGER
            )
        """)

        conn.commit()

    def add_faculty(self, name: str, branch: Optional[str] = None) -> int:
        """Add a faculty and return faculty_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO faculties (name, branch) VALUES (?, ?)",
            (name, branch)
        )
        conn.commit()
        cursor.execute("SELECT faculty_id FROM faculties WHERE name = ?", (name,))
        return cursor.fetchone()[0]

    def add_subject(self, code: str, name: str, faculty_id: int) -> int:
        """Add a subject and return subject_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO subjects (code, name, faculty_id) VALUES (?, ?, ?)",
            (code, name, faculty_id)
        )
        conn.commit()
        cursor.execute("SELECT subject_id FROM subjects WHERE code = ?", (code,))
        return cursor.fetchone()[0]

    def add_student(self, roll_number: str, name: str, section: str, semester: str) -> int:
        """Add a student and return student_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO students (roll_number, name, section, semester) VALUES (?, ?, ?, ?)",
            (roll_number, name, section, semester)
        )
        conn.commit()
        cursor.execute("SELECT student_id FROM students WHERE roll_number = ?", (roll_number,))
        return cursor.fetchone()[0]

    def add_result(self, student_id: int, subject_id: int, marks: float, status: str = None):
        """Add a result for a student-subject pair."""
        conn = self._get_connection()
        cursor = conn.cursor()
        if status is None:
            status = "Pass" if marks >= 40 else "Fail"
        cursor.execute(
            """INSERT OR REPLACE INTO results (student_id, subject_id, marks, status)
               VALUES (?, ?, ?, ?)""",
            (student_id, subject_id, marks, status)
        )
        conn.commit()

    def add_attendance(self, student_id: int, status: str):
        """Add attendance status for a student.

        Accepted statuses are PRESENT and ABSENT (case-insensitive input).
        """
        normalized_status = str(status).strip().upper()
        if normalized_status not in {"PRESENT", "ABSENT"}:
            raise ValueError(
                f"Invalid attendance status '{status}'. Use PRESENT or ABSENT."
            )

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO attendance (student_id, status) VALUES (?, ?)",
            (student_id, normalized_status)
        )
        conn.commit()

    def import_from_dataframe(
        self,
        df: pd.DataFrame,
        pass_threshold: float = 40.0,
        semester: str = "Unknown"
    ):
        """
        Import results from a DataFrame.
        Expected columns: roll_number, name, section, attendance, [subject columns with marks]
        Subject column format: "CODE NAME-FACULTY" (e.g., "CSIT-601 SE-Prof. Vivek Rawal")
        """
        # Get all faculty names from columns (assuming pattern like "CODE NAME-Faculty")
        faculties_dict = {}
        subjects_dict = {}

        # Expected columns
        expected_cols = {"roll_number", "name", "section", "attendance"}
        subject_cols = [col for col in df.columns if col.lower() not in expected_cols]

        for col in subject_cols:
            # Parse subject column - format: "CODE NAME-FACULTY"
            # Example: "CSIT-601 SE-Prof. Vivek Rawal"
            if "-Prof." in col or "-Dr." in col:
                # Split by the last occurrence of dash before Prof/Dr
                parts = col.rsplit("-Prof.", 1)
                if len(parts) == 2:
                    code_name = parts[0].strip()
                    faculty = "Prof. " + parts[1].strip()
                else:
                    # Try Dr.
                    parts = col.rsplit("-Dr.", 1)
                    if len(parts) == 2:
                        code_name = parts[0].strip()
                        faculty = "Dr. " + parts[1].strip()
                    else:
                        code_name = col
                        faculty = "Unassigned"
            else:
                code_name = col
                faculty = "Unassigned"

            # Extract code (first word/part before space)
            code_parts = code_name.split()
            code = code_parts[0] if code_parts else col
            name = code_name if len(code_parts) <= 1 else " ".join(code_parts[1:])

            if faculty not in faculties_dict:
                faculties_dict[faculty] = self.add_faculty(faculty)
            
            if code not in subjects_dict:
                subjects_dict[code] = self.add_subject(code, name, faculties_dict[faculty])

        # Add students and results
        for _, row in df.iterrows():
            roll = row.get("roll_number", "").strip()
            name = row.get("name", "").strip()
            section = row.get("section", "").strip()
            attendance = row.get("attendance", "Present").strip().upper()

            if not roll or not name:
                continue

            student_id = self.add_student(roll, name, section, semester)
            self.add_attendance(student_id, attendance)

            # Add results for each subject
            for col in subject_cols:
                if pd.notna(row.get(col)):
                    try:
                        marks = float(row[col])
                        # Get code from column
                        code_parts = col.split()
                        code = code_parts[0] if code_parts else col
                        subject_id = subjects_dict.get(code)
                        if subject_id:
                            status = "Pass" if marks >= pass_threshold else "Fail"
                            self.add_result(student_id, subject_id, marks, status)
                    except (ValueError, KeyError):
                        pass

    def get_overall_statistics(self) -> Dict[str, Any]:
        """Get overall result statistics (excluding absent students).

        Pass policy for overall statistics:
        - A student is counted as passed only if all recorded subject results are PASS.
        - Students with no recorded results are treated as not passed.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total present students
        cursor.execute("""
            SELECT COUNT(DISTINCT s.student_id) as count
            FROM students s
            LEFT JOIN attendance a ON s.student_id = a.student_id
            WHERE a.status IS NULL OR a.status != 'ABSENT'
        """)
        present_students = cursor.fetchone()[0] or 0

        # Students who passed (all recorded subjects are PASS, with at least one subject result)
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM (
                SELECT r.student_id
                FROM results r
                JOIN students s ON s.student_id = r.student_id
                LEFT JOIN attendance a ON s.student_id = a.student_id
                WHERE a.status IS NULL OR a.status != 'ABSENT'
                GROUP BY r.student_id
                HAVING COUNT(*) > 0
                   AND SUM(CASE WHEN UPPER(COALESCE(r.status, '')) = 'PASS' THEN 0 ELSE 1 END) = 0
            )
        """)
        passed_students = cursor.fetchone()[0] or 0

        result_percentage = (passed_students / present_students * 100) if present_students > 0 else 0

        return {
            "total_students": present_students,
            "passed_students": passed_students,
            "result_percentage": round(result_percentage, 2),
        }

    def get_faculty_wise_analysis(self) -> List[Dict[str, Any]]:
        """Get result analysis grouped by faculty."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                f.name as faculty_name,
                COUNT(DISTINCT CASE WHEN r.student_id IN (
                    SELECT s.student_id FROM students s
                    LEFT JOIN attendance a ON s.student_id = a.student_id
                    WHERE a.status IS NULL OR a.status != 'ABSENT'
                ) THEN r.student_id END) as students_appeared,
                COUNT(DISTINCT CASE WHEN r.status = 'Pass' AND r.student_id IN (
                    SELECT s.student_id FROM students s
                    LEFT JOIN attendance a ON s.student_id = a.student_id
                    WHERE a.status IS NULL OR a.status != 'ABSENT'
                ) THEN r.student_id END) as students_passed
            FROM faculties f
            LEFT JOIN subjects sub ON f.faculty_id = sub.faculty_id
            LEFT JOIN results r ON sub.subject_id = r.subject_id
            GROUP BY f.faculty_id, f.name
            ORDER BY f.name
        """)

        results = []
        for row in cursor.fetchall():
            appeared = row[1] or 0
            passed = row[2] or 0
            pct = (passed / appeared * 100) if appeared > 0 else 0
            results.append({
                "faculty": row[0],
                "appeared": appeared,
                "passed": passed,
                "result_percentage": round(pct, 2),
            })

        return results

    def get_subject_wise_analysis(self) -> List[Dict[str, Any]]:
        """Get result analysis grouped by subject."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                sub.code,
                sub.name,
                f.name as faculty_name,
                COUNT(DISTINCT CASE WHEN r.student_id IN (
                    SELECT s.student_id FROM students s
                    LEFT JOIN attendance a ON s.student_id = a.student_id
                    WHERE a.status IS NULL OR a.status != 'ABSENT'
                ) THEN r.student_id END) as students_appeared,
                COUNT(DISTINCT CASE WHEN r.status = 'Pass' AND r.student_id IN (
                    SELECT s.student_id FROM students s
                    LEFT JOIN attendance a ON s.student_id = a.student_id
                    WHERE a.status IS NULL OR a.status != 'ABSENT'
                ) THEN r.student_id END) as students_passed
            FROM subjects sub
            LEFT JOIN faculties f ON sub.faculty_id = f.faculty_id
            LEFT JOIN results r ON sub.subject_id = r.subject_id
            GROUP BY sub.subject_id, sub.code, sub.name, f.name
            ORDER BY sub.code
        """)

        results = []
        for row in cursor.fetchall():
            appeared = row[3] or 0
            passed = row[4] or 0
            pct = (passed / appeared * 100) if appeared > 0 else 0
            results.append({
                "code": row[0],
                "name": row[1],
                "faculty": row[2],
                "appeared": appeared,
                "passed": passed,
                "result_percentage": round(pct, 2),
            })

        return results

    def get_section_wise_analysis(self) -> List[Dict[str, Any]]:
        """Get result analysis grouped by section."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                s.section,
                COUNT(DISTINCT CASE WHEN a.status IS NULL OR a.status != 'ABSENT' THEN s.student_id END) as appeared,
                COUNT(DISTINCT CASE WHEN r.status = 'Pass' AND (a.status IS NULL OR a.status != 'ABSENT') THEN r.student_id END) as passed
            FROM students s
            LEFT JOIN attendance a ON s.student_id = a.student_id
            LEFT JOIN results r ON s.student_id = r.student_id
            GROUP BY s.section
            ORDER BY s.section
        """)

        results = []
        for row in cursor.fetchall():
            appeared = row[1] or 0
            passed = row[2] or 0
            pct = (passed / appeared * 100) if appeared > 0 else 0
            results.append({
                "section": row[0],
                "appeared": appeared,
                "passed": passed,
                "result_percentage": round(pct, 2),
            })

        return results

    def get_section_faculty_analysis(self) -> List[Dict[str, Any]]:
        """Get result analysis by section and faculty."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                s.section,
                f.name as faculty_name,
                sub.code,
                COUNT(DISTINCT CASE WHEN a.status IS NULL OR a.status != 'ABSENT' THEN r.student_id END) as appeared,
                COUNT(DISTINCT CASE WHEN r.status = 'Pass' AND (a.status IS NULL OR a.status != 'ABSENT') THEN r.student_id END) as passed
            FROM students s
            LEFT JOIN attendance a ON s.student_id = a.student_id
            LEFT JOIN results r ON s.student_id = r.student_id
            LEFT JOIN subjects sub ON r.subject_id = sub.subject_id
            LEFT JOIN faculties f ON sub.faculty_id = f.faculty_id
            GROUP BY s.section, f.faculty_id, f.name, sub.subject_id, sub.code
            ORDER BY s.section, f.name, sub.code
        """)

        results = []
        for row in cursor.fetchall():
            appeared = row[3] or 0
            passed = row[4] or 0
            pct = (passed / appeared * 100) if appeared > 0 else 0
            results.append({
                "section": row[0],
                "faculty": row[1],
                "subject_code": row[2],
                "appeared": appeared,
                "passed": passed,
                "result_percentage": round(pct, 2),
            })

        return results

    def clear_all(self):
        """Clear all data from database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM results")
        cursor.execute("DELETE FROM attendance")
        cursor.execute("DELETE FROM students")
        cursor.execute("DELETE FROM subjects")
        cursor.execute("DELETE FROM faculties")
        cursor.execute("DELETE FROM analysis_sessions")
        conn.commit()

    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
