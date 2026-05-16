from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Teacher:
    id: int
    name: str
    email: str


@dataclass(frozen=True)
class Assignment:
    id: int
    teacher_id: int
    exam_session: str
    class_name: str
    subject: str
    subject_code: str
    max_marks: int


@dataclass(frozen=True)
class MarkEntry:
    assignment_id: int
    roll_no: str
    student_name: str
    mid_sem_marks: float | None
    is_absent: bool
