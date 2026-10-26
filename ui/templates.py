from __future__ import annotations

import io

import pandas as pd

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def make_students_template() -> bytes:
    df = pd.DataFrame(
        [
            {"Roll Number": "0133CI231002", "Name": "AARBI DHAKAD", "Attendance Percentage": 82},
            {"Roll Number": "0133CI231008", "Name": "ABHISHEK KUMAR", "Attendance Percentage": 61},
            {"Roll Number": "0133CI231014", "Name": "ADITYA KUMAR SHAH", "Attendance Percentage": 75},
            {"Roll Number": "0133CI231024", "Name": "AMANJEET SINGH", "Attendance Percentage": 38},
            {"Roll Number": "0133CI231035", "Name": "ANJALI SHRIVASTAVA", "Attendance Percentage": 55},
        ]
    )
    return df_to_excel_bytes(df)
