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
        {"bold": True, "align": "center", "valign": "vcenter", "font_size": 14, "border": 1}
    )
    sub_fmt = workbook.add_format(
        {"bold": True, "align": "center", "valign": "vcenter", "font_size": 14, "border": 1}
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
            "font_size": 14,
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
    Produces section-wise debarred sheets — one sheet per section, same
    header format as the attendance sheets.
    Columns: S.NO | Board EnrollNo | Student Name | Attendance %
    """
    target = output_dir / "SIRT_Debarred_List.xlsx"
    output_dir.mkdir(parents=True, exist_ok=True)

    not_eligible = not_eligible.sort_values(by=["Roll Number"], kind="mergesort").reset_index(drop=True)

    has_section = "Section" in not_eligible.columns
    has_branch  = "Branch"  in not_eligible.columns

    # Build (sheet_name, subtitle, group_df) list — same logic as attendance
    groups: list[tuple[str, str, pd.DataFrame]] = []
    if has_branch and has_section:
        for (branch, section), grp in not_eligible.groupby(["Branch", "Section"], sort=True):
            sheet_name = f"{branch}-{section}"
            subtitle   = f"{branch} {semester} - {branch}-{section}"
            groups.append((sheet_name, subtitle, grp.reset_index(drop=True)))
    elif has_section:
        for section, grp in not_eligible.groupby("Section", sort=True):
            sheet_name = f"Section-{section}"
            subtitle   = f"{semester} - Section {section}"
            groups.append((sheet_name, subtitle, grp.reset_index(drop=True)))
    else:
        groups.append(("Debarred", f"Debarred List (Attendance < {attendance_cutoff:.0f}%)", not_eligible))

    col_headers = ["S.NO", "Board EnrollNo", "Student Name", "Attendance %"]
    col_widths  = [8, 20, 35, 16]
    num_cols    = len(col_headers)

    def _safe(name: str) -> str:
        cleaned = "".join(ch for ch in name if ch not in r'\/*?:[]}')
        return (cleaned or "Sheet")[:31]

    with pd.ExcelWriter(target, engine="xlsxwriter") as writer:
        for sheet_key, subtitle, grp_df in groups:
            sheet_name = _safe(sheet_key)
            pd.DataFrame().to_excel(writer, sheet_name=sheet_name, index=False)
            wb = writer.book
            ws = writer.sheets[sheet_name]

            hdr_row = _write_sirt_header(
                ws, wb, num_cols,
                institute=institute,
                department=department,
                exam_title=exam_title,
                sub_title=f"{subtitle}  |  Debarred (Attendance < {attendance_cutoff:.0f}%)",
            )

            hf  = _header_fmt(wb)
            cf  = _cell_fmt(wb)
            cnf = _center_fmt(wb)

            for c, (name, width) in enumerate(zip(col_headers, col_widths)):
                ws.write(hdr_row, c, name, hf)
                ws.set_column(c, c, width)
            ws.set_row(hdr_row, 28)

            for r_idx, (_, row) in enumerate(grp_df.iterrows()):
                data_row = hdr_row + 1 + r_idx
                ws.write(data_row, 0, r_idx + 1, cnf)
                ws.write(data_row, 1, str(row["Roll Number"]), cf)
                ws.write(data_row, 2, str(row["Name"]), cf)
                ws.write(data_row, 3, f"{float(row['Attendance Percentage']):.2f}%", cnf)
                ws.set_row(data_row, 25)

    return target


def export_sirt_attendance_sheets_excel(
    students_df: pd.DataFrame,
    output_dir: Path,
    subjects: list | None = None,
    institute: str = "SAGAR INSTITUTE OF RESEARCH & TECHNOLOGY",
    department: str = "DEPARTMENT OF CSIT",
    exam_title: str = "I MID SEM EXAMINATION (JAN-JUN 2026)",
    semester: str = "6th Sem",
) -> Path:
    """
    Produces section-wise attendance sheets with a two-row column header:
      Row 1: S.NO | Board EnrollNo | Student Name | <date1> | <date2> | ...
      Row 2: (merged)| (merged)    | (merged)     | <subj1> | <subj2> | ...

    students_df : eligible students DataFrame with Branch and Section columns.
    subjects    : list of {"subject": str, "date": str} dicts (one per exam).
    """
    target = output_dir / "SIRT_Attendance_Sheets.xlsx"
    output_dir.mkdir(parents=True, exist_ok=True)

    if subjects is None:
        subjects = []

    students_df = students_df.sort_values(by=["Roll Number"], kind="mergesort").reset_index(drop=True)

    has_section = "Section" in students_df.columns
    has_branch  = "Branch"  in students_df.columns

    # Build (sheet_name, subtitle, group_df) list
    groups: list[tuple[str, str, pd.DataFrame]] = []
    if has_branch and has_section:
        for (branch, section), grp in students_df.groupby(["Branch", "Section"], sort=True):
            sheet_name = f"{branch}-{section}"
            subtitle   = f"{branch} {semester} - {branch}-{section}"
            groups.append((sheet_name, subtitle, grp.reset_index(drop=True)))
    elif has_section:
        for section, grp in students_df.groupby("Section", sort=True):
            sheet_name = f"Section-{section}"
            subtitle   = f"{semester} - Section {section}"
            groups.append((sheet_name, subtitle, grp.reset_index(drop=True)))
    else:
        groups.append(("All Students", semester, students_df.reset_index(drop=True)))

    num_fixed = 3   # S.NO, Board EnrollNo, Student Name
    num_subj  = len(subjects)
    total_cols = num_fixed + max(num_subj, 1)

    def _safe(name: str) -> str:
        cleaned = "".join(ch for ch in name if ch not in r'\/*?:[]}')
        return (cleaned or "Sheet")[:31]

    with pd.ExcelWriter(target, engine="xlsxwriter") as writer:
        for sheet_key, subtitle, grp_df in groups:
            sheet_name = _safe(sheet_key)
            pd.DataFrame().to_excel(writer, sheet_name=sheet_name, index=False)
            wb = writer.book
            ws = writer.sheets[sheet_name]

            hdr_row = _write_sirt_header(
                ws, wb, total_cols,
                institute=institute,
                department=department,
                exam_title=exam_title,
                sub_title=subtitle,
            )

            hf  = _header_fmt(wb)
            cf  = _cell_fmt(wb)
            cnf = _center_fmt(wb)

            date_row = hdr_row
            subj_row = hdr_row + 1

            # First 3 columns span both header rows
            ws.merge_range(date_row, 0, subj_row, 0, "S.NO",           hf)
            ws.merge_range(date_row, 1, subj_row, 1, "Board EnrollNo", hf)
            ws.merge_range(date_row, 2, subj_row, 2, "Student Name",   hf)
            ws.set_column(0, 0, 8)
            ws.set_column(1, 1, 20)
            ws.set_column(2, 2, 35)

            if subjects:
                for i, subj in enumerate(subjects):
                    col = num_fixed + i
                    ws.write(date_row, col, subj.get("date", ""),    hf)
                    ws.write(subj_row, col, subj.get("subject", ""), hf)
                    ws.set_column(col, col, 17)
            else:
                # Fallback: single Signature column
                ws.merge_range(date_row, 3, subj_row, 3, "Signature", hf)
                ws.set_column(3, 3, 30)

            ws.set_row(date_row, 28)
            ws.set_row(subj_row, 28)

            data_start = hdr_row + 2
            for r_idx, (_, row) in enumerate(grp_df.iterrows()):
                data_row = data_start + r_idx
                ws.write(data_row, 0, r_idx + 1,            cnf)
                ws.write(data_row, 1, str(row["Roll Number"]), cf)
                ws.write(data_row, 2, str(row["Name"]),       cf)
                for i in range(max(num_subj, 1)):
                    ws.write(data_row, num_fixed + i, "", cnf)
                ws.set_row(data_row, 25)
    return target
