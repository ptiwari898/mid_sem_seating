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


def make_rooms_template() -> bytes:
    df = pd.DataFrame(
        [
            {"Room Number": "F-307", "Capacity": 40},
            {"Room Number": "F-308", "Capacity": 40},
            {"Room Number": "F-309", "Capacity": 40},
            {"Room Number": "F-310", "Capacity": 30},
        ]
    )
    return df_to_excel_bytes(df)


def make_sample_result_workbook() -> bytes:
    """Generate a realistic SIRT-style result workbook for demo uploads."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        wb = writer.book

        hdr_fmt = wb.add_format(
            {
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "font_size": 12,
                "border": 1,
            }
        )
        col_fmt = wb.add_format(
            {
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "border": 1,
                "bg_color": "#D9E1F2",
            }
        )
        cell_fmt = wb.add_format({"border": 1, "align": "center", "valign": "vcenter"})

        institute = "SAGAR INSTITUTE OF RESEARCH & TECHNOLOGY"
        dept = "DEPARTMENT OF COMPUTER SCIENCE & INFORMATION TECHNOLOGY (CSIT)"
        exam = "I MID SEM EXAMINATION (JAN-JUN 2026)"

        branches = {
            "6th A": [
                ("0133CI231002", "AARBI DHAKAD", 85),
                ("0133CI231008", "ABHISHEK KUMAR", 62),
                ("0133CI231014", "ADITYA KUMAR SHAH", 78),
                ("0133CI231024", "AMANJEET SINGH", 35),
                ("0133CI231035", "ANJALI SHRIVASTAVA", 55),
                ("0133CI231041", "ANKIT PATEL", 90),
                ("0133CI231047", "ANSHUL VERMA", 48),
                ("0133CI231053", "ARPIT MISHRA", 72),
                ("0133CI231059", "ATUL SHARMA", 66),
                ("0133CI231065", "BHAVESH TIWARI", 80),
            ],
            "6th B": [
                ("0133ME231001", "AAKASH SINGH", 70),
                ("0133ME231007", "AASTHA GUPTA", 55),
                ("0133ME231013", "ABHAY KUMAR", 38),
                ("0133ME231019", "ABHINAV RAI", 85),
                ("0133ME231025", "ADITI JAIN", 60),
                ("0133ME231031", "ADITYA THAKUR", 77),
                ("0133ME231037", "AJAY BAGHEL", 92),
                ("0133ME231043", "AKASH CHOUHAN", 44),
                ("0133ME231049", "AKSHAY KORI", 68),
                ("0133ME231055", "ALKA PATEL", 73),
            ],
            "6th C": [
                ("0133EC231003", "AKASH SAHU", 81),
                ("0133EC231009", "ALISHA KHAN", 59),
                ("0133EC231015", "AMANDEEP KHATRI", 36),
                ("0133EC231021", "AMISHA DUBEY", 74),
                ("0133EC231027", "AMRIT PAL", 88),
                ("0133EC231033", "ANANYA SHUKLA", 50),
                ("0133EC231039", "ANKITA YADAV", 67),
                ("0133EC231045", "ANSHIKA TRIPATHI", 41),
                ("0133EC231051", "ANURAG TIWARI", 95),
                ("0133EC231057", "ARJUN SINGH", 63),
            ],
        }

        for sheet_name, students in branches.items():
            ws = wb.add_worksheet(sheet_name)
            ws.set_column(0, 0, 6)
            ws.set_column(1, 1, 22)
            ws.set_column(2, 2, 32)
            ws.set_column(3, 3, 22)

            ws.set_row(0, 20)
            ws.set_row(1, 18)
            ws.set_row(2, 16)
            ws.merge_range("A1:D1", institute, hdr_fmt)
            ws.merge_range("A2:D2", dept, hdr_fmt)
            ws.merge_range("A3:D3", exam, hdr_fmt)
            ws.merge_range("A4:D4", f"Subject: Computer Networks    {sheet_name}", hdr_fmt)

            for col, label in enumerate(["S.No", "Board EnrollNo", "Student Name", "Attendance %"]):
                ws.write(4, col, label, col_fmt)

            for i, (roll, name, att) in enumerate(students):
                ws.write(5 + i, 0, i + 1, cell_fmt)
                ws.write(5 + i, 1, roll, cell_fmt)
                ws.write(5 + i, 2, name, cell_fmt)
                ws.write(5 + i, 3, f"{att}%", cell_fmt)

        ms = wb.add_worksheet("Main Seating")
        ms.set_column(0, 0, 8)
        ms.set_column(1, 1, 16)
        ms.set_column(2, 2, 12)
        ms.set_column(3, 3, 32)
        ms.set_column(4, 4, 26)
        ms.set_column(5, 5, 14)

        ms.merge_range("A1:F1", institute, hdr_fmt)
        ms.merge_range("A2:F2", exam, hdr_fmt)
        ms.merge_range("A3:F3", "MAIN SEATING ARRANGEMENT", hdr_fmt)

        ms_cols = ["S. No.", "BRANCH", "Section", "Roll Number", "No. of Students Appeared", "Class Room"]
        for col, label in enumerate(ms_cols):
            ms.write(3, col, label, col_fmt)

        room_rows = [
            (
                1,
                "CSIT",
                "A",
                "0133CI231002, 0133CI231008, 0133CI231014, 0133CI231024, 0133CI231035, 0133CI231041, 0133CI231047, 0133CI231053, 0133CI231059, 0133CI231065",
                10,
                "F-307",
            ),
            (
                2,
                "ME",
                "B",
                "0133ME231001, 0133ME231007, 0133ME231013, 0133ME231019, 0133ME231025, 0133ME231031, 0133ME231037, 0133ME231043, 0133ME231049, 0133ME231055",
                10,
                "F-308",
            ),
            (
                3,
                "EC",
                "C",
                "0133EC231003, 0133EC231009, 0133EC231015, 0133EC231021, 0133EC231027, 0133EC231033, 0133EC231039, 0133EC231045, 0133EC231051, 0133EC231057",
                10,
                "F-309",
            ),
        ]
        for r, row in enumerate(room_rows):
            for c, val in enumerate(row):
                ms.write(4 + r, c, val, cell_fmt)

        db = wb.add_worksheet("Debarred")
        db.merge_range("A1:E1", institute, hdr_fmt)
        db.merge_range("A2:E2", "Debarred Students List (Attendance < 40%)", hdr_fmt)
        for col, label in enumerate(["S.No", "Board EnrollNo", "Student Name", "Attendance %", "Section"]):
            db.write(2, col, label, col_fmt)
        debarred = [
            (1, "0133CI231024", "AMANJEET SINGH", "35%", "A"),
            (2, "0133ME231013", "ABHAY KUMAR", "38%", "B"),
            (3, "0133EC231015", "AMANDEEP KHATRI", "36%", "C"),
            (4, "0133ME231043", "AKASH CHOUHAN", "44%", "B"),
            (5, "0133EC231045", "ANSHIKA TRIPATHI", "41%", "C"),
        ]
        for r, row in enumerate(debarred):
            for c, val in enumerate(row):
                db.write(3 + r, c, val, cell_fmt)

    return buf.getvalue()
