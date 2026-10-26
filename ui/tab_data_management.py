from __future__ import annotations

import time
from datetime import datetime

import pandas as pd
import streamlit as st

from exam_seating.io_utils import parse_attendance


# ── Initialisation ────────────────────────────────────────────────

def _init_session_state() -> None:
    """Initialise session‑state keys used by this tab."""
    if "saved_students" not in st.session_state:
        st.session_state["saved_students"] = pd.DataFrame()


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


# ── Render ───────────────────────────────────────────────────────


def render_tab_data_management() -> None:
    """Render the saved-student data tab."""
    _init_session_state()

    st.header("Saved Students")
    st.caption("Keep a student list for this browser session so Result Analysis can use it.")

    saved = st.session_state["saved_students"]

    with st.expander("Upload students file", expanded=saved.empty):
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
                    attendance_numeric = parse_attendance(uploaded_df["Attendance Percentage"])
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
                    st.success(f"Saved {len(uploaded_df)} students to this session.")
                    st.dataframe(
                        uploaded_df.head(10), use_container_width=True, hide_index=True
                    )

            except Exception as e:
                st.error(f"Failed to process file: {str(e)[:200]}")

    saved = st.session_state["saved_students"]  # read again: the upload above may have changed it
    if not saved.empty:
        saved_at = datetime.fromtimestamp(st.session_state.get("students_saved_at", 0))
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1, 1], vertical_alignment="center")
            c1.markdown(f"**{len(saved)} students** saved at {saved_at:%H:%M}")
            c2.download_button(
                "Download",
                icon=":material/download:",
                data=saved.to_csv(index=False).encode("utf-8"),
                file_name="saved_students.csv",
                mime="text/csv",
                use_container_width=True,
            )
            if c3.button("Clear", icon=":material/delete:", help="Remove the saved list", use_container_width=True):
                _clear_saved_students()
                st.rerun()
