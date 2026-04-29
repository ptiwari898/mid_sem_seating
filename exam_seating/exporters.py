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
        for room_no, room_df in room_allocations.items():
            sheet_name = _safe_sheet_name(f"Room_{room_no}")
            room_df.to_excel(writer, sheet_name=sheet_name, index=False)

            attendance_df = room_df[["Roll Number", "Name"]].copy()
            attendance_df["Signature"] = ""
            attendance_sheet_name = _safe_sheet_name(f"Att_{room_no}")
            attendance_df.to_excel(writer, sheet_name=attendance_sheet_name, index=False)

        not_eligible.to_excel(writer, sheet_name="Not_Eligible", index=False)

        summary_df = pd.DataFrame(
            {
                "Metric": [
                    "Total Students",
                    "Eligible Students",
                    "Not Eligible Students",
                    "Allocated Students",
                    "Unallocated Students",
                    "Room Count",
                    "Total Capacity",
                    "Effective Capacity",
                ],
                "Value": [
                    summary.total_students,
                    summary.eligible_students,
                    summary.not_eligible_students,
                    summary.allocated_students,
                    summary.unallocated_students,
                    summary.room_count,
                    summary.total_capacity,
                    summary.effective_capacity,
                ],
            }
        )
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

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
