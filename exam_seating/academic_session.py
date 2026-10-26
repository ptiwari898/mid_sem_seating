"""The academic session (JAN-JUN or JULY-DEC) a date falls in, for exam titles."""
from __future__ import annotations

from datetime import date

EXAM_NAME = "I MID SEM EXAMINATION"


def current_session(today: date | None = None) -> str:
    """"JAN-JUN 2026" from January to June, "JULY-DEC 2026" from July to December."""
    today = today or date.today()
    months = "JAN-JUN" if today.month <= 6 else "JULY-DEC"
    return f"{months} {today.year}"


def default_exam_title(today: date | None = None) -> str:
    """"I MID SEM EXAMINATION (JULY-DEC 2026)": the exam name plus the session of `today`."""
    return f"{EXAM_NAME} ({current_session(today)})"
