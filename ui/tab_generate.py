from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from exam_seating.io_utils import DataValidationError
from exam_seating.service import SeatingConfig, run_seating_system
from exam_seating.sirt_exporters import (
    export_sirt_attendance_sheets_excel,
    export_sirt_debarred_excel,
    export_sirt_main_seating_excel,
)
from ui.runtime import create_new_run_dirs, load_rooms_from_upload, load_students_from_upload
from ui.templates import XLSX_MIME, make_students_template
from utils.workbook import ZIP_MIME, bundle_reports_zip


def render_tab_generate(info: dict) -> None:
    st.header("Step 2 - Generate Seating Plan")

    if "rooms_with_info" not in st.session_state:
        st.session_state["rooms_with_info"] = []
    if "exam_subjects" not in st.session_state:
        st.session_state["exam_subjects"] = []
    if "editing_subject_index" not in st.session_state:
        st.session_state["editing_subject_index"] = None
    if "editing_room_index" not in st.session_state:
        st.session_state["editing_room_index"] = None

    st.subheader("1. Upload Students")
    st.caption("Required columns: Roll Number, Name, Attendance Percentage")

    col_tmpl, _ = st.columns([1, 3])
    col_tmpl.download_button(
        "Download template",
        data=make_students_template(),
        file_name="students_template.xlsx",
        mime=XLSX_MIME,
        key="tmpl_students_gen",
    )

    students_sqlite_table = st.text_input(
        "Students SQLite table name",
        value="students",
        help="Used only for .db/.sqlite/.sqlite3 uploads.",
    )
    students_file = st.file_uploader(
        "Upload students (.xlsx/.xls/.csv/.db/.sqlite/.sqlite3)",
        type=["xlsx", "xls", "csv", "db", "sqlite", "sqlite3"],
        key="students_upload_gen",
    )

    students_df = pd.DataFrame()
    if students_file is not None:
        try:
            students_df = load_students_from_upload(students_file, students_sqlite_table)
            if not students_df.empty:
                students_df.columns = [c.strip() for c in students_df.columns]

            required = {"Roll Number", "Name", "Attendance Percentage"}
            missing = required - set(students_df.columns)
            if not students_df.empty and missing:
                st.error(f"Missing columns in uploaded file: {', '.join(missing)}")
                students_df = pd.DataFrame()
            elif not students_df.empty:
                attendance_numeric = pd.to_numeric(students_df["Attendance Percentage"], errors="coerce")
                invalid_attendance_count = int(attendance_numeric.isna().sum())
                if invalid_attendance_count > 0:
                    st.warning(
                        f"{invalid_attendance_count} students had unparseable attendance and were excluded."
                    )
                students_df = students_df[attendance_numeric.notna()].copy()
                students_df["Attendance Percentage"] = attendance_numeric[attendance_numeric.notna()].astype(float)
                students_df = students_df.drop_duplicates(subset=["Roll Number"], keep="first")
                students_df = students_df.sort_values(by=["Roll Number"], kind="mergesort").reset_index(drop=True)

                sections = students_df["Section"].nunique() if "Section" in students_df.columns else None
                info_msg = f"Loaded {len(students_df)} students"
                if sections:
                    info_msg += f" across {sections} section(s)"
                st.success(info_msg)
        except Exception as exc:
            st.error(f"Could not read students file: {exc}")

    st.divider()
    st.subheader("2. Rooms")

    rooms_method = st.radio(
        "Room input method",
        options=["Add manually", "Upload rooms file"],
        horizontal=True,
    )

    uploaded_rooms_df = pd.DataFrame()
    if rooms_method == "Upload rooms file":
        rooms_sqlite_table = st.text_input(
            "Rooms SQLite table name",
            value="rooms",
            help="Used only for .db/.sqlite/.sqlite3 uploads.",
        )
        rooms_file = st.file_uploader(
            "Upload rooms (.xlsx/.xls/.csv/.db/.sqlite/.sqlite3)",
            type=["xlsx", "xls", "csv", "db", "sqlite", "sqlite3"],
            key="rooms_upload_gen",
        )
        if rooms_file is not None:
            try:
                uploaded_rooms_df = load_rooms_from_upload(rooms_file, rooms_sqlite_table)
                uploaded_rooms_df["Room Number"] = uploaded_rooms_df["Room Number"].astype(str).str.strip()
                uploaded_rooms_df["Capacity"] = pd.to_numeric(uploaded_rooms_df["Capacity"], errors="coerce")
                uploaded_rooms_df = uploaded_rooms_df.dropna(subset=["Capacity"])
                uploaded_rooms_df["Capacity"] = uploaded_rooms_df["Capacity"].astype(int)
                st.success(f"Loaded {len(uploaded_rooms_df)} rooms")
                st.dataframe(uploaded_rooms_df, use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error(f"Could not read rooms file: {exc}")

    if rooms_method == "Add manually":
        with st.form("add_room_form", clear_on_submit=True):
            c1, c2, c_btn = st.columns([2, 1.5, 0.8])
            room_no_in = c1.text_input("Room Number", placeholder="F-307")
            capacity_in = c2.number_input("Capacity", 1, 500, 40, 1)
            add_room = c_btn.form_submit_button("Add")

            if add_room:
                if not room_no_in:
                    st.error("Room Number is required.")
                else:
                    existing = {r["Room Number"] for r in st.session_state["rooms_with_info"]}
                    if room_no_in in existing:
                        st.error(f"Room {room_no_in} already added.")
                    else:
                        st.session_state["rooms_with_info"].append(
                            {"Room Number": room_no_in, "Capacity": int(capacity_in)}
                        )

        if st.session_state["rooms_with_info"]:
            rooms_display = pd.DataFrame(st.session_state["rooms_with_info"])
            st.dataframe(rooms_display, use_container_width=True, hide_index=True)

            st.markdown("Room Row Actions")
            for idx, row in enumerate(st.session_state["rooms_with_info"]):
                r1, r2, r3, r4, r5 = st.columns([0.5, 3, 2, 1, 1])
                r1.write(str(idx + 1))
                r2.write(str(row.get("Room Number", "")))
                r3.write(str(row.get("Capacity", "")))

                if r4.button("Edit", key=f"edit_room_{idx}"):
                    st.session_state["editing_room_index"] = idx
                    st.rerun()
                if r5.button("Delete", key=f"delete_room_{idx}"):
                    st.session_state["rooms_with_info"].pop(idx)
                    if st.session_state["editing_room_index"] == idx:
                        st.session_state["editing_room_index"] = None
                    st.rerun()

            edit_room_idx = st.session_state.get("editing_room_index")
            if edit_room_idx is not None and 0 <= edit_room_idx < len(st.session_state["rooms_with_info"]):
                st.markdown("Edit Selected Room")
                current_room = st.session_state["rooms_with_info"][edit_room_idx]

                with st.form("edit_room_form"):
                    er1, er2, er3, er4 = st.columns([2, 1.5, 1, 1])
                    edit_room_no = er1.text_input(
                        "Room Number",
                        value=str(current_room.get("Room Number", "")),
                        key="edit_room_number",
                    )
                    edit_capacity = er2.number_input(
                        "Capacity",
                        min_value=1,
                        max_value=500,
                        value=int(current_room.get("Capacity", 40)),
                        step=1,
                        key="edit_room_capacity",
                    )
                    save_room = er3.form_submit_button("Save")
                    cancel_room = er4.form_submit_button("Cancel")

                    if save_room:
                        if not edit_room_no.strip():
                            st.error("Room Number is required.")
                        else:
                            duplicate = any(
                                i != edit_room_idx and r.get("Room Number") == edit_room_no.strip()
                                for i, r in enumerate(st.session_state["rooms_with_info"])
                            )
                            if duplicate:
                                st.error(f"Room {edit_room_no.strip()} already exists.")
                            else:
                                st.session_state["rooms_with_info"][edit_room_idx] = {
                                    "Room Number": edit_room_no.strip(),
                                    "Capacity": int(edit_capacity),
                                }
                                st.session_state["editing_room_index"] = None
                                st.rerun()

                    if cancel_room:
                        st.session_state["editing_room_index"] = None
                        st.rerun()

            if st.button("Clear all rooms", key="clear_rooms"):
                st.session_state["rooms_with_info"] = []
                st.session_state["editing_room_index"] = None
                st.rerun()

    st.divider()
    st.subheader("3. Exam Timetable (Subject-wise and Date-wise)")

    with st.form("add_subject_form", clear_on_submit=True):
        s1, s2, s_btn = st.columns([2, 1.5, 0.8])
        subj_in = s1.text_input("Subject", placeholder="CSIT-401 (M-III)")
        exam_date = s2.date_input("Exam Date", key="subject_date_input")
        add_subject = s_btn.form_submit_button("Add")

        if add_subject:
            if not subj_in.strip():
                st.error("Subject is required.")
            else:
                st.session_state["exam_subjects"].append(
                    {
                        "subject": subj_in.strip(),
                        "date": exam_date.strftime("%d-%b-%y"),
                    }
                )

    if st.session_state["exam_subjects"]:
        st.caption("These columns will be added to attendance sheets.")
        subject_df = pd.DataFrame(st.session_state["exam_subjects"])
        st.dataframe(subject_df, use_container_width=True, hide_index=True)

        st.markdown("Row Actions")
        for idx, row in enumerate(st.session_state["exam_subjects"]):
            c1, c2, c3, c4, c5 = st.columns([0.5, 3, 2, 1, 1])
            c1.write(str(idx + 1))
            c2.write(row.get("subject", ""))
            c3.write(row.get("date", ""))

            if c4.button("Edit", key=f"edit_subject_{idx}"):
                st.session_state["editing_subject_index"] = idx
                st.rerun()
            if c5.button("Delete", key=f"delete_subject_{idx}"):
                st.session_state["exam_subjects"].pop(idx)
                if st.session_state["editing_subject_index"] == idx:
                    st.session_state["editing_subject_index"] = None
                st.rerun()

        edit_idx = st.session_state.get("editing_subject_index")
        if edit_idx is not None and 0 <= edit_idx < len(st.session_state["exam_subjects"]):
            st.markdown("Edit Selected Row")
            current = st.session_state["exam_subjects"][edit_idx]
            try:
                current_date = datetime.strptime(current.get("date", "01-Jan-26"), "%d-%b-%y").date()
            except ValueError:
                current_date = datetime.today().date()

            with st.form("edit_subject_form"):
                e1, e2, e3, e4 = st.columns([2, 1.5, 1, 1])
                edit_subject = e1.text_input("Subject", value=current.get("subject", ""), key="edit_subject_name")
                edit_date = e2.date_input("Exam Date", value=current_date, key="edit_subject_date")
                save_edit = e3.form_submit_button("Save")
                cancel_edit = e4.form_submit_button("Cancel")

                if save_edit:
                    if not edit_subject.strip():
                        st.error("Subject is required.")
                    else:
                        st.session_state["exam_subjects"][edit_idx] = {
                            "subject": edit_subject.strip(),
                            "date": edit_date.strftime("%d-%b-%y"),
                        }
                        st.session_state["editing_subject_index"] = None
                        st.rerun()

                if cancel_edit:
                    st.session_state["editing_subject_index"] = None
                    st.rerun()

        if st.button("Clear timetable", key="clear_subjects"):
            st.session_state["exam_subjects"] = []
            st.session_state["editing_subject_index"] = None
            st.rerun()

    st.divider()
    st.subheader("4. Options")
    o1, o2, o3, o4 = st.columns(4)
    attendance_cutoff = o1.number_input("Attendance cutoff (%)", 0.0, 100.0, 40.0, 1.0)
    shuffle = o2.checkbox("Shuffle students")
    seed = o3.number_input("Seed", 0, 99999, 42, 1)
    alt_seats = o4.checkbox("Alternate seats")

    if not students_df.empty:
        eligible_count = int((pd.to_numeric(students_df["Attendance Percentage"], errors="coerce") >= attendance_cutoff).sum())
        active_rooms = (
            uploaded_rooms_df.to_dict("records")
            if rooms_method == "Upload rooms file" and not uploaded_rooms_df.empty
            else st.session_state["rooms_with_info"]
        )
        total_capacity = sum(int(r["Capacity"]) for r in active_rooms)

        sm1, sm2, sm3 = st.columns(3)
        sm1.metric("Eligible", eligible_count)
        sm2.metric("Debarred", len(students_df) - eligible_count)
        sm3.metric("Total Room Capacity", total_capacity if total_capacity else "-")

        rooms_ok = bool(active_rooms) and total_capacity >= eligible_count
    else:
        rooms_ok = False

    st.divider()
    if not st.button("Generate Seating Plan", type="primary", use_container_width=True, disabled=not rooms_ok):
        return

    if students_df.empty:
        st.error("Upload a valid students file first.")
        return

    active_rooms = (
        uploaded_rooms_df.to_dict("records")
        if rooms_method == "Upload rooms file" and not uploaded_rooms_df.empty
        else st.session_state["rooms_with_info"]
    )
    if not active_rooms:
        st.error("Add at least one room before generating.")
        return

    rooms_df = pd.DataFrame([{"Room Number": r["Room Number"], "Capacity": r["Capacity"]} for r in active_rooms])

    _, input_dir, output_dir = create_new_run_dirs()

    try:
        student_path = input_dir / "students.xlsx"
        room_path = input_dir / "rooms.xlsx"
        students_df.to_excel(student_path, index=False)
        rooms_df.to_excel(room_path, index=False)

        config = SeatingConfig(
            students_file=str(student_path),
            rooms_file=str(room_path),
            attendance_cutoff=float(attendance_cutoff),
            output_dir=str(output_dir),
            shuffle_students=shuffle,
            random_seed=int(seed) if shuffle else None,
            alternate_seats=alt_seats,
            export_pdf_file=False,
        )
        result = run_seating_system(config)

    except (DataValidationError, FileNotFoundError) as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        st.error(f"Unexpected error: {exc}")
        return

    st.success("Seating plan generated")

    m = st.columns(4)
    m[0].metric("Total", result.summary.total_students)
    m[1].metric("Eligible", result.summary.eligible_students)
    m[2].metric("Allocated", result.summary.allocated_students)
    m[3].metric("Debarred", result.summary.not_eligible_students)

    raw_students = pd.read_excel(student_path)
    has_section = "Section" in raw_students.columns
    has_branch = "Branch" in raw_students.columns
    extra_cols = (["Section"] if has_section else []) + (["Branch"] if has_branch else [])

    alloc_sheets = pd.read_excel(output_dir / "exam_seating_output.xlsx", sheet_name=None)
    room_allocations_enriched: dict[str, pd.DataFrame] = {}
    for sheet_name, df in alloc_sheets.items():
        if not sheet_name.startswith("Room_"):
            continue
        room_no = sheet_name[len("Room_"):]
        if extra_cols:
            lookup = raw_students[["Roll Number"] + extra_cols].copy()
            lookup["Roll Number"] = lookup["Roll Number"].astype(str).str.strip()
            df["Roll Number"] = df["Roll Number"].astype(str).str.strip()
            df = df.merge(lookup, on="Roll Number", how="left")
        room_allocations_enriched[room_no] = df

    not_eligible_df = pd.read_excel(output_dir / "exam_seating_output.xlsx", sheet_name="Not_Eligible")
    if extra_cols:
        lookup = raw_students[["Roll Number"] + extra_cols].copy()
        lookup["Roll Number"] = lookup["Roll Number"].astype(str).str.strip()
        not_eligible_df["Roll Number"] = not_eligible_df["Roll Number"].astype(str).str.strip()
        not_eligible_df = not_eligible_df.merge(lookup, on="Roll Number", how="left")

    sirt_seating_path = export_sirt_main_seating_excel(
        room_allocations_enriched,
        output_dir,
        institute=info["institute"],
        department=info["department"],
        exam_title=info["exam_title"],
        semester=info["semester"],
    )
    sirt_debarred_path = export_sirt_debarred_excel(
        not_eligible_df,
        output_dir,
        institute=info["institute"],
        department=info["department"],
        exam_title=info["exam_title"],
        semester=info["semester"],
        attendance_cutoff=float(attendance_cutoff),
    )

    eligible_for_att = raw_students.copy()
    eligible_for_att["Attendance Percentage"] = pd.to_numeric(
        eligible_for_att["Attendance Percentage"], errors="coerce"
    )
    eligible_for_att = eligible_for_att[
        eligible_for_att["Attendance Percentage"] >= float(attendance_cutoff)
    ].reset_index(drop=True)

    sirt_att_path = export_sirt_attendance_sheets_excel(
        eligible_for_att,
        output_dir,
        subjects=st.session_state["exam_subjects"],
        institute=info["institute"],
        department=info["department"],
        exam_title=info["exam_title"],
        semester=info["semester"],
    )

    st.subheader("Downloads")
    d1, d2, d3 = st.columns(3)
    d1.download_button(
        "Main Seating Plan",
        data=sirt_seating_path.read_bytes(),
        file_name="SIRT_Main_Seating.xlsx",
        mime=XLSX_MIME,
        use_container_width=True,
    )
    d2.download_button(
        "Debarred List",
        data=sirt_debarred_path.read_bytes(),
        file_name="SIRT_Debarred_List.xlsx",
        mime=XLSX_MIME,
        use_container_width=True,
    )
    d3.download_button(
        "Attendance Sheets",
        data=sirt_att_path.read_bytes(),
        file_name="SIRT_Attendance_Sheets.xlsx",
        mime=XLSX_MIME,
        use_container_width=True,
    )

    combined_bytes = bundle_reports_zip(
        [sirt_seating_path, sirt_debarred_path, sirt_att_path],
        ["SIRT_Main_Seating.xlsx", "SIRT_Debarred_List.xlsx", "SIRT_Attendance_Sheets.xlsx"],
    )
    st.download_button(
        "Download All Reports (.zip)",
        data=combined_bytes,
        file_name="SIRT_All_Reports.zip",
        mime=ZIP_MIME,
        use_container_width=True,
        type="primary",
    )
