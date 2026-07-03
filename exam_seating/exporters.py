from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable

import pandas as pd

from .models import SeatingSummary


def _safe_sheet_name(name: str) -> str:
    cleaned = "".join(ch for ch in name if ch not in ["\\", "/", "*", "?", ":", "[", "]"])
    return (cleaned or "Sheet")[:31]


def export_roomwise_text(room_allocations: Dict[str, pd.DataFrame], output_dir: Path) -> Path:
    target = output_dir / "room_wise_seating_plan.txt"
    lines: list[str] = []

    for room_no, room_df in room_allocations.items():
        lines.append(f"Room {room_no}")
        lines.append("-" * 72)
        lines.append(f"{'Seat':<8}{'Roll Number':<20}{'Name':<30}{'Attendance %':>12}")

        if room_df.empty:
            lines.append("No students allocated")
        else:
            for _, row in room_df.iterrows():
                lines.append(
                    f"{int(row['Seat Number']):<8}"
                    f"{str(row['Roll Number']):<20}"
                    f"{str(row['Name']):<30}"
                    f"{float(row['Attendance Percentage']):>12.2f}"
                )
        lines.append("")

    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def export_not_eligible_text(not_eligible: pd.DataFrame, output_dir: Path) -> Path:
    target = output_dir / "not_eligible_students.txt"
    lines: list[str] = ["Not Eligible Students", "-" * 72]
    lines.append(f"{'Roll Number':<20}{'Name':<30}{'Attendance %':>12}")

    if not not_eligible.empty:
        for _, row in not_eligible.iterrows():
            lines.append(
                f"{str(row['Roll Number']):<20}"
                f"{str(row['Name']):<30}"
                f"{float(row['Attendance Percentage']):>12.2f}"
            )

    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def export_attendance_text(room_allocations: Dict[str, pd.DataFrame], output_dir: Path) -> Path:
    target = output_dir / "attendance_sheet.txt"
    lines: list[str] = []

    for room_no, room_df in room_allocations.items():
        lines.append(f"Attendance Sheet - Room {room_no}")
        lines.append("-" * 72)
        lines.append(f"{'Roll Number':<20}{'Name':<30}{'Signature':<20}")

        if room_df.empty:
            lines.append("No students allocated")
        else:
            for _, row in room_df.iterrows():
                lines.append(f"{str(row['Roll Number']):<20}{str(row['Name']):<30}{'':<20}")
        lines.append("")

    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def export_summary_text(summary: SeatingSummary, output_dir: Path) -> Path:
    target = output_dir / "summary.txt"
    lines = [
        "Seating Arrangement Summary",
        "-" * 72,
        f"Total Students      : {summary.total_students}",
        f"Eligible Students   : {summary.eligible_students}",
        f"Not Eligible        : {summary.not_eligible_students}",
        f"Allocated Students  : {summary.allocated_students}",
        f"Unallocated Students: {summary.unallocated_students}",
        f"Room Count          : {summary.room_count}",
        f"Total Capacity      : {summary.total_capacity}",
        f"Effective Capacity  : {summary.effective_capacity}",
    ]
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def export_excel(
    room_allocations: Dict[str, pd.DataFrame],
    not_eligible: pd.DataFrame,
    summary: SeatingSummary,
    output_dir: Path,
) -> Path:
    target = output_dir / "exam_seating_output.xlsx"

    with pd.ExcelWriter(target, engine="xlsxwriter") as writer:
        wb = writer.book
        
        # Define formats without formulas
        header_fmt = wb.add_format({
            "bold": True,
            "bg_color": "#D9E1F2",
            "border": 1,
            "align": "center",
            "valign": "vcenter"
        })
        data_fmt = wb.add_format({
            "border": 1,
            "align": "left",
            "valign": "vcenter"
        })
        center_fmt = wb.add_format({
            "border": 1,
            "align": "center",
            "valign": "vcenter"
        })
        
        for room_no, room_df in room_allocations.items():
            sheet_name = _safe_sheet_name(f"Room_{room_no}")
            ws = wb.add_worksheet(sheet_name)
            
            # Write headers
            for col, col_name in enumerate(room_df.columns):
                ws.write(0, col, col_name, header_fmt)
            
            # Write data
            for row_idx, (_, row) in enumerate(room_df.iterrows(), start=1):
                for col_idx, col_name in enumerate(room_df.columns):
                    value = row[col_name]
                    # Convert NaN/None to empty string
                    if pd.isna(value):
                        value = ""
                    ws.write(row_idx, col_idx, value, data_fmt)

            # Create attendance sheet
            attendance_sheet_name = _safe_sheet_name(f"Att_{room_no}")
            att_ws = wb.add_worksheet(attendance_sheet_name)
            
            # Write headers for attendance sheet
            att_cols = ["Roll Number", "Name", "Signature"]
            for col, col_name in enumerate(att_cols):
                att_ws.write(0, col, col_name, header_fmt)
            
            # Write attendance data
            for row_idx, (_, row) in enumerate(room_df.iterrows(), start=1):
                att_ws.write(row_idx, 0, str(row["Roll Number"]), data_fmt)
                att_ws.write(row_idx, 1, str(row["Name"]), data_fmt)
                att_ws.write(row_idx, 2, "", data_fmt)  # Empty signature field

        # Write Not Eligible sheet
        not_elig_ws = wb.add_worksheet("Not_Eligible")
        not_elig_cols = not_eligible.columns.tolist()
        
        for col, col_name in enumerate(not_elig_cols):
            not_elig_ws.write(0, col, col_name, header_fmt)
        
        for row_idx, (_, row) in enumerate(not_eligible.iterrows(), start=1):
            for col_idx, col_name in enumerate(not_elig_cols):
                value = row[col_name]
                if pd.isna(value):
                    value = ""
                not_elig_ws.write(row_idx, col_idx, value, data_fmt)

        # Write Summary sheet
        summary_ws = wb.add_worksheet("Summary")
        summary_ws.write(0, 0, "Metric", header_fmt)
        summary_ws.write(0, 1, "Value", header_fmt)
        
        summary_data = [
            ("Total Students", summary.total_students),
            ("Eligible Students", summary.eligible_students),
            ("Not Eligible Students", summary.not_eligible_students),
            ("Allocated Students", summary.allocated_students),
            ("Unallocated Students", summary.unallocated_students),
            ("Room Count", summary.room_count),
            ("Total Capacity", summary.total_capacity),
            ("Effective Capacity", summary.effective_capacity),
        ]
        
        for row_idx, (metric, value) in enumerate(summary_data, start=1):
            summary_ws.write(row_idx, 0, metric, data_fmt)
            summary_ws.write(row_idx, 1, value, center_fmt)

    return target


def export_pdf(room_allocations: Dict[str, pd.DataFrame], output_dir: Path) -> Path | None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        return None

    target = output_dir / "room_wise_seating_plan.pdf"
    doc = SimpleDocTemplate(str(target), pagesize=A4)
    styles = getSampleStyleSheet()
    story: list[object] = []

    for room_no, room_df in room_allocations.items():
        story.append(Paragraph(f"Room {room_no}", styles["Heading3"]))
        data = [["Seat", "Roll Number", "Name", "Attendance %"]]

        if room_df.empty:
            data.append(["", "", "No students allocated", ""])
        else:
            for _, row in room_df.iterrows():
                data.append(
                    [
                        int(row["Seat Number"]),
                        str(row["Roll Number"]),
                        str(row["Name"]),
                        f"{float(row['Attendance Percentage']):.2f}",
                    ]
                )

        table = Table(data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 12))

    doc.build(story)
    return target


def collect_generated_files(paths: Iterable[Path | None]) -> list[str]:
    return [str(path) for path in paths if path is not None]
