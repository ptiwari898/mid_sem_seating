"""
Streamlit web app for the Automatic Exam Seating Arrangement System.

Tab 1 – Convert Result Workbook
    Upload your existing result Excel → one-click auto-extract students + rooms
    → preview data → download ready-to-use input files

Tab 2 – Generate Seating Plan
    Upload (or use auto-extracted) students + rooms files
    → configure options → generate seating
    → download SIRT-formatted outputs (Main Seating, Debarred List, Attendance Sheets, Excel)
"""
from __future__ import annotations

import io
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st

from convert_result_to_students import convert_result_file
from exam_seating.io_utils import DataValidationError
from exam_seating.service import SeatingConfig, run_seating_system
from exam_seating.sirt_exporters import (
    export_sirt_attendance_sheets_excel,
    export_sirt_debarred_excel,
    export_sirt_main_seating_excel,
    export_sirt_section_attendance_excel,
)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _save_uploaded(uploaded_file, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / uploaded_file.name
    path.write_bytes(uploaded_file.getbuffer())
    return path


def _df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def _make_students_template() -> bytes:
    df = pd.DataFrame(
        [
            {"Roll Number": "0133CI231002", "Name": "AARBI DHAKAD",       "Attendance Percentage": 82},
            {"Roll Number": "0133CI231008", "Name": "ABHISHEK KUMAR",     "Attendance Percentage": 61},
            {"Roll Number": "0133CI231014", "Name": "ADITYA KUMAR SHAH",  "Attendance Percentage": 75},
            {"Roll Number": "0133CI231024", "Name": "AMANJEET SINGH",     "Attendance Percentage": 38},
            {"Roll Number": "0133CI231035", "Name": "ANJALI SHRIVASTAVA", "Attendance Percentage": 55},
        ]
    )
    return _df_to_excel_bytes(df)


def _make_rooms_template() -> bytes:
    df = pd.DataFrame(
        [
            {"Room Number": "F-307", "Capacity": 40},
            {"Room Number": "F-308", "Capacity": 40},
            {"Room Number": "F-309", "Capacity": 40},
            {"Room Number": "F-310", "Capacity": 30},
        ]
    )
    return _df_to_excel_bytes(df)


def _make_room_exam_config_template() -> bytes:
    """Template for room exam configuration with room, capacity, subject, and date."""
    df = pd.DataFrame(
        [
            {"Room Number": "F-307", "Capacity": 40, "Subject": "Computer Networks", "Date": "2026-06-05"},
            {"Room Number": "F-308", "Capacity": 40, "Subject": "Database Systems",  "Date": "2026-06-05"},
            {"Room Number": "F-309", "Capacity": 40, "Subject": "Web Development",   "Date": "2026-06-06"},
            {"Room Number": "F-310", "Capacity": 30, "Subject": "Data Structures",   "Date": "2026-06-06"},
        ]
    )
    return _df_to_excel_bytes(df)


def _make_sample_result_workbook() -> bytes:
    """Generate a realistic SIRT-style result workbook with header rows, 3 branch sheets,
    and a Main Seating sheet — ready to upload in Step 1."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        wb = writer.book

        # ── Styles ────────────────────────────────────────────────────────────
        hdr_fmt = wb.add_format({
            "bold": True, "align": "center", "valign": "vcenter",
            "font_size": 12, "border": 1,
        })
        col_fmt = wb.add_format({
            "bold": True, "align": "center", "valign": "vcenter",
            "border": 1, "bg_color": "#D9E1F2",
        })
        cell_fmt = wb.add_format({"border": 1, "align": "center", "valign": "vcenter"})

        # ── Branch sheets ─────────────────────────────────────────────────────
        INSTITUTE = "SAGAR INSTITUTE OF RESEARCH & TECHNOLOGY"
        DEPT      = "DEPARTMENT OF COMPUTER SCIENCE & INFORMATION TECHNOLOGY (CSIT)"
        EXAM      = "I MID SEM EXAMINATION (JAN–JUN 2026)"

        branches = {
            "6th A": [
                ("0133CI231002", "AARBI DHAKAD",           85),
                ("0133CI231008", "ABHISHEK KUMAR",          62),
                ("0133CI231014", "ADITYA KUMAR SHAH",       78),
                ("0133CI231024", "AMANJEET SINGH",          35),
                ("0133CI231035", "ANJALI SHRIVASTAVA",      55),
                ("0133CI231041", "ANKIT PATEL",             90),
                ("0133CI231047", "ANSHUL VERMA",            48),
                ("0133CI231053", "ARPIT MISHRA",            72),
                ("0133CI231059", "ATUL SHARMA",             66),
                ("0133CI231065", "BHAVESH TIWARI",          80),
            ],
            "6th B": [
                ("0133ME231001", "AAKASH SINGH",            70),
                ("0133ME231007", "AASTHA GUPTA",            55),
                ("0133ME231013", "ABHAY KUMAR",             38),
                ("0133ME231019", "ABHINAV RAI",             85),
                ("0133ME231025", "ADITI JAIN",              60),
                ("0133ME231031", "ADITYA THAKUR",           77),
                ("0133ME231037", "AJAY BAGHEL",             92),
                ("0133ME231043", "AKASH CHOUHAN",           44),
                ("0133ME231049", "AKSHAY KORI",             68),
                ("0133ME231055", "ALKA PATEL",              73),
            ],
            "6th C": [
                ("0133EC231003", "AKASH SAHU",              81),
                ("0133EC231009", "ALISHA KHAN",             59),
                ("0133EC231015", "AMANDEEP KHATRI",         36),
                ("0133EC231021", "AMISHA DUBEY",            74),
                ("0133EC231027", "AMRIT PAL",               88),
                ("0133EC231033", "ANANYA SHUKLA",           50),
                ("0133EC231039", "ANKITA YADAV",            67),
                ("0133EC231045", "ANSHIKA TRIPATHI",        41),
                ("0133EC231051", "ANURAG TIWARI",           95),
                ("0133EC231057", "ARJUN SINGH",             63),
            ],
        }

        for sheet_name, students in branches.items():
            ws = wb.add_worksheet(sheet_name)
            ws.set_column(0, 0, 6)
            ws.set_column(1, 1, 22)
            ws.set_column(2, 2, 32)
            ws.set_column(3, 3, 22)

            # Header rows (institute branding)
            ws.set_row(0, 20)
            ws.set_row(1, 18)
            ws.set_row(2, 16)
            ws.merge_range("A1:D1", INSTITUTE, hdr_fmt)
            ws.merge_range("A2:D2", DEPT,      hdr_fmt)
            ws.merge_range("A3:D3", EXAM,      hdr_fmt)
            ws.merge_range("A4:D4", f"Subject: Computer Networks    {sheet_name}", hdr_fmt)

            # Column headers at row 5 (0-indexed: row 4)
            for col, label in enumerate(["S.No", "Board EnrollNo", "Student Name", "Attendance %"]):
                ws.write(4, col, label, col_fmt)

            # Student data
            for i, (roll, name, att) in enumerate(students):
                ws.write(5 + i, 0, i + 1,   cell_fmt)
                ws.write(5 + i, 1, roll,     cell_fmt)
                ws.write(5 + i, 2, name,     cell_fmt)
                ws.write(5 + i, 3, f"{att}%", cell_fmt)

        # ── Main Seating sheet ────────────────────────────────────────────────
        ms = wb.add_worksheet("Main Seating")
        ms.set_column(0, 0, 8)
        ms.set_column(1, 1, 16)
        ms.set_column(2, 2, 12)
        ms.set_column(3, 3, 32)
        ms.set_column(4, 4, 26)
        ms.set_column(5, 5, 14)

        ms.merge_range("A1:F1", INSTITUTE, hdr_fmt)
        ms.merge_range("A2:F2", EXAM, hdr_fmt)
        ms.merge_range("A3:F3", "MAIN SEATING ARRANGEMENT", hdr_fmt)

        ms_cols = ["S. No.", "BRANCH", "Section", "Roll Number", "No. of Students Appeared", "Class Room"]
        for col, label in enumerate(ms_cols):
            ms.write(3, col, label, col_fmt)

        room_rows = [
            (1, "CSIT",  "A", "0133CI231002, 0133CI231008, 0133CI231014, 0133CI231024, 0133CI231035, 0133CI231041, 0133CI231047, 0133CI231053, 0133CI231059, 0133CI231065", 10, "F-307"),
            (2, "ME",    "B", "0133ME231001, 0133ME231007, 0133ME231013, 0133ME231019, 0133ME231025, 0133ME231031, 0133ME231037, 0133ME231043, 0133ME231049, 0133ME231055", 10, "F-308"),
            (3, "EC",    "C", "0133EC231003, 0133EC231009, 0133EC231015, 0133EC231021, 0133EC231027, 0133EC231033, 0133EC231039, 0133EC231045, 0133EC231051, 0133EC231057", 10, "F-309"),
        ]
        for r, row in enumerate(room_rows):
            for c, val in enumerate(row):
                ms.write(4 + r, c, val, cell_fmt)

        # ── Debarred sheet (bonus) ────────────────────────────────────────────
        db = wb.add_worksheet("Debarred")
        db.merge_range("A1:E1", INSTITUTE, hdr_fmt)
        db.merge_range("A2:E2", "Debarred Students List (Attendance < 40%)", hdr_fmt)
        for col, label in enumerate(["S.No", "Board EnrollNo", "Student Name", "Attendance %", "Section"]):
            db.write(2, col, label, col_fmt)
        debarred = [
            (1, "0133CI231024", "AMANJEET SINGH",    "35%", "A"),
            (2, "0133ME231013", "ABHAY KUMAR",        "38%", "B"),
            (3, "0133EC231015", "AMANDEEP KHATRI",    "36%", "C"),
            (4, "0133ME231043", "AKASH CHOUHAN",      "44%", "B"),
            (5, "0133EC231045", "ANSHIKA TRIPATHI",   "41%", "C"),
        ]
        for r, row in enumerate(debarred):
            for c, val in enumerate(row):
                db.write(3 + r, c, val, cell_fmt)

    return buf.getvalue()


def _sidebar_institute_info() -> dict:
    st.sidebar.header("Institute Info")
    institute = st.sidebar.text_input("Institute Name", "SAGAR INSTITUTE OF RESEARCH & TECHNOLOGY")
    department = st.sidebar.text_input("Department", "DEPARTMENT OF CSIT")
    exam_title = st.sidebar.text_input("Exam Title", "I MID SEM EXAMINATION (JAN-JUN 2026)")
    semester = st.sidebar.text_input("Semester", "6th Sem")

    st.sidebar.divider()
    st.sidebar.subheader("Sample Input Templates")
    st.sidebar.write("Not sure about the file format? Download these examples.")
    st.sidebar.download_button(
        label="⬇ students_template.xlsx",
        data=_make_students_template(),
        file_name="students_template.xlsx",
        mime=XLSX_MIME,
        help="Required columns: Roll Number | Name | Attendance Percentage",
    )
    st.sidebar.download_button(
        label="⬇ rooms_template.xlsx",
        data=_make_rooms_template(),
        file_name="rooms_template.xlsx",
        mime=XLSX_MIME,
        help="Required columns: Room Number | Capacity",
    )

    return {"institute": institute, "department": department,
            "exam_title": exam_title, "semester": semester}


def tab_convert() -> None:
    st.header("📂 Step 1 — Convert Result Workbook")
    st.markdown(
        """
        Upload your **SIRT result Excel file** (.xlsx / .xls).  
        The app will automatically detect every branch sheet, extract student roll numbers,
        names, and attendance, and pull exam room data from the **Main Seating** sheet —
        all in one click.  
        The extracted files are then passed directly to **Step 2** so you never need to
        prepare input files by hand.
        """
    )

    # ── How it works ──────────────────────────────────────────────────────────
    with st.expander("ℹ️  How does this work?", expanded=False):
        st.markdown(
            """
            | Stage | What happens |
            |---|---|
            | **Upload** | You upload the result Excel workbook (the same file shared by the exam section). |
            | **Sheet detection** | All branch/section sheets (e.g. *6th A*, *6th B*) are listed. Utility sheets like *Main Seating* and *Debarred* are excluded automatically. |
            | **Extraction** | Each sheet is scanned for the student table. Roll number, name, and attendance % are normalised. Section and branch are inferred from the sheet name. |
            | **Rooms** | Room numbers and capacities are read from the *Main Seating* sheet (if present). |
            | **Download / Continue** | Preview both tables, then either download them as `.xlsx` files or go straight to Step 2 — the data is already loaded. |
            """
        )
        st.markdown("**Want to try it with a sample file first?**")
        st.download_button(
            label="⬇ Download sample_result_workbook.xlsx",
            data=_make_sample_result_workbook(),
            file_name="sample_result_workbook.xlsx",
            mime=XLSX_MIME,
            help="A realistic SIRT-format workbook with 3 branch sheets, a Main Seating sheet, and a Debarred sheet.",
            key="sample_wb_expander",
        )

    # ── Sample templates ──────────────────────────────────────────────────────
    with st.expander("📥  Don't have a result workbook? Use these manual input templates", expanded=False):
        st.markdown("If you want to enter student and room data by hand instead of uploading a result workbook, download these starter files, fill them in, and upload them in **Step 2**.")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                "**students_template.xlsx**  \n"
                "Columns: `Roll Number` · `Name` · `Attendance Percentage`"
            )
            st.download_button(
                "⬇ Download students_template.xlsx",
                data=_make_students_template(),
                file_name="students_template.xlsx",
                mime=XLSX_MIME,
                key="tmpl_students_tab1",
            )
        with c2:
            st.markdown(
                "**rooms_template.xlsx**  \n"
                "Columns: `Room Number` · `Capacity`"
            )
            st.download_button(
                "⬇ Download rooms_template.xlsx",
                data=_make_rooms_template(),
                file_name="rooms_template.xlsx",
                mime=XLSX_MIME,
                key="tmpl_rooms_tab1",
            )

    st.divider()

    # ── Upload ─────────────────────────────────────────────────────────────────
    st.subheader("📤 Upload your result workbook")
    st.caption("New here? Download the sample workbook below, then upload it to see how extraction works.")
    st.download_button(
        label="⬇ Download sample_result_workbook.xlsx  (try with this first)",
        data=_make_sample_result_workbook(),
        file_name="sample_result_workbook.xlsx",
        mime=XLSX_MIME,
        help="Contains 3 branch sheets (6th A/B/C), Main Seating, and Debarred — mirrors a real SIRT result file.",
        key="sample_wb_upload_section",
    )
    result_file = st.file_uploader(
        "Accepted formats: .xlsx, .xls",
        type=["xlsx", "xls"],
        key="result_upload",
        help="Upload the Excel result file received from the exam section.",
    )

    if result_file is None:
        st.info("⬆️  Upload a result workbook above, then click **Extract Students & Rooms**.")
        return

    run_id = uuid4().hex[:8]
    tmp_dir = Path("web_runs") / run_id / "input"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    result_path = tmp_dir / result_file.name
    result_path.write_bytes(result_file.getbuffer())

    # ── Sheet selector ─────────────────────────────────────────────────────────
    xl = pd.ExcelFile(result_path)
    all_sheets = xl.sheet_names
    default_selected = [
        s for s in all_sheets
        if "debarred" not in s.lower()
        and s.lower() not in {"sheet1", "over all result", "exam duty chart", "main seating"}
    ]
    st.subheader("📋 Select student sheets")
    st.caption(
        "All sheets are listed below. Deselect any that do not contain student data "
        "(e.g. summary sheets, duty charts)."
    )
    selected_sheets = st.multiselect(
        "Sheets to include",
        options=all_sheets,
        default=default_selected,
        help="Only selected sheets will be scanned for student records.",
    )
    if not selected_sheets:
        st.warning("Select at least one sheet before extracting.")
        return

    st.divider()

    # ── Extract button ─────────────────────────────────────────────────────────
    if st.button("⚙️  Extract Students & Rooms", type="primary", use_container_width=True):
        with st.spinner("Reading workbook and extracting data…"):
            try:
                students, rooms = convert_result_file(
                    result_path,
                    sheets=selected_sheets,
                    skip_debarred=False,
                )
            except Exception as exc:
                st.error(f"❌ Extraction failed: {exc}")
                return

        if students.empty:
            st.error("No student records found in the selected sheets. Check that the sheets contain a 'Board EnrollNo' or 'Roll Number' column.")
            return

        # ── Results ────────────────────────────────────────────────────────────
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Students", len(students))
        m2.metric("Rooms Found", len(rooms))
        m3.metric("Sections", students["Section"].nunique() if "Section" in students.columns else "—")

        st.success("✅ Extraction complete! Preview your data and download below, or switch to **Step 2** to generate the seating plan right away.")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("👨‍🎓 Students")
            st.dataframe(students.head(20), use_container_width=True)
            if len(students) > 20:
                st.caption(f"Showing first 20 of {len(students)} rows.")
            st.download_button(
                label=f"⬇ Download students_extracted.xlsx  ({len(students)} rows)",
                data=_df_to_excel_bytes(students),
                file_name="students_extracted.xlsx",
                mime=XLSX_MIME,
                use_container_width=True,
            )
        with col2:
            st.subheader("🏫 Rooms")
            if rooms.empty:
                st.warning("No rooms found in the workbook. You can upload a rooms file manually in Step 2.")
            else:
                st.dataframe(rooms, use_container_width=True)
                st.download_button(
                    label=f"⬇ Download rooms_extracted.xlsx  ({len(rooms)} rows)",
                    data=_df_to_excel_bytes(rooms),
                    file_name="rooms_extracted.xlsx",
                    mime=XLSX_MIME,
                    use_container_width=True,
                )

        st.session_state["extracted_students"] = students
        st.session_state["extracted_rooms"] = rooms
        st.info("💡 Data has been loaded into memory. Switch to **Step 2 — Generate Seating Plan** to continue.")


def tab_generate(info: dict) -> None:
    st.header("📋 Step 2 — Generate Seating Plan")

    # Initialize session state for manual data entry
    if "manual_students" not in st.session_state:
        st.session_state["manual_students"] = []
    if "manual_rooms" not in st.session_state:
        st.session_state["manual_rooms"] = []
    if "manual_exam_config" not in st.session_state:
        st.session_state["manual_exam_config"] = []
    if "manual_timetable" not in st.session_state:
        st.session_state["manual_timetable"] = []

    # ── Tab switcher for input method ──────────────────────────────────────────
    have_extracted = "extracted_students" in st.session_state
    input_source = st.radio(
        "Choose input method:",
        options=["Manual Entry", "From Step 1 Extraction"] if have_extracted else ["Manual Entry"],
        horizontal=True,
    )

    if input_source == "From Step 1 Extraction" and have_extracted:
        st.success(
            f"✅ Using extracted data: **{len(st.session_state['extracted_students'])}** students, "
            f"**{len(st.session_state['extracted_rooms'])}** rooms."
        )
        students_df = st.session_state["extracted_students"].copy()
        rooms_df = st.session_state["extracted_rooms"].copy()
        exam_config_df = None
    else:
        # ── MANUAL ENTRY SECTION ──────────────────────────────────────────────
        st.subheader("👨‍🎓 Add Students")
        st.caption("Enter student details one by one, or upload an Excel/CSV file.")

        # ── Upload options ─────────────────────────────────────────────────────
        upload_mode = st.radio(
            "Upload method:",
            ["Simple Excel / CSV", "Section-wise Attendance Workbook (multi-sheet)"],
            horizontal=True,
            key="student_upload_mode",
        )

        # ── Simple upload ──────────────────────────────────────────────────────
        with st.expander("📂 Upload Students from Excel / CSV", expanded=upload_mode == "Simple Excel / CSV"):
            st.caption(
                "File must have columns: **Roll Number**, **Name**, **Attendance Percentage**. "
                "Duplicate roll numbers will be skipped."
            )
            uploaded_students = st.file_uploader(
                "Choose file", type=["xlsx", "xls", "csv"], key="students_upload"
            )
            col_import, col_dl = st.columns([1, 1])
            if col_import.button("⬆️ Import Students", key="import_students_btn"):
                if uploaded_students is None:
                    st.error("Please select a file first.")
                else:
                    try:
                        if uploaded_students.name.endswith(".csv"):
                            df_up = pd.read_csv(uploaded_students)
                        else:
                            df_up = pd.read_excel(uploaded_students)

                        required_cols = {"Roll Number", "Name", "Attendance Percentage"}
                        missing = required_cols - set(df_up.columns)
                        if missing:
                            st.error(f"Missing columns: {', '.join(missing)}")
                        else:
                            df_up = df_up.dropna(subset=["Roll Number", "Name"])
                            existing_rolls = {s["Roll Number"] for s in st.session_state["manual_students"]}
                            added, skipped = 0, 0
                            for _, row in df_up.iterrows():
                                roll = str(row["Roll Number"]).strip()
                                if roll in existing_rolls:
                                    skipped += 1
                                else:
                                    st.session_state["manual_students"].append({
                                        "Roll Number": roll,
                                        "Name": str(row["Name"]).strip(),
                                        "Attendance Percentage": float(row["Attendance Percentage"]),
                                    })
                                    existing_rolls.add(roll)
                                    added += 1
                            msg = f"✅ Imported **{added}** student(s)."
                            if skipped:
                                msg += f" Skipped **{skipped}** duplicate(s)."
                            st.success(msg)
                            st.rerun()
                    except Exception as exc:
                        st.error(f"Failed to read file: {exc}")

            col_dl.download_button(
                "⬇️ Download Template",
                data=_make_students_template(),
                file_name="students_template.xlsx",
                mime=XLSX_MIME,
                key="dl_students_template_manual",
            )

        # ── Section-wise workbook upload ───────────────────────────────────────
        with st.expander("📑 Upload Section-wise Attendance Workbook", expanded=upload_mode == "Section-wise Attendance Workbook (multi-sheet)"):
            st.caption(
                "Upload a multi-sheet Excel workbook where **each sheet is one section** "
                "(e.g. *6th A*, *6th B*, *CSIT-A*). "
                "Each sheet must contain roll number, name, and attendance % columns "
                "(column names are detected automatically). "
                "Debarred sheets are skipped automatically."
            )
            uploaded_section_wb = st.file_uploader(
                "Choose workbook", type=["xlsx", "xls"], key="section_wb_upload"
            )

            if uploaded_section_wb is not None:
                try:
                    import tempfile, os
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                        tmp.write(uploaded_section_wb.getbuffer())
                        tmp_path = Path(tmp.name)

                    xl_preview = pd.ExcelFile(tmp_path)
                    all_sheets = xl_preview.sheet_names
                    non_debarred = [s for s in all_sheets if "debarred" not in s.lower()]

                    st.info(
                        f"Detected **{len(all_sheets)}** sheet(s): {', '.join(all_sheets)}. "
                        f"**{len(non_debarred)}** will be processed (debarred sheets skipped)."
                    )

                    selected_sheets = st.multiselect(
                        "Sheets to import (deselect any you want to skip):",
                        options=non_debarred,
                        default=non_debarred,
                        key="section_wb_sheets",
                    )
                except Exception as exc:
                    st.error(f"Could not read workbook: {exc}")
                    selected_sheets = []
                    tmp_path = None
            else:
                selected_sheets = []
                tmp_path = None

            if st.button("⬆️ Import from Workbook", key="import_section_wb_btn"):
                if uploaded_section_wb is None:
                    st.error("Please select a workbook first.")
                elif not selected_sheets:
                    st.error("No sheets selected.")
                else:
                    try:
                        students_extracted, _ = convert_result_file(
                            tmp_path, sheets=selected_sheets, skip_debarred=False
                        )
                        if students_extracted.empty:
                            st.error(
                                "No valid student data found. Make sure each sheet has "
                                "roll number, name, and attendance % columns."
                            )
                        else:
                            existing_rolls = {s["Roll Number"] for s in st.session_state["manual_students"]}
                            added, skipped = 0, 0
                            for _, row in students_extracted.iterrows():
                                roll = str(row["Roll Number"]).strip()
                                if roll in existing_rolls:
                                    skipped += 1
                                else:
                                    st.session_state["manual_students"].append({
                                        "Roll Number": roll,
                                        "Name": str(row["Name"]).strip(),
                                        "Attendance Percentage": float(row["Attendance Percentage"]),
                                    })
                                    existing_rolls.add(roll)
                                    added += 1
                            msg = f"✅ Imported **{added}** student(s) from **{len(selected_sheets)}** section(s)."
                            if skipped:
                                msg += f" Skipped **{skipped}** duplicate(s)."
                            st.success(msg)
                            try:
                                os.unlink(tmp_path)
                            except Exception:
                                pass
                            st.rerun()
                    except Exception as exc:
                        st.error(f"Import failed: {exc}")

        with st.form("add_student_form", clear_on_submit=True):
            col1, col2, col3, col_btn = st.columns([2, 3, 2, 1])
            roll_no = col1.text_input("Roll Number", placeholder="0133CI231002")
            name = col2.text_input("Name", placeholder="John Doe")
            attendance = col3.number_input("Attendance %", 0.0, 100.0, 50.0, 1.0)
            add_student = col_btn.form_submit_button("➕ Add")

            if add_student and roll_no and name:
                # Check for duplicates
                existing_rolls = {s["Roll Number"] for s in st.session_state["manual_students"]}
                if roll_no in existing_rolls:
                    st.error(f"Roll number {roll_no} already exists!")
                else:
                    st.session_state["manual_students"].append({
                        "Roll Number": roll_no,
                        "Name": name,
                        "Attendance Percentage": attendance,
                    })
                    st.success(f"Added {name} ({roll_no})")

        if st.session_state["manual_students"]:
            st.markdown("**Students Added:**")
            students_display = pd.DataFrame(st.session_state["manual_students"])
            col_table, col_delete = st.columns([0.95, 0.05])
            col_table.dataframe(students_display, use_container_width=True, hide_index=True)

            if col_delete.button("🗑️", key="delete_students", help="Clear all students"):
                st.session_state["manual_students"] = []
                st.rerun()

        st.divider()

        # ── Add Rooms ─────────────────────────────────────────────────────────
        st.subheader("🏫 Add Rooms")
        st.caption("Enter room details. Room number must be unique.")

        with st.form("add_room_form", clear_on_submit=True):
            col1, col2, col_btn = st.columns([2, 2, 1])
            room_no = col1.text_input("Room Number", placeholder="F-307")
            capacity = col2.number_input("Capacity", 1, 500, 40, 1)
            add_room = col_btn.form_submit_button("➕ Add")

            if add_room and room_no:
                existing_rooms = {r["Room Number"] for r in st.session_state["manual_rooms"]}
                if room_no in existing_rooms:
                    st.error(f"Room {room_no} already exists!")
                else:
                    st.session_state["manual_rooms"].append({
                        "Room Number": room_no,
                        "Capacity": int(capacity),
                    })
                    st.success(f"Added {room_no} (capacity {capacity})")

        if st.session_state["manual_rooms"]:
            st.markdown("**Rooms Added:**")
            rooms_display = pd.DataFrame(st.session_state["manual_rooms"])
            col_table, col_delete = st.columns([0.95, 0.05])
            col_table.dataframe(rooms_display, use_container_width=True, hide_index=True)

            if col_delete.button("🗑️", key="delete_rooms", help="Clear all rooms"):
                st.session_state["manual_rooms"] = []
                st.rerun()

        st.divider()

        # ── Add Exam Config (optional) ────────────────────────────────────────
        with st.expander("📅 Add Exam Config (Optional — Room, Subject, Date)", expanded=False):
            st.caption("Specify which subject will be held in which room and on which date.")

            with st.form("add_exam_config_form", clear_on_submit=True):
                col1, col2, col3, col4, col_btn = st.columns([1.5, 1.5, 1.8, 1.5, 0.8])
                room_no_cfg = col1.text_input("Room Number", placeholder="F-307", key="cfg_room")
                capacity_cfg = col2.number_input("Capacity", 1, 500, 40, 1, key="cfg_capacity")
                subject = col3.text_input("Subject", placeholder="Computer Networks", key="cfg_subject")
                date = col4.date_input("Date", key="cfg_date")
                add_cfg = col_btn.form_submit_button("➕ Add")

                if add_cfg and room_no_cfg and subject:
                    st.session_state["manual_exam_config"].append({
                        "Room Number": room_no_cfg,
                        "Capacity": int(capacity_cfg),
                        "Subject": subject,
                        "Date": str(date),
                    })
                    st.success(f"Added {room_no_cfg} - {subject} ({date})")

            if st.session_state["manual_exam_config"]:
                st.markdown("**Exam Config Added:**")
                cfg_display = pd.DataFrame(st.session_state["manual_exam_config"])
                col_table, col_delete = st.columns([0.95, 0.05])
                col_table.dataframe(cfg_display, use_container_width=True, hide_index=True)

                if col_delete.button("🗑️", key="delete_exam_config", help="Clear exam config"):
                    st.session_state["manual_exam_config"] = []
                    st.rerun()

        # Convert to DataFrames
        students_df = pd.DataFrame(st.session_state["manual_students"]) if st.session_state["manual_students"] else pd.DataFrame()
        rooms_df = pd.DataFrame(st.session_state["manual_rooms"]) if st.session_state["manual_rooms"] else pd.DataFrame()
        exam_config_df = pd.DataFrame(st.session_state["manual_exam_config"]) if st.session_state["manual_exam_config"] else None

    st.divider()

    # ── Exam Timetable (section-wise attendance sheet columns) ─────────────────
    with st.expander("📅 Exam Timetable — for section-wise attendance sheets (optional)", expanded=False):
        st.caption(
            "Add each exam subject with its date. The section-wise attendance sheet will show "
            "these as column headers (dates merged across subjects on the same day), "
            "matching the SIRT format."
        )
        with st.form("add_timetable_form", clear_on_submit=True):
            tc1, tc2, tc_btn = st.columns([3, 2, 1])
            tt_subject = tc1.text_input("Subject code / name", placeholder="CSIT-601 SE")
            tt_date = tc2.text_input("Exam date", placeholder="06-Apr-26")
            add_tt = tc_btn.form_submit_button("➕ Add")

            if add_tt and tt_subject:
                st.session_state["manual_timetable"].append({
                    "subject": tt_subject.strip(),
                    "date": tt_date.strip(),
                })
                st.success(f"Added: {tt_subject.strip()} — {tt_date.strip()}")

        if st.session_state["manual_timetable"]:
            st.markdown("**Timetable:**")
            tt_df = pd.DataFrame(st.session_state["manual_timetable"])
            tt_df.index = tt_df.index + 1
            col_tt, col_tt_del = st.columns([0.95, 0.05])
            col_tt.dataframe(tt_df, use_container_width=True)
            if col_tt_del.button("🗑️", key="del_timetable", help="Clear timetable"):
                st.session_state["manual_timetable"] = []
                st.rerun()

    st.divider()
    st.subheader("⚙️ Options")
    o1, o2, o3, o4, o5 = st.columns(5)
    attendance_cutoff = o1.number_input("Attendance cutoff (%)", 0.0, 100.0, 40.0, 1.0)
    shuffle = o2.checkbox("Shuffle students")
    seed = o3.number_input("Seed", 0, 99999, 42, 1)
    alt_seats = o4.checkbox("Alternate seats")
    export_pdf = o5.checkbox("Export PDF")

    if not st.button("🎯 Generate Seating Plan", type="primary", use_container_width=True):
        return

    # ── Validation ────────────────────────────────────────────────────────────
    if students_df.empty:
        st.error("❌ No students. Add students above and try again.")
        return
    if rooms_df.empty:
        st.error("❌ No rooms. Add rooms above and try again.")
        return

    run_id = uuid4().hex[:8]
    base_dir = Path("web_runs") / run_id
    input_dir = base_dir / "input"
    output_dir = base_dir / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Save DataFrames to Excel
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
            export_pdf_file=export_pdf,
        )
        result = run_seating_system(config)

    except (DataValidationError, FileNotFoundError) as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        st.error(f"Unexpected error: {exc}")
        return

    st.success("Seating plan generated!")

    m = st.columns(4)
    m[0].metric("Total Students", result.summary.total_students)
    m[1].metric("Eligible", result.summary.eligible_students)
    m[2].metric("Allocated", result.summary.allocated_students)
    m[3].metric("Debarred (Not Eligible)", result.summary.not_eligible_students)

    # Re-attach Section/Branch to room allocations for SIRT output
    raw_students = (
        pd.read_excel(student_path)
        if student_path.suffix in {".xlsx", ".xls"}
        else pd.read_csv(student_path)
    )
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
        room_allocations_enriched, output_dir,
        institute=info["institute"], department=info["department"],
        exam_title=info["exam_title"], semester=info["semester"],
    )
    sirt_debarred_path = export_sirt_debarred_excel(
        not_eligible_df, output_dir,
        institute=info["institute"], department=info["department"],
        exam_title=info["exam_title"], attendance_cutoff=float(attendance_cutoff),
    )
    # Section-wise attendance with timetable columns (if timetable was provided)
    timetable = st.session_state.get("manual_timetable", [])
    sirt_att_path = export_sirt_attendance_sheets_excel(
        room_allocations_enriched, output_dir,
        institute=info["institute"], department=info["department"],
        exam_title=info["exam_title"],
        timetable=timetable,
    )
    sirt_sec_att_path = export_sirt_section_attendance_excel(
        room_allocations_enriched, output_dir,
        timetable=timetable,
        institute=info["institute"], department=info["department"],
        exam_title=info["exam_title"], semester=info["semester"],
    )

    st.subheader("SIRT-Formatted Downloads")
    d1, d2, d3, d4 = st.columns(4)
    d1.download_button(
        "⬇ Main Seating Plan (SIRT format)",
        data=sirt_seating_path.read_bytes(),
        file_name="SIRT_Main_Seating.xlsx", mime=XLSX_MIME,
    )
    d2.download_button(
        "⬇ Debarred List (SIRT format)",
        data=sirt_debarred_path.read_bytes(),
        file_name="SIRT_Debarred_List.xlsx", mime=XLSX_MIME,
    )
    d3.download_button(
        "⬇ Attendance Sheets (room-wise)",
        data=sirt_att_path.read_bytes(),
        file_name="SIRT_Attendance_Sheets.xlsx", mime=XLSX_MIME,
    )
    d4.download_button(
        "⬇ Section Attendance (with subjects)",
        data=sirt_sec_att_path.read_bytes(),
        file_name="SIRT_Section_Attendance.xlsx", mime=XLSX_MIME,
        help="Section-wise sheets with date/subject columns. Add subjects via 'Exam Timetable' above.",
    )

    with st.expander("Other generated files"):
        for file_name in result.generated_files:
            fp = Path(file_name)
            if not fp.exists():
                continue
            s = fp.suffix.lower()
            mime = "text/plain" if s == ".txt" else XLSX_MIME if s == ".xlsx" else "application/pdf" if s == ".pdf" else "application/octet-stream"
            st.download_button(
                label=f"⬇ {fp.name}",
                data=fp.read_bytes(),
                file_name=fp.name,
                mime=mime,
                key=f"dl_{fp.name}_{run_id}",
            )


def main() -> None:
    st.set_page_config(
        page_title="SIRT Exam Seating System",
        page_icon="🪑",
        layout="wide",
    )
    st.title("SIRT — Automatic Exam Seating Arrangement")

    info = _sidebar_institute_info()

    tab_generate(info)


if __name__ == "__main__":
    main()
