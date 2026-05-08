from __future__ import annotations

import pytest

from experimental.result_analyzer import ResultDatabase


def test_overall_statistics_counts_only_all_subject_pass_students(tmp_path) -> None:
    db = ResultDatabase(str(tmp_path / "result_analysis.db"))

    faculty_id = db.add_faculty("Prof. A")
    sub1_id = db.add_subject("CSIT-601", "SE", faculty_id)
    sub2_id = db.add_subject("CSIT-602", "CN", faculty_id)

    s1 = db.add_student("R001", "Alice", "A", "6")
    s2 = db.add_student("R002", "Bob", "A", "6")
    s3 = db.add_student("R003", "Cara", "A", "6")
    s4 = db.add_student("R004", "Drew", "A", "6")

    # Present student with all subjects passed.
    db.add_attendance(s1, "PRESENT")
    db.add_result(s1, sub1_id, 70, "Pass")
    db.add_result(s1, sub2_id, 68, "Pass")

    # Present student with one subject failed.
    db.add_attendance(s2, "PRESENT")
    db.add_result(s2, sub1_id, 55, "Pass")
    db.add_result(s2, sub2_id, 30, "Fail")

    # Present student with no recorded results.
    db.add_attendance(s3, "PRESENT")

    # Absent student should not affect totals.
    db.add_attendance(s4, "ABSENT")
    db.add_result(s4, sub1_id, 99, "Pass")

    stats = db.get_overall_statistics()

    assert stats["total_students"] == 3
    assert stats["passed_students"] == 1
    assert stats["result_percentage"] == 33.33

    db.close()


def test_add_attendance_normalizes_mixed_case_status(tmp_path) -> None:
    db = ResultDatabase(str(tmp_path / "result_analysis.db"))
    student_id = db.add_student("R010", "Evan", "A", "6")

    db.add_attendance(student_id, "Absent")

    conn = db._get_connection()
    row = conn.execute(
        "SELECT status FROM attendance WHERE student_id = ?", (student_id,)
    ).fetchone()

    assert row is not None
    assert row[0] == "ABSENT"

    db.close()


def test_add_attendance_rejects_invalid_status(tmp_path) -> None:
    db = ResultDatabase(str(tmp_path / "result_analysis.db"))
    student_id = db.add_student("R011", "Fia", "A", "6")

    with pytest.raises(ValueError, match="Use PRESENT or ABSENT"):
        db.add_attendance(student_id, "Leave")

    db.close()


def test_clear_all_also_clears_analysis_sessions(tmp_path) -> None:
    db = ResultDatabase(str(tmp_path / "result_analysis.db"))

    conn = db._get_connection()
    conn.execute(
        """
        INSERT INTO analysis_sessions (
            session_name,
            created_at,
            pass_threshold,
            total_students,
            present_students,
            passed_students
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("run-1", "2026-05-08 10:00:00", 40.0, 10, 9, 7),
    )
    conn.commit()

    before = conn.execute("SELECT COUNT(*) FROM analysis_sessions").fetchone()[0]
    assert before == 1

    db.clear_all()

    after = conn.execute("SELECT COUNT(*) FROM analysis_sessions").fetchone()[0]
    assert after == 0

    db.close()
