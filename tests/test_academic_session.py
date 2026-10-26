from __future__ import annotations

from datetime import date

import openpyxl
import pandas as pd
import pytest

from exam_seating import academic_session
from exam_seating.academic_session import current_session, default_exam_title
from exam_seating.sirt_exporters import export_sirt_debarred_excel


@pytest.mark.parametrize(
    "day, expected",
    [
        (date(2026, 1, 1), "JAN-JUN 2026"),
        (date(2026, 6, 30), "JAN-JUN 2026"),
        (date(2026, 7, 1), "JULY-DEC 2026"),
        (date(2026, 10, 26), "JULY-DEC 2026"),
        (date(2026, 12, 31), "JULY-DEC 2026"),
        (date(2027, 1, 1), "JAN-JUN 2027"),
    ],
)
def test_session_follows_the_month_and_year(day, expected):
    assert current_session(day) == expected


def test_default_title_keeps_the_exam_name():
    assert default_exam_title(date(2026, 10, 26)) == "I MID SEM EXAMINATION (JULY-DEC 2026)"


def test_exporter_uses_todays_session_when_no_title_is_given(tmp_path, monkeypatch):
    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 8, 15)

    monkeypatch.setattr(academic_session, "date", FakeDate)
    debarred = pd.DataFrame(
        [["9", "Z", 10.0]], columns=["Roll Number", "Name", "Attendance Percentage"]
    )
    path = export_sirt_debarred_excel(debarred, tmp_path)  # no exam_title passed

    cells = {str(c.value) for ws in openpyxl.load_workbook(path).worksheets for row in ws.iter_rows() for c in row}
    assert "I MID SEM EXAMINATION (JULY-DEC 2026)" in cells
