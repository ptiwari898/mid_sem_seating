from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import streamlit as st

from exam_seating.io_utils import DataValidationError, load_students
from teacher_portal import auth
from teacher_portal import db
from teacher_portal.models import MarkEntry

_SUPPORTED_SUFFIXES = {".csv", ".xlsx", ".xls", ".db", ".sqlite", ".sqlite3"}
_REQUIRED_COLUMNS = {"Roll Number", "Name", "Attendance Percentage"}


def _find_latest_students_source() -> Path | None:
    base_dir = Path("web_runs")
    if not base_dir.exists():
        return None

    candidates = [
        path
        for path in base_dir.glob("*/input/students/*")
        if path.is_file() and path.suffix.lower() in _SUPPORTED_SUFFIXES
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _load_students_from_saved_path(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".db", ".sqlite", ".sqlite3", ".csv"}:
        return load_students(path)

    xl = pd.ExcelFile(path)
    sheet_frames: list[pd.DataFrame] = []
    skipped_sheets: list[str] = []
    for sheet in xl.sheet_names:
        sheet_df = pd.read_excel(xl, sheet_name=sheet)
        sheet_df.columns = [str(col).strip() for col in sheet_df.columns]
        if _REQUIRED_COLUMNS.issubset(sheet_df.columns):
            if "Section" not in sheet_df.columns:
                match = re.search(r"\b([A-Z])\s*$", sheet.strip())
                sheet_df["Section"] = match.group(1) if match else sheet.strip()
            if "Branch" not in sheet_df.columns:
                branch_part = re.sub(r"\s*[A-Z]\s*$", "", sheet.strip()).strip()
                sheet_df["Branch"] = branch_part if branch_part else "CSIT"
            sheet_frames.append(sheet_df)
        else:
            skipped_sheets.append(sheet)

    if not sheet_frames:
        raise DataValidationError(
            "None of the workbook sheets contain Roll Number, Name, and Attendance Percentage."
        )

    students_df = pd.concat(sheet_frames, ignore_index=True)
    if skipped_sheets:
        st.caption(f"Skipped sheets without required columns: {', '.join(skipped_sheets)}")
    return students_df


def _parse_class_name(class_name: str) -> tuple[str | None, str | None]:
    tokens = class_name.strip().split()
    section = None
    branch = None
    if tokens and len(tokens[-1]) == 1 and tokens[-1].isalpha():
        section = tokens[-1].upper()
        if len(tokens) >= 2:
            branch = tokens[-2].upper()
    elif tokens:
        branch = tokens[-1].upper()
    return branch, section


def _filter_students_for_class(students_df: pd.DataFrame, class_name: str) -> pd.DataFrame:
    filtered_df = students_df.copy()
    branch, section = _parse_class_name(class_name)

    if section and "Section" in filtered_df.columns:
        filtered_df = filtered_df[
            filtered_df["Section"].astype(str).str.strip().str.upper() == section
        ]

    if branch and "Branch" in filtered_df.columns:
        branch_mask = filtered_df["Branch"].astype(str).str.strip().str.upper().str.contains(branch, regex=False)
        branch_filtered = filtered_df[branch_mask]
        if not branch_filtered.empty:
            filtered_df = branch_filtered

    if filtered_df.empty:
        return filtered_df

    ordered_columns = [column for column in ["Roll Number", "Name", "Section", "Branch"] if column in filtered_df.columns]
    return (
        filtered_df[ordered_columns]
        .drop_duplicates(subset=["Roll Number"], keep="first")
        .sort_values(by=["Roll Number"], kind="mergesort")
        .reset_index(drop=True)
    )


def _build_editor_dataframe(students_df: pd.DataFrame, existing_marks_df: pd.DataFrame) -> pd.DataFrame:
    editor_df = students_df[["Roll Number", "Name"]].copy()
    editor_df["Mid-Sem Marks"] = pd.NA
    editor_df["Absent"] = False

    if existing_marks_df.empty:
        return editor_df

    marks_lookup = existing_marks_df.set_index("roll_no").to_dict("index")
    for index, row in editor_df.iterrows():
        roll_no = str(row["Roll Number"])
        existing = marks_lookup.get(roll_no)
        if existing is None:
            continue
        editor_df.at[index, "Mid-Sem Marks"] = existing["mid_sem_marks"]
        editor_df.at[index, "Absent"] = bool(existing["is_absent"])
    return editor_df


def render_tab_teacher_portal() -> None:
    st.header("Teacher Portal")

    if "teacher_portal_teacher_id" not in st.session_state:
        st.session_state["teacher_portal_teacher_id"] = None

    teacher_id = st.session_state["teacher_portal_teacher_id"]
    if teacher_id is None:
        code = st.text_input("Enter your login code", type="password", key="teacher_portal_code")
        if st.button("Login", key="teacher_portal_login"):
            matched_teacher = auth.verify_code(code.strip(), db.get_all_teachers_with_hashes())
            if matched_teacher is None:
                st.error("Invalid code.")
            else:
                st.session_state["teacher_portal_teacher_id"] = matched_teacher
                st.rerun()
        return

    teacher = db.get_teacher_by_id(int(teacher_id))
    if teacher is None:
        st.session_state["teacher_portal_teacher_id"] = None
        st.error("Teacher account not found.")
        return

    top_left, top_right = st.columns([5, 1])
    top_left.success(f"Hello, {teacher.name}")
    if top_right.button("Logout", key="teacher_portal_logout"):
        st.session_state["teacher_portal_teacher_id"] = None
        st.rerun()

    assignments = db.get_assignments_for_teacher(teacher.id)
    if not assignments:
        st.info("No assignments are assigned to you yet.")
        return

    assignment_options = {
        f"{assignment.exam_session} | {assignment.class_name} | {assignment.subject} ({assignment.subject_code})": assignment
        for assignment in assignments
    }
    selected_label = st.selectbox("Your Assignments", list(assignment_options.keys()), key="teacher_portal_assignment")
    assignment = assignment_options[selected_label]

    latest_source = _find_latest_students_source()
    if latest_source is None:
        st.warning("No student source found. Upload students in the Seating Plan tab first.")
        return

    try:
        students_df = _load_students_from_saved_path(latest_source)
    except Exception as exc:
        st.error(f"Could not load students from {latest_source.name}: {exc}")
        return

    class_students_df = _filter_students_for_class(students_df, assignment.class_name)
    if class_students_df.empty:
        st.warning(
            "No students matched this class in the latest uploaded student data. "
            "Check the class name or upload a file with matching Section/Branch columns."
        )
        return

    existing_marks_df = db.get_marks_for_assignment(assignment.id)
    editor_df = _build_editor_dataframe(class_students_df, existing_marks_df)

    st.caption(f"Student source: {latest_source.name}")
    st.caption(
        f"Submitting mid-sem marks for {assignment.subject} ({assignment.subject_code}) "
        f"in {assignment.exam_session}."
    )

    edited_df = st.data_editor(
        editor_df,
        use_container_width=True,
        hide_index=True,
        disabled=["Roll Number", "Name"],
        column_config={
            "Mid-Sem Marks": st.column_config.NumberColumn(
                "Mid-Sem Marks (/30)",
                min_value=0.0,
                max_value=float(assignment.max_marks),
                step=0.5,
            ),
            "Absent": st.column_config.CheckboxColumn("Absent"),
        },
        key=f"teacher_marks_editor_{assignment.id}",
    )

    if st.button("Submit Marks", key=f"teacher_submit_marks_{assignment.id}"):
        entries: list[MarkEntry] = []
        for _, row in edited_df.iterrows():
            is_absent = bool(row["Absent"])
            raw_marks = row["Mid-Sem Marks"]
            marks_value = None if pd.isna(raw_marks) else float(raw_marks)
            entries.append(
                MarkEntry(
                    assignment_id=assignment.id,
                    roll_no=str(row["Roll Number"]).strip(),
                    student_name=str(row["Name"]).strip(),
                    mid_sem_marks=0.0 if is_absent else marks_value,
                    is_absent=is_absent,
                )
            )

        try:
            db.submit_marks(entries)
            st.success(
                f"Marks submitted for {assignment.subject} - {assignment.exam_session}."
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Could not submit marks: {exc}")
