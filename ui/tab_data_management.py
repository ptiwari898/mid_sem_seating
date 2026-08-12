from __future__ import annotations

import hashlib
import time
from datetime import datetime

import pandas as pd
import streamlit as st

MARKS_PIN_KEY = "MARKS_PIN"


# ── Initialisation ────────────────────────────────────────────────

def _init_session_state() -> None:
    """Initialise session‑state keys used by this tab."""
    if "saved_students" not in st.session_state:
        st.session_state["saved_students"] = pd.DataFrame()
    if "faculty_marks" not in st.session_state:
        st.session_state["faculty_marks"] = None
    if "marks_authenticated" not in st.session_state:
        st.session_state["marks_authenticated"] = False
    if "pin_attempts" not in st.session_state:
        st.session_state["pin_attempts"] = 0
    if "pin_time" not in st.session_state:
        st.session_state["pin_time"] = 0


# ── Persistence helpers ──────────────────────────────────────────


def _save_students_to_session(students_df: pd.DataFrame) -> None:
    """Persist student DataFrame to session state."""
    st.session_state["saved_students"] = students_df.copy()
    st.session_state["students_saved_at"] = time.time()


def _load_students_from_session() -> pd.DataFrame:
    """Return saved student DataFrame, or empty DataFrame."""
    if st.session_state["saved_students"].empty:
        return pd.DataFrame()
    return st.session_state["saved_students"].copy()


def _clear_saved_students() -> None:
    st.session_state["saved_students"] = pd.DataFrame()
    st.session_state.pop("students_saved_at", None)


# ── PIN authentication ───────────────────────────────────────────


def _validate_pin(pin: str) -> bool:
    """Validate the 4‑digit PIN against Streamlit secrets."""
    # Initialise secrets key if not already loaded
    if MARKS_PIN_KEY not in st.secrets:
        st.error("⚠️ PIN configuration missing. Ask admin to set MARKS_PIN in .streamlit/secrets.toml.")
        return False

    correct_pin = str(st.secrets[MARKS_PIN_KEY])
    if pin == correct_pin:
        st.session_state["marks_authenticated"] = True
        st.session_state["pin_attempts"] = 0
        st.session_state["pin_time"] = time.time()
        return True
    else:
        st.session_state["pin_attempts"] += 1
        remaining = max(0, 3 - st.session_state["pin_attempts"])
        if st.session_state["pin_attempts"] >= 3 and pin != correct_pin:
            st.error(
                "🔒 Too many failed attempts. PIN locked for 15 minutes. "
                "Try again later or restart the app."
            )
            # Auto‑reset after 15 min
            if time.time() - st.session_state["pin_time"] > 900:
                st.session_state["pin_attempts"] = 0
                st.session_state["marks_authenticated"] = False
        else:
            st.error(f"Invalid PIN. {remaining} attempt(s) remaining.")
        return False


# ── Marks‑entry data builder ─────────────────────────────────────


def _build_marks_entries(students_df: pd.DataFrame) -> pd.DataFrame:
    """Create an editable DataFrame for faculty to enter marks."""
    df = students_df[["Roll Number", "Name"]].copy()
    df["Marks"] = 0
    df["Absent"] = False
    return df


# ── Render ───────────────────────────────────────────────────────


def render_tab_data_management() -> None:
    """Render the Data & Marks Management tab."""
    _init_session_state()

    st.header("📋 Data & Marks Management")

    # -----------------------------------------------------------------
    # A. Student Data Storage
    # -----------------------------------------------------------------
    st.subheader("💾 Student Data Storage")

    st.caption("Upload and save student data. This data will be available in the Result Analysis tab.")
    st.info(
        "💡 **Tip:** Save your student list once. It will persist for this session "
        "and can be loaded automatically in the Result Analysis tab."
    )

    with st.expander("Upload Students File", expanded=st.session_state["saved_students"].empty):
        students_file = st.file_uploader(
            "Upload students (.xlsx/.xls/.csv)",
            type=["xlsx", "xls", "csv"],
            key="students_upload_dm",
        )

        if students_file is not None:
            try:
                if students_file.name.lower().endswith(".csv"):
                    uploaded_df = pd.read_csv(students_file)
                else:
                    xl = pd.ExcelFile(students_file)
                    # Auto-detect which sheet has the required columns
                    uploaded_df = pd.DataFrame()
                    for sheet in xl.sheet_names:
                        df_sheet = pd.read_excel(xl, sheet_name=sheet)
                        required = {"Roll Number", "Name", "Attendance Percentage"}
                        if required.issubset(set(df_sheet.columns)):
                            uploaded_df = df_sheet
                            break
                    if uploaded_df.empty:
                        st.error("No sheet with Roll Number, Name, Attendance Percentage found.")
                        st.stop()

                # Normalise columns
                uploaded_df.columns = [c.strip() for c in uploaded_df.columns]

                required = {"Roll Number", "Name", "Attendance Percentage"}
                missing = required - set(uploaded_df.columns)
                if missing:
                    st.error(f"Missing required columns: {', '.join(missing)}")
                else:
                    # Normalise attendance
                    attendance_numeric = pd.to_numeric(
                        uploaded_df["Attendance Percentage"], errors="coerce"
                    )
                    invalid_count = int(attendance_numeric.isna().sum())
                    if invalid_count > 0:
                        st.warning(f"{invalid_count} students had unparseable attendance and were excluded.")
                    uploaded_df = uploaded_df[attendance_numeric.notna()].copy()
                    uploaded_df["Attendance Percentage"] = (
                        attendance_numeric[attendance_numeric.notna()].astype(float)
                    )
                    uploaded_df = uploaded_df.drop_duplicates(subset=["Roll Number"], keep="first")
                    uploaded_df = uploaded_df.sort_values(
                        by=["Roll Number"], kind="mergesort"
                    ).reset_index(drop=True)

                if not uploaded_df.empty:
                    _save_students_to_session(uploaded_df)
                    st.success(f"✅ Saved {len(uploaded_df)} students to session.")
                    st.dataframe(
                        uploaded_df.head(10), use_container_width=True, hide_index=True
                    )

            except Exception as e:
                st.error(f"⚠️ Failed to process file: {str(e)[:200]}")

    # -----------------------------------------------------------------
    # Buttons for managing saved data
    # -----------------------------------------------------------------
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if not st.session_state["saved_students"].empty:
            if st.button("🗑️ Clear Saved Data", help="Clear saved student data"):
                _clear_saved_students()
                st.rerun()
    with col_b:
        if st.session_state["saved_students"].empty:
            st.caption("No saved data yet.")

    # -----------------------------------------------------------------
    # B. Faculty Marks Upload (PIN Protected)
    # -----------------------------------------------------------------
    st.divider()
    st.subheader("🔐 Faculty Marks Entry")

    # PIN entry area
    if not st.session_state["marks_authenticated"]:
        st.caption("Enter the 4‑digit PIN to access marks entry.")
        pin_col1, pin_col2 = st.columns([3, 1])
        with pin_col1:
            pin_code = st.text_input("PIN", type="password", key="pin_input_dm")
        with pin_col2:
            if st.button("Submit", help="Enter PIN to authenticate"):
                _validate_pin(pin_code)

        if st.session_state["pin_attempts"] >= 3 and not st.session_state["marks_authenticated"]:
            st.warning("🔒 3 failed attempts reached. Waiting 15 min before retry...")
        st.caption(
            "Default PIN: `1234` (configured in `.streamlit/secrets.toml`). "
            "Contact admin to change."
        )

    # -----------------------------------------------------------------
    # Marks entry interface (shown after PIN auth)
    # -----------------------------------------------------------------
    else:
        st.success("✅ Authentication successful.")

        # Faculty info form
        with st.form("faculty_info_form"):
            c1, c2, c3 = st.columns(3)
            faculty_name = c1.text_input("Faculty Name", key="faculty_name")
            subject_name = c2.text_input("Subject Name/Code", key="subject_name")
            exam_name = c3.text_input("Exam Name", key="exam_name")
            submit_info = st.form_submit_button("Submit Faculty Info")

        if submit_info:
            if not faculty_name.strip() or not subject_name.strip():
                st.error("Faculty name and subject are required.")
            else:
                students_df = _load_students_from_session()
                if students_df.empty:
                    st.error("No student data saved. Please upload students first.")
                else:
                    # Build editable marks table
                    marks_df = _build_marks_entries(students_df)

                    st.session_state["faculty_marks"] = {
                        "faculty_name": faculty_name.strip(),
                        "subject": subject_name.strip(),
                        "exam": exam_name.strip() if exam_name.strip() else "Unnamed Exam",
                        "entries": marks_df.to_dict("records"),
                        "verified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }

                    st.success("✅ Faculty info saved. Marks entry interface below.")
                    st.rerun()

        # -----------------------------------------------------------------
        # Marks data editor
        # -----------------------------------------------------------------
        if st.session_state["faculty_marks"] is not None:
            marks_data = st.session_state["faculty_marks"]
            students_df = _load_students_from_session()

            st.caption(f"Faculty: **{marks_data['faculty_name']}**  |  Subject: **{marks_data['subject']}**  |  Exam: **{marks_data['exam']}**")

            # Merge existing marks if any
            entries = marks_data.get("entries", [])
            if entries:
                # Ensure columns match
                existing_df = pd.DataFrame(entries)
                if list(existing_df.columns) != ["Roll Number", "Name", "Marks", "Absent"]:
                    # Rebuild from students
                    entries = _build_marks_entries(students_df).to_dict("records")
            else:
                entries = _build_marks_entries(students_df).to_dict("records")

            # Editable data editor
            edited_df = st.data_editor(
                pd.DataFrame(entries),
                column_config={
                    "Roll Number": st.column_config.TextColumn(
                        "Roll No.", help="Student roll number"
                    ),
                    "Name": st.column_config.TextColumn("Student Name", help="Student name"),
                    "Marks": st.column_config.NumberColumn(
                        "Marks",
                        help="Marks obtained (0-30)",
                        min_value=0,
                        max_value=30,
                        step=1,
                    ),
                    "Absent": st.column_config.CheckboxColumn(
                        "Absent", help="Mark student as absent"
                    ),
                },
                disabled=["Roll Number", "Name"],
                use_container_width=True,
                hide_index=True,
                key="marks_editor_dm",
            )

            # -----------------------------------------------------------------
            # Submit marks button
            # -----------------------------------------------------------------
            st.divider()
            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("💾 Submit Marks", type="primary", use_container_width=True):
                    # Update the entries with edited values
                    marks_data["entries"] = edited_df.to_dict("records")
                    marks_data["verified_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    st.session_state["faculty_marks"] = marks_data

                    # Also save marks globally for other tabs to use
                    st.session_state["submitted_marks"] = {
                        "faculty": marks_data["faculty_name"],
                        "subject": marks_data["subject"],
                        "exam": marks_data["exam"],
                        "entries": edited_df.to_dict("records"),
                        "timestamp": datetime.now().isoformat(),
                    }

                    st.success("✅ Marks submitted successfully!")
                    st.balloons()
                    st.rerun()

            with c2:
                if st.button("❌ Cancel", use_container_width=True):
                    # Reset authentication but keep students
                    st.session_state["marks_authenticated"] = False
                    st.session_state["pin_attempts"] = 0
                    st.session_state.pop("faculty_marks", None)
                    st.session_state.pop("submitted_marks", None)
                    st.rerun()

    # -----------------------------------------------------------------
    # C. Data History & Export
    # -----------------------------------------------------------------
    st.divider()
    st.subheader("📚 Data History")

    # Summarise what we have
    history_parts = []

    if not st.session_state["saved_students"].empty:
        history_parts.append(
            f"📁 Saved students: **{len(st.session_state['saved_students'])}** "
            f"(saved at {datetime.fromtimestamp(st.session_state.get('students_saved_at', 0)).strftime('%H:%M:%S')})"
        )

    if st.session_state.get("faculty_marks") is not None:
        fm = st.session_state["faculty_marks"]
        history_parts.append(
            f"📝 Marks submitted: **{fm['subject']}** by {fm['faculty_name']} "
            f"for {fm['exam']}"
        )

    if st.session_state.get("submitted_marks") is not None:
        sm = st.session_state["submitted_marks"]
        history_parts.append(
            f"📊 Submitted marks: **{sm['subject']}** ({len(sm['entries'])} entries)"
        )

    if not history_parts:
        history_parts.append("No data saved yet. Upload students and submit marks above.")

    for line in history_parts:
        st.caption(line)

    # Export / Clear buttons
    col_x, col_y = st.columns([1, 1])
    with col_x:
        if (
            not st.session_state["saved_students"].empty
            or st.session_state.get("faculty_marks") is not None
            or st.session_state.get("submitted_marks") is not None
        ):
            if st.button("📥 Export All Data", help="Export saved students + marks as CSV/Excel"):
                # Build export DataFrames
                export_parts = []

                # Saved students
                if not st.session_state["saved_students"].empty:
                    export_parts.append(
                        st.session_state["saved_students"]
                        .rename(
                            columns={
                                "Roll Number": "Roll_No",
                                "Name": "Student_Name",
                                "Attendance Percentage": "Attendance_%",
                            }
                        )
                        .assign(Source="Saved_Students")
                    )

                # Faculty marks
                if st.session_state.get("faculty_marks") is not None:
                    fm = st.session_state["faculty_marks"]
                    marks_df = pd.DataFrame(fm["entries"])
                    marks_export = marks_df.assign(
                        Faculty=fm["faculty_name"],
                        Subject=fm["subject"],
                        Exam=fm["exam"],
                        Source="Faculty_Marks",
                    )
                    export_parts.append(marks_export)

                if export_parts:
                    combined = pd.concat(export_parts, ignore_index=True)
                    csv_bytes = combined.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "Download Export CSV",
                        data=csv_bytes,
                        file_name="data_export.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

    with col_y:
        if (
            not st.session_state["saved_students"].empty
            or st.session_state.get("faculty_marks") is not None
            or st.session_state.get("submitted_marks") is not None
        ):
            if st.button("🗑️ Clear All Data", help="Clear all saved data for this session"):
                _clear_saved_students()
                st.session_state.pop("faculty_marks", None)
                st.session_state.pop("submitted_marks", None)
                st.session_state["marks_authenticated"] = False
                st.session_state["pin_attempts"] = 0
                st.rerun()