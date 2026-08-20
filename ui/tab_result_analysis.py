from __future__ import annotations

import io

import pandas as pd
import streamlit as st

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CSV_MIME  = "text/csv"

RESULT_TEMPLATE_DF = pd.DataFrame(
    [
        {"Board EnrollNo": "0133CI241003", "Student Name": "AADITYA KUMAR PANDEY", "Subject1_Marks": 20, "Subject2_Marks": 15},
        {"Board EnrollNo": "0133CI241004", "Student Name": "AAKASH BANSAL",         "Subject1_Marks": 18, "Subject2_Marks": 19},
        {"Board EnrollNo": "0133CI241005", "Student Name": "AARTI CHOUDHARY",       "Subject1_Marks": 14, "Subject2_Marks": 17},
    ]
)


def _norm_text(value: object) -> str:
    return "".join(ch for ch in str(value).strip().lower() if ch.isalnum())


def _read_uploaded_table(uploaded_file, selected_sheet: str | None = None) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)

    if name.endswith((".xlsx", ".xls")):
        if selected_sheet:
            return pd.read_excel(uploaded_file, sheet_name=selected_sheet)
        return pd.read_excel(uploaded_file)

    raise ValueError("Unsupported file type. Use .xlsx, .xls, or .csv")


def _detect_columns(columns: list[str]) -> dict[str, str | None]:
    roll_alias = {
        "roll", "rollno", "rollnumber", "enrollment", "enrollno",
        "enrollmentno", "boardenrollno", "boardenroll",
    }
    name_alias = {"name", "studentname", "student"}

    detected: dict[str, str | None] = {"roll": None, "name": None}
    for col in columns:
        n = _norm_text(col)
        if detected["roll"] is None and n in roll_alias:
            detected["roll"] = col
        if detected["name"] is None and n in name_alias:
            detected["name"] = col

    return detected


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def _build_section_excel(
    work: pd.DataFrame,
    subjects: list[dict],   # [{"subject": str, "faculty": str, "col": str}]
    institute: str,
    department: str,
    exam_title: str,
    section: str,
    pass_threshold: float,
) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        wb = writer.book
        ws = wb.add_worksheet("Result")

        hdr_fmt = wb.add_format({
            "bold": True, "align": "center", "valign": "vcenter",
            "font_size": 12, "border": 1,
        })
        col_fmt = wb.add_format({
            "bold": True, "align": "center", "valign": "vcenter",
            "border": 1, "bg_color": "#D9E1F2", "text_wrap": True,
        })
        cell_fmt = wb.add_format({"border": 1, "align": "center", "valign": "vcenter"})
        fail_fmt = wb.add_format({
            "border": 1, "align": "center", "valign": "vcenter", "font_color": "#FF0000",
        })

        last_col = 2 + len(subjects)  # 0=SNO, 1=EnrollNo, 2=Name, 3..=subjects

        ws.set_column(0, 0, 6)
        ws.set_column(1, 1, 20)
        ws.set_column(2, 2, 30)
        ws.set_column(3, last_col, 16)

        # 4 merged title rows
        for row_i, (text, row_h) in enumerate([
            (institute,  20),
            (department, 18),
            (exam_title, 16),
            (section,    16),
        ]):
            ws.set_row(row_i, row_h)
            ws.merge_range(row_i, 0, row_i, last_col, text, hdr_fmt)

        # Two-row column header: S.NO / EnrollNo / Name merged; faculty on row4, subject on row5
        ws.set_row(4, 20)
        ws.set_row(5, 18)
        ws.merge_range(4, 0, 5, 0, "S.NO",           col_fmt)
        ws.merge_range(4, 1, 5, 1, "Board EnrollNo",  col_fmt)
        ws.merge_range(4, 2, 5, 2, "Student Name",    col_fmt)
        for i, subj in enumerate(subjects):
            ws.write(4, 3 + i, subj["faculty"],  col_fmt)
            ws.write(5, 3 + i, subj["subject"], col_fmt)

        # Data rows
        for row_i, (_, row) in enumerate(work.iterrows()):
            r = 6 + row_i
            ws.write(r, 0, row_i + 1,                 cell_fmt)
            ws.write(r, 1, row.get("Roll Number", ""), cell_fmt)
            ws.write(r, 2, row.get("Name", ""),        cell_fmt)
            for c_i, subj in enumerate(subjects):
                raw = row.get(subj["col"])
                num = pd.to_numeric(raw, errors="coerce") if pd.notna(raw) else None
                fmt = fail_fmt if (num is not None and float(num) < pass_threshold) else cell_fmt
                ws.write(r, 3 + c_i, "" if (raw is None or (isinstance(raw, float) and pd.isna(raw))) else raw, fmt)

    return buf.getvalue()


def _build_summary_excel(summary_df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
    return buf.getvalue()


def render_tab_result_analysis() -> None:
    st.header("Result Analysis")
    st.caption("Upload result file, add subjects with faculty names, and export a styled section-wise sheet.")

    st.download_button(
        "Download Result Analysis Template (CSV)",
        data=_to_csv_bytes(RESULT_TEMPLATE_DF),
        file_name="result_analysis_template.csv",
        mime=CSV_MIME,
        use_container_width=True,
    )

    # ── Data Source Selection ─────────────────────────────────────────────────
    st.subheader("Data Source")
    use_saved_data = st.checkbox(
        "Use saved student data from Data & Marks Management",
        help="Toggle to use student data saved in the Data & Marks Management tab instead of uploading a file"
    )

    # Initialize session state for data management functions if needed
    if "saved_students" not in st.session_state:
        st.session_state["saved_students"] = pd.DataFrame()

    # Handle data loading based on selection
    if use_saved_data:
        # Use saved student data
        df = st.session_state["saved_students"].copy()
        if df.empty:
            st.warning("⚠️ No student data saved yet. Please go to Data & Marks Management tab to save student data first.")
            st.info("💡 Save your student data in the Data & Marks Management tab, then return here and toggle this option.")
            return
        else:
            # Validate required columns
            required_cols = {"Roll Number", "Name"}
            if not required_cols.issubset(set(df.columns)):
                missing = required_cols - set(df.columns)
                st.error(f"❌ Saved student data missing required columns: {', '.join(missing)}")
                st.info("Please re-save valid student data in the Data & Marks Management tab.")
                return
            else:
                st.success(f"✅ Using saved student data: {len(df)} students loaded")
                st.dataframe(df.head(10), use_container_width=True)
                # Normalize column names for consistency
                df.columns = [c.strip() for c in df.columns]

                # For saved data, we know the columns
                roll_col = "Roll Number"
                name_col = "Name"
                # Set a flag to skip file upload processing
                is_saved_data = True
    else:
        # ── File Upload ────────────────────────────────────────────────────────────
        uploaded = st.file_uploader(
            "Upload result file (.xlsx / .xls / .csv)",
            type=["xlsx", "xls", "csv"],
            key="result_analysis_upload",
        )

        if uploaded is None:
            st.info("Upload a file to continue.")
            return

        try:
            df = _read_uploaded_table(uploaded)
        except Exception:
            st.error("Failed to read the uploaded file.")
            return

        if df.empty:
            st.error("Uploaded file has no rows.")
            return

        df.columns = [str(c).strip() for c in df.columns]
        st.subheader("Preview")
        st.dataframe(df.head(10), use_container_width=True)

        selected_sheet = None
        if uploaded.name.lower().endswith((".xlsx", ".xls")):
            xl = pd.ExcelFile(uploaded)
            selected_sheet = st.selectbox("Select sheet", xl.sheet_names, key="result_analysis_sheet")
            uploaded.seek(0)

        try:
            df = _read_uploaded_table(uploaded, selected_sheet=selected_sheet)
        except Exception:
            st.error("Failed to read the uploaded file.")
            return

        if df.empty:
            st.error("Uploaded file has no rows.")
            return

        df.columns = [str(c).strip() for c in df.columns]
        st.subheader("Preview (after sheet selection)")
        st.dataframe(df.head(10), use_container_width=True)
        # Set flag for file upload path
        is_saved_data = False

    # ── Column Mapping ─────────────────────────────────────────────────────────
    st.subheader("Column Mapping")
    if use_saved_data:
        # For saved data, we already know the columns
        st.info("Using saved student data: Roll Number → Board EnrollNo, Name → Student Name")
        roll_col = "Roll Number"
        name_col = "Name"
        all_cols = ["Roll Number", "Name"] + [c for c in df.columns if c not in ["Roll Number", "Name"]]
    else:
        # For uploaded files, detect columns
        detected = _detect_columns(list(df.columns))
        all_cols  = [""] + list(df.columns)
        cm1, cm2 = st.columns(2)
        roll_col = cm1.selectbox(
            "Board EnrollNo / Roll column", all_cols,
            index=all_cols.index(detected["roll"]) if detected["roll"] in all_cols else 0,
            key="ra_roll_col",
        )
        name_col = cm2.selectbox(
            "Student Name column", all_cols,
            index=all_cols.index(detected["name"]) if detected["name"] in all_cols else 0,
            key="ra_name_col",
        )

    # ── Subjects ───────────────────────────────────────────────────────────────
    st.subheader("Subjects")
    if "ra_subjects" not in st.session_state:
        st.session_state["ra_subjects"] = []

    with st.form("ra_add_subject_form", clear_on_submit=True):
        fs1, fs2, fs3, fs4 = st.columns([2, 2, 2, 1])
        s_code    = fs1.text_input("Subject Code / Name", placeholder="e.g. CN, CSIT-601")
        s_faculty = fs2.text_input("Faculty Name",        placeholder="Prof. A. Sharma")
        s_col     = fs3.selectbox("Marks Column (from file)", all_cols)
        add_subj  = fs4.form_submit_button("Add", use_container_width=True)
        if add_subj:
            if not s_code.strip() or not s_col:
                st.error("Subject Code and Marks Column are required.")
            else:
                st.session_state["ra_subjects"].append(
                    {"subject": s_code.strip(), "faculty": s_faculty.strip(), "col": s_col}
                )

    if st.session_state["ra_subjects"]:
        subj_preview = pd.DataFrame(st.session_state["ra_subjects"])
        subj_preview.index = range(1, len(subj_preview) + 1)
        st.dataframe(
            subj_preview.rename(columns={"subject": "Subject", "faculty": "Faculty", "col": "File Column"}),
            use_container_width=True,
        )
        remove_idx = st.number_input(
            "Remove subject by row #", min_value=0,
            max_value=len(st.session_state["ra_subjects"]), value=0, step=1,
            key="ra_remove_subj",
        )
        if st.button("Remove", key="ra_remove_btn") and remove_idx > 0:
            st.session_state["ra_subjects"].pop(remove_idx - 1)
            st.rerun()

    # ── Settings ───────────────────────────────────────────────────────────────
    pass_threshold = st.number_input("Pass Marks", min_value=0.0, max_value=1000.0, value=40.0, step=1.0)

    if not st.button("Generate Result Analysis", type="primary", use_container_width=True):
        return

    # ── Validation ─────────────────────────────────────────────────────────────
    if not roll_col and not name_col:
        st.error("Please select at least one of Roll Number or Student Name column.")
        return

    if not st.session_state["ra_subjects"]:
        st.error("Please add at least one subject.")
        return

    subjects = st.session_state["ra_subjects"]

    # ── Build work dataframe ───────────────────────────────────────────────────
    work = pd.DataFrame()
    work["Roll Number"] = df[roll_col].astype(str).str.strip() if roll_col else ""
    work["Name"]        = df[name_col].astype(str).str.strip() if name_col else ""
    for subj in subjects:
        if subj["col"] in df.columns:
            work[subj["col"]] = df[subj["col"]]

    # ── Per-subject summary ────────────────────────────────────────────────────
    summary_rows = []
    for subj in subjects:
        col    = subj["col"]
        marks  = pd.to_numeric(work[col], errors="coerce") if col in work.columns else pd.Series(dtype=float)
        appeared = int(marks.notna().sum())
        passed   = int((marks >= pass_threshold).sum())
        avg      = round(float(marks.dropna().mean()), 2) if appeared else 0.0
        pass_pct = round(passed / appeared * 100, 2) if appeared else 0.0
        top_idx  = marks.idxmax() if appeared else None
        topper   = work.loc[top_idx, "Name"] if top_idx is not None else "N/A"
        summary_rows.append({
            "Subject":       subj["subject"],
            "Faculty":       subj["faculty"],
            "Total":         len(work),
            "Appeared":      appeared,
            "Passed":        passed,
            "Failed":        appeared - passed,
            "Pass %":        pass_pct,
            "Average Marks": avg,
            "Topper":        topper,
        })

    summary_df = pd.DataFrame(summary_rows)

    # ── Generate styled section-wise Excel ────────────────────────────────────
    section_excel = _build_section_excel(
        work, subjects,
        institute.strip(), department.strip(), exam_title.strip(), section.strip(),
        pass_threshold,
    )

    # ── Display ────────────────────────────────────────────────────────────────
    st.subheader("Dashboard")
    total = len(work)
    tot_appeared = sum(r["Appeared"] for r in summary_rows)
    tot_passed   = sum(r["Passed"]   for r in summary_rows)
    overall_pct  = round(tot_passed / tot_appeared * 100, 2) if tot_appeared else 0.0
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Total Students", total)
    d2.metric("Subjects",       len(subjects))
    d3.metric("Avg Pass %",     f"{overall_pct:.2f}")
    d4.metric("Pass Threshold", int(pass_threshold))

    st.subheader("Subject-wise Summary")
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    st.subheader("Export")
    c1, c2 = st.columns(2)
    c1.download_button(
        "Download Section-wise Excel",
        data=section_excel,
        file_name="result_section_wise.xlsx",
        mime=XLSX_MIME,
        use_container_width=True,
    )
    c2.download_button(
        "Download Summary CSV",
        data=_to_csv_bytes(summary_df),
        file_name="result_summary.csv",
        mime=CSV_MIME,
        use_container_width=True,
    )

