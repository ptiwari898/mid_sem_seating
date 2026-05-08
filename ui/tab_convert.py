from __future__ import annotations

from convert_result_to_students import convert_result_file
import pandas as pd
import streamlit as st

from ui.runtime import create_new_run_input_dir
from ui.templates import XLSX_MIME, df_to_excel_bytes, make_rooms_template, make_sample_result_workbook, make_students_template


def render_tab_convert() -> None:
    st.header("Step 1 - Convert Result Workbook")
    st.markdown(
        """
        Upload your SIRT result Excel file (.xlsx / .xls).
        The app auto-extracts students and rooms from selected sheets.
        """
    )

    with st.expander("How it works", expanded=False):
        st.markdown(
            """
            | Stage | What happens |
            |---|---|
            | Upload | Upload result workbook from exam section. |
            | Sheet detection | Select branch sheets to include. |
            | Extraction | Student/attendance data is parsed and normalized. |
            | Rooms | Room and capacity values are extracted from workbook. |
            """
        )

    with st.expander("Templates", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download students_template.xlsx",
                data=make_students_template(),
                file_name="students_template.xlsx",
                mime=XLSX_MIME,
                key="tmpl_students_tab1",
            )
        with c2:
            st.download_button(
                "Download rooms_template.xlsx",
                data=make_rooms_template(),
                file_name="rooms_template.xlsx",
                mime=XLSX_MIME,
                key="tmpl_rooms_tab1",
            )

    st.download_button(
        label="Download sample_result_workbook.xlsx",
        data=make_sample_result_workbook(),
        file_name="sample_result_workbook.xlsx",
        mime=XLSX_MIME,
        key="sample_wb_upload_section",
    )

    result_file = st.file_uploader(
        "Accepted formats: .xlsx, .xls",
        type=["xlsx", "xls"],
        key="result_upload",
    )

    if result_file is None:
        st.info("Upload a result workbook, then click Extract Students & Rooms.")
        return

    input_dir = create_new_run_input_dir()
    result_path = input_dir / result_file.name
    result_path.write_bytes(result_file.getbuffer())

    xl = pd.ExcelFile(result_path)
    all_sheets = xl.sheet_names
    default_selected = [
        s
        for s in all_sheets
        if "debarred" not in s.lower()
        and s.lower() not in {"sheet1", "over all result", "exam duty chart", "main seating"}
    ]

    selected_sheets = st.multiselect(
        "Sheets to include",
        options=all_sheets,
        default=default_selected,
        key="selected_result_sheets",
    )

    if not selected_sheets:
        st.warning("Select at least one sheet before extracting.")
        return

    if st.button("Extract Students & Rooms", type="primary", use_container_width=True):
        with st.spinner("Reading workbook and extracting data..."):
            try:
                students, rooms = convert_result_file(
                    result_path,
                    sheets=selected_sheets,
                    skip_debarred=False,
                )
            except Exception as exc:
                st.error(f"Extraction failed: {exc}")
                return

        if students.empty:
            st.error("No student records found in selected sheets.")
            return

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Students", len(students))
        m2.metric("Rooms Found", len(rooms))
        m3.metric("Sections", students["Section"].nunique() if "Section" in students.columns else "-")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Students")
            st.dataframe(students.head(20), use_container_width=True)
            st.download_button(
                label=f"Download students_extracted.xlsx ({len(students)} rows)",
                data=df_to_excel_bytes(students),
                file_name="students_extracted.xlsx",
                mime=XLSX_MIME,
                use_container_width=True,
            )
        with col2:
            st.subheader("Rooms")
            if rooms.empty:
                st.warning("No rooms found in workbook. Upload rooms manually in Step 2.")
            else:
                st.dataframe(rooms, use_container_width=True)
                st.download_button(
                    label=f"Download rooms_extracted.xlsx ({len(rooms)} rows)",
                    data=df_to_excel_bytes(rooms),
                    file_name="rooms_extracted.xlsx",
                    mime=XLSX_MIME,
                    use_container_width=True,
                )

        st.session_state["extracted_students"] = students
        st.session_state["extracted_rooms"] = rooms
        st.success("Extraction complete. Continue to Step 2.")
