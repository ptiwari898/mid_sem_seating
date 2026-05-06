"""
SIRT-branded Excel exporter.

Produces formatted workbooks matching the institute's style:
  - Merged header rows with institute/department/exam title
  - Section-wise attendance sheets with date/subject column headers
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
    timetable: list | None = None,
) -> Path:
    """
    Produces attendance sheets (one per room) in the SIRT style.
    If timetable is provided, columns after Student Name are:
      date row (merged across subjects on same date) + subject row.
    Otherwise falls back to a single Signature column.
    """
    from collections import OrderedDict as _OD

    target = output_dir / "SIRT_Attendance_Sheets.xlsx"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not timetable:
        timetable = []

    FIXED = 3  # S.NO, Board EnrollNo, Student Name
    num_subjects = len(timetable)
    total_cols = FIXED + max(num_subjects, 1)

    # Group subjects by date for merged date header row
    date_groups: _OD = _OD()
    for i, entry in enumerate(timetable):
        d = entry.get("date", "")
        date_groups.setdefault(d, []).append(i)

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
                ws, wb, total_cols,
                institute=institute,
                department=department,
                exam_title=exam_title,
                sub_title=f"Class Room: {room_no}",
            )

            hf = _header_fmt(wb)
            hf_date = wb.add_format({
                "bold": True, "align": "center", "valign": "vcenter",
                "bg_color": "#BDD7EE", "border": 1, "text_wrap": True,
            })
            cf  = _cell_fmt(wb)
            cnf = _center_fmt(wb)
            sig_fmt = wb.add_format({"border": 1, "align": "center"})

            if not timetable:
                # ── Fallback: single header row with Signature column ─────────
                for c, (name, width) in enumerate(zip(
                    ["S.NO", "Board EnrollNo", "Student Name", "Signature"],
                    [8, 20, 35, 30],
                )):
                    ws.write(hdr_row, c, name, hf)
                    ws.set_column(c, c, width)
                ws.set_row(hdr_row, 28)
                data_start = hdr_row + 1

                if room_df.empty:
                    ws.write(data_start, 0, "No students allocated", cf)
                else:
                    for r_idx, (_, row) in enumerate(room_df.iterrows()):
                        dr = data_start + r_idx
                        ws.write(dr, 0, r_idx + 1, cnf)
                        ws.write(dr, 1, str(row["Roll Number"]), cf)
                        ws.write(dr, 2, str(row["Name"]), cf)
                        ws.write(dr, 3, "", sig_fmt)
                        ws.set_row(dr, 22)
            else:
                # ── Two-row header: date row + subject row ────────────────────
                date_row = hdr_row
                subj_row = hdr_row + 1

                # Fixed columns merged across both header rows
                ws.merge_range(date_row, 0, subj_row, 0, "S.NO", hf)
                ws.merge_range(date_row, 1, subj_row, 1, "Board EnrollNo", hf)
                ws.merge_range(date_row, 2, subj_row, 2, "Student Name", hf)
                ws.set_column(0, 0, 8)
                ws.set_column(1, 1, 22)
                ws.set_column(2, 2, 35)
                ws.set_row(date_row, 28)
                ws.set_row(subj_row, 28)

                # Date row: merge cells that share the same date
                for date_val, indices in date_groups.items():
                    start_col = FIXED + indices[0]
                    end_col   = FIXED + indices[-1]
                    if start_col == end_col:
                        ws.write(date_row, start_col, date_val, hf_date)
                    else:
                        ws.merge_range(date_row, start_col, date_row, end_col, date_val, hf_date)

                # Subject row
                for i, entry in enumerate(timetable):
                    col = FIXED + i
                    ws.write(subj_row, col, entry.get("subject", ""), hf)
                    ws.set_column(col, col, 18)

                data_start = subj_row + 1

                if room_df.empty:
                    ws.write(data_start, 0, "No students allocated", cf)
                else:
                    for r_idx, (_, row) in enumerate(room_df.iterrows()):
                        dr = data_start + r_idx
                        ws.write(dr, 0, r_idx + 1, cnf)
                        ws.write(dr, 1, str(row["Roll Number"]), cf)
                        ws.write(dr, 2, str(row["Name"]), cf)
                        for i in range(num_subjects):
                            ws.write(dr, FIXED + i, "", sig_fmt)
                        ws.set_row(dr, 22)

    return target


def export_sirt_section_attendance_excel(
    room_allocations: Dict[str, pd.DataFrame],
    output_dir: Path,
    timetable: list,
    institute: str = "SAGAR INSTITUTE OF RESEARCH & TECHNOLOGY",
    department: str = "DEPARTMENT OF CSIT",
    exam_title: str = "I MID SEM EXAMINATION (JAN-JUN 2026)",
    semester: str = "6th Sem",
    default_branch: str = "CSIT",
) -> Path:
    """
    Produces section-wise attendance sheets matching the SIRT format shown in the image:
      - Merged institute/dept/exam title headers
      - Two-row column header: dates merged across subjects in top row, subject codes in bottom row
      - Fixed columns: S.NO | Board EnrollNo | Student Name (merged vertically across both header rows)
      - One sheet per section

    timetable: list of dicts, e.g.
        [{"subject": "CSIT-601 SE", "date": "06-Apr-26"}, ...]
    """
    from collections import OrderedDict as _OD

    target = output_dir / "SIRT_Section_Attendance.xlsx"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect all students, keeping one row per roll number
    all_frames = [df for df in room_allocations.values() if not df.empty]
    if not all_frames:
        return target

    all_students = pd.concat(all_frames, ignore_index=True)
    all_students = all_students.drop_duplicates(subset=["Roll Number"])
    all_students["Roll Number"] = all_students["Roll Number"].astype(str).str.strip()

    FIXED = 3  # S.NO, Board EnrollNo, Student Name
    num_subjects = len(timetable)
    total_cols = FIXED + max(num_subjects, 1)

    # Group subjects by date (preserving insertion order)
    date_groups: _OD = _OD()
    for i, entry in enumerate(timetable):
        d = entry.get("date", "")
        date_groups.setdefault(d, []).append(i)

    def _safe_sheet(name: str) -> str:
        cleaned = "".join(ch for ch in name if ch not in r'\/*?:[]')
        return (cleaned or "Sheet")[:31]

    with pd.ExcelWriter(target, engine="xlsxwriter") as writer:
        pd.DataFrame().to_excel(writer, sheet_name="_tmp", index=False)
        wb = writer.book

        hf = wb.add_format({
            "bold": True, "align": "center", "valign": "vcenter",
            "bg_color": "#D9E1F2", "border": 1, "text_wrap": True,
        })
        hf_date = wb.add_format({
            "bold": True, "align": "center", "valign": "vcenter",
            "bg_color": "#BDD7EE", "border": 1, "text_wrap": True,
        })
        cf = _cell_fmt(wb)
        cnf = _center_fmt(wb)
        sig_fmt = wb.add_format({"border": 1})

        # Determine sections
        if "Section" in all_students.columns:
            section_groups = list(all_students.groupby("Section", sort=True))
        else:
            section_groups = [("", all_students)]

        for section_name, section_df in section_groups:
            branch = (
                section_df["Branch"].iloc[0]
                if "Branch" in section_df.columns and not section_df["Branch"].isna().all()
                else default_branch
            )
            sub_title = (
                f"{branch} {semester} - {section_name}"
                if section_name
                else f"{branch} {semester}"
            )
            sheet_name = _safe_sheet(
                f"Sec {section_name}" if section_name else "All Students"
            )

            pd.DataFrame().to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]

            hdr_row = _write_sirt_header(
                ws, wb, total_cols,
                institute=institute,
                department=department,
                exam_title=exam_title,
                sub_title=sub_title,
            )

            date_row = hdr_row
            subj_row = hdr_row + 1

            # ── Fixed column headers (S.NO, Board EnrollNo, Student Name)
            # merged vertically across both header rows
            ws.merge_range(date_row, 0, subj_row, 0, "S.NO", hf)
            ws.merge_range(date_row, 1, subj_row, 1, "Board EnrollNo", hf)
            ws.merge_range(date_row, 2, subj_row, 2, "Student Name", hf)
            ws.set_column(0, 0, 8)
            ws.set_column(1, 1, 22)
            ws.set_column(2, 2, 35)
            ws.set_row(date_row, 28)
            ws.set_row(subj_row, 28)

            if not timetable:
                # Fallback: single Signature column
                ws.merge_range(date_row, 3, subj_row, 3, "Signature", hf)
                ws.set_column(3, 3, 30)
            else:
                # Date row: merge across subjects sharing the same date
                for date_val, indices in date_groups.items():
                    start_col = FIXED + indices[0]
                    end_col = FIXED + indices[-1]
                    if start_col == end_col:
                        ws.write(date_row, start_col, date_val, hf_date)
                    else:
                        ws.merge_range(date_row, start_col, date_row, end_col, date_val, hf_date)

                # Subject row
                for i, entry in enumerate(timetable):
                    col = FIXED + i
                    ws.write(subj_row, col, entry.get("subject", ""), hf)
                    ws.set_column(col, col, 18)

            # ── Data rows
            section_df = section_df.sort_values("Roll Number").reset_index(drop=True)
            for r_idx, (_, row) in enumerate(section_df.iterrows()):
                data_row = subj_row + 1 + r_idx
                ws.write(data_row, 0, r_idx + 1, cnf)
                ws.write(data_row, 1, str(row["Roll Number"]), cf)
                ws.write(data_row, 2, str(row["Name"]), cf)
                for j in range(max(num_subjects, 1)):
                    ws.write(data_row, FIXED + j, "", sig_fmt)
                ws.set_row(data_row, 22)

        # Hide the placeholder sheet
        try:
            writer.sheets["_tmp"].hide()
        except Exception:
            pass

    return target

