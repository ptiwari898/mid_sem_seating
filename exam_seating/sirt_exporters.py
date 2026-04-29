"""
SIRT-branded Excel exporter.

Produces formatted workbooks matching the institute's style:
  - Merged header rows with institute/department/exam title
  - Main seating sheet: Branch | Section | Roll Numbers | Count | Room
  - Debarred list sheet: S.NO | Board EnrollNo | Student Name
  - Attendance sheet per room: S.NO | Board EnrollNo | Student Name | Signature
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd


def _write_sirt_header(
    ws,
    workbook,
    total_cols: int,
    institute: str,
    department: str,
    exam_title: str,
    sub_title: str = "",
) -> int:
    """Write 3–4 merged title rows. Returns the next available row index (0-based)."""
    bold_center = workbook.add_format(
        {"bold": True, "align": "center", "valign": "vcenter", "font_size": 12, "border": 1}
    )
    sub_fmt = workbook.add_format(
        {"bold": True, "align": "center", "valign": "vcenter", "font_size": 11, "border": 1}
    )

    last_col = total_cols - 1
    row = 0
    ws.merge_range(row, 0, row, last_col, institute, bold_center)
    ws.set_row(row, 20)
    row += 1
    ws.merge_range(row, 0, row, last_col, department, bold_center)
    ws.set_row(row, 18)
    row += 1
    ws.merge_range(row, 0, row, last_col, exam_title, bold_center)
    ws.set_row(row, 18)
    row += 1
    if sub_title:
        ws.merge_range(row, 0, row, last_col, sub_title, sub_fmt)
        ws.set_row(row, 18)
        row += 1

    return row


def _header_fmt(workbook):
    return workbook.add_format(
        {
            "bold": True,
            "align": "center",
            "valign": "vcenter",
            "bg_color": "#D9E1F2",
            "border": 1,
            "text_wrap": True,
        }
    )


def _cell_fmt(workbook):
    return workbook.add_format({"align": "left", "valign": "vcenter", "border": 1, "text_wrap": True})


def _center_fmt(workbook):
    return workbook.add_format({"align": "center", "valign": "vcenter", "border": 1})


def export_sirt_main_seating_excel(
    room_allocations: Dict[str, pd.DataFrame],
    output_dir: Path,
    institute: str = "SAGAR INSTITUTE OF RESEARCH & TECHNOLOGY",
    department: str = "DEPARTMENT OF CSIT",
    exam_title: str = "I MID SEM EXAMINATION (JAN-JUN 2026)",
    default_branch: str = "CSIT",
    semester: str = "6th Sem",
) -> Path:
    """
    Produces a Main Seating sheet like Image 5:
    S.No | Branch | Section | Roll Numbers (comma-sep) | No. of Students | Class Room
    """
    target = output_dir / "SIRT_Main_Seating.xlsx"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build rows: group by room then section
    rows = []
    sno = 1
    for room_no, room_df in room_allocations.items():
        if room_df.empty:
            continue
        # Group by Section if available, else treat as one group
        if "Section" in room_df.columns:
            groups = room_df.groupby("Section", sort=True)
        else:
            groups = [("", room_df)]

        for section, grp in groups:
            rolls = grp["Roll Number"].tolist()
            branch = grp["Branch"].iloc[0] if "Branch" in grp.columns else default_branch
            roll_str = ", ".join(str(r) for r in rolls)
            rows.append(
                {
                    "S. No.": sno,
                    "BRANCH": branch,
                    "Section": str(section),
                    "Roll Number": roll_str,
                    "No. of Students Appeared": len(rolls),
                    "Class Room": room_no,
                }
            )
            sno += 1

    col_widths = [8, 10, 10, 80, 22, 14]
    col_headers = ["S. No.", "BRANCH", "Section", "Roll Number", "No. of Students Appeared", "Class Room"]
    num_cols = len(col_headers)

    with pd.ExcelWriter(target, engine="xlsxwriter") as writer:
        # Write a dummy df so the sheet is created
        pd.DataFrame().to_excel(writer, sheet_name="Main Seating", index=False)
        wb = writer.book
        ws = writer.sheets["Main Seating"]

        hdr_row = _write_sirt_header(
            ws, wb, num_cols,
            institute=institute,
            department=department,
            exam_title=exam_title,
            sub_title=f"{department.split()[2] if len(department.split()) > 2 else default_branch} {semester}",
        )

        hf = _header_fmt(wb)
        cf = _cell_fmt(wb)
        cnf = _center_fmt(wb)

        for c, (name, width) in enumerate(zip(col_headers, col_widths)):
            ws.write(hdr_row, c, name, hf)
            ws.set_column(c, c, width)
        ws.set_row(hdr_row, 30)

        for r_idx, row in enumerate(rows):
            data_row = hdr_row + 1 + r_idx
            ws.write(data_row, 0, row["S. No."], cnf)
            ws.write(data_row, 1, row["BRANCH"], cnf)
            ws.write(data_row, 2, row["Section"], cnf)
            ws.write(data_row, 3, row["Roll Number"], cf)
            ws.write(data_row, 4, row["No. of Students Appeared"], cnf)
            ws.write(data_row, 5, row["Class Room"], cnf)
            ws.set_row(data_row, 30)

    return target


def export_sirt_debarred_excel(
    not_eligible: pd.DataFrame,
    output_dir: Path,
    institute: str = "SAGAR INSTITUTE OF RESEARCH & TECHNOLOGY",
    department: str = "DEPARTMENT OF CSIT",
    exam_title: str = "I MID SEM EXAMINATION (JAN-JUN 2026)",
    semester: str = "6th Sem",
    attendance_cutoff: float = 40.0,
) -> Path:
    """
    Produces a Debarred List sheet matching Image 4:
    S.NO | Board EnrollNo | Student Name  (section-wise sub-headers if Section column present)
    """
    target = output_dir / "SIRT_Debarred_List.xlsx"
    output_dir.mkdir(parents=True, exist_ok=True)

    col_headers = ["S.NO", "Board EnrollNo", "Student Name", "Attendance %", "Section"]
    col_widths = [8, 20, 35, 14, 12]
    num_cols = len(col_headers)

    with pd.ExcelWriter(target, engine="xlsxwriter") as writer:
        pd.DataFrame().to_excel(writer, sheet_name="Debarred List", index=False)
        wb = writer.book
        ws = writer.sheets["Debarred List"]

        hdr_row = _write_sirt_header(
            ws, wb, num_cols,
            institute=institute,
            department=department,
            exam_title=exam_title,
            sub_title=f"Debarred List (Attendance < {attendance_cutoff:.0f}%)",
        )

        hf = _header_fmt(wb)
        cf = _cell_fmt(wb)
        cnf = _center_fmt(wb)

        for c, (name, width) in enumerate(zip(col_headers, col_widths)):
            ws.write(hdr_row, c, name, hf)
            ws.set_column(c, c, width)
        ws.set_row(hdr_row, 28)

        for r_idx, (_, row) in enumerate(not_eligible.iterrows()):
            data_row = hdr_row + 1 + r_idx
            ws.write(data_row, 0, r_idx + 1, cnf)
            ws.write(data_row, 1, str(row["Roll Number"]), cf)
            ws.write(data_row, 2, str(row["Name"]), cf)
            ws.write(data_row, 3, f"{float(row['Attendance Percentage']):.2f}%", cnf)
            ws.write(data_row, 4, str(row.get("Section", "")), cnf)
            ws.set_row(data_row, 22)

    return target


def export_sirt_attendance_sheets_excel(
    room_allocations: Dict[str, pd.DataFrame],
    output_dir: Path,
    institute: str = "SAGAR INSTITUTE OF RESEARCH & TECHNOLOGY",
    department: str = "DEPARTMENT OF CSIT",
    exam_title: str = "I MID SEM EXAMINATION (JAN-JUN 2026)",
) -> Path:
    """
    Produces attendance sheets (one per room) in the SIRT style matching Image 1.
    Columns: S.NO | Board EnrollNo | Student Name | Signature
    """
    target = output_dir / "SIRT_Attendance_Sheets.xlsx"
    output_dir.mkdir(parents=True, exist_ok=True)

    col_headers = ["S.NO", "Board EnrollNo", "Student Name", "Signature"]
    col_widths = [8, 20, 35, 30]
    num_cols = len(col_headers)

    def _safe(name: str) -> str:
        cleaned = "".join(ch for ch in name if ch not in r'\/*?:[]}')
        return (cleaned or "Sheet")[:31]

    with pd.ExcelWriter(target, engine="xlsxwriter") as writer:
        for room_no, room_df in room_allocations.items():
            sheet_name = _safe(f"Room {room_no}")
            pd.DataFrame().to_excel(writer, sheet_name=sheet_name, index=False)
            wb = writer.book
            ws = writer.sheets[sheet_name]

            hdr_row = _write_sirt_header(
                ws, wb, num_cols,
                institute=institute,
                department=department,
                exam_title=exam_title,
                sub_title=f"Class Room: {room_no}",
            )

            hf = _header_fmt(wb)
            cf = _cell_fmt(wb)
            cnf = _center_fmt(wb)
            sig_fmt = wb.add_format({"border": 1, "align": "center"})

            for c, (name, width) in enumerate(zip(col_headers, col_widths)):
                ws.write(hdr_row, c, name, hf)
                ws.set_column(c, c, width)
            ws.set_row(hdr_row, 28)

            if room_df.empty:
                ws.write(hdr_row + 1, 0, "No students allocated", cf)
            else:
                for r_idx, (_, row) in enumerate(room_df.iterrows()):
                    data_row = hdr_row + 1 + r_idx
                    ws.write(data_row, 0, r_idx + 1, cnf)
                    ws.write(data_row, 1, str(row["Roll Number"]), cf)
                    ws.write(data_row, 2, str(row["Name"]), cf)
                    ws.write(data_row, 3, "", sig_fmt)
                    ws.set_row(data_row, 22)

    return target
