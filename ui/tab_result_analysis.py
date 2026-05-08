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
    section_alias = {"section", "sec", "group", "batch"}

    detected: dict[str, str | None] = {"roll": None, "name": None, "section": None}
    for col in columns:
        n = _norm_text(col)
        if detected["roll"] is None and n in roll_alias:
            detected["roll"] = col
        if detected["name"] is None and n in name_alias:
            detected["name"] = col
        if detected["section"] is None and n in section_alias:
            detected["section"] = col

    return detected


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def _to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "Template") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return buf.getvalue()


def _clean_text_series(series: pd.Series) -> pd.Series:
    cleaned = series.fillna("").astype(str).str.strip()
    return cleaned.where(~cleaned.str.lower().isin({"nan", "none", "nat"}), "")


def _numeric_with_invalid_mask(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    cleaned = _clean_text_series(series)
    numeric = pd.to_numeric(series, errors="coerce")
    invalid_mask = (cleaned != "") & numeric.isna()
    return numeric, invalid_mask


def _safe_sheet_name(section_name: str, used_names: set[str]) -> str:
    invalid = set('[]:*?/\\')
    cleaned = "".join("_" if ch in invalid else ch for ch in (section_name or "").strip())
    cleaned = cleaned[:31].strip()
    if not cleaned:
        cleaned = "Section"

    base = cleaned
    counter = 1
    while cleaned in used_names:
        suffix = f"_{counter}"
        cleaned = f"{base[:31 - len(suffix)]}{suffix}"
        counter += 1
    used_names.add(cleaned)
    return cleaned


def _write_section_sheet(
    wb,
    ws,
    work: pd.DataFrame,
    subjects: list[dict],   # [{"subject": str, "faculty": str, "col": str}]
    institute: str,
    department: str,
    exam_title: str,
    section: str,
    pass_threshold: float,
    max_marks_per_subject: float,
):
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
    summary_title_fmt = wb.add_format({
        "bold": True,
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "bg_color": "#F2F2F2",
    })
    summary_key_fmt = wb.add_format({
        "bold": True,
        "align": "left",
        "valign": "vcenter",
        "border": 1,
        "bg_color": "#F2F2F2",
    })
    pct_fmt = wb.add_format({
        "border": 1,
        "align": "center",
        "valign": "vcenter",
        "num_format": "0.00",
    })

    subject_start_col = 3
    subject_end_col = subject_start_col + len(subjects) - 1
    total_col = subject_end_col + 1
    percentage_col = total_col + 1
    pass_fail_col = percentage_col + 1
    last_col = pass_fail_col

    ws.set_column(0, 0, 6)
    ws.set_column(1, 1, 30)
    ws.set_column(2, 2, 22)
    ws.set_column(3, subject_end_col, 20)
    ws.set_column(total_col, pass_fail_col, 16)

    # 4 merged title rows
    for row_i, (text, row_h) in enumerate([
        (institute, 20),
        (department, 18),
        (exam_title, 16),
        (section, 16),
    ]):
        ws.set_row(row_i, row_h)
        ws.merge_range(row_i, 0, row_i, last_col, text, hdr_fmt)

    # Two-row header: row4 dates, row5 subject/faculty with totals at right.
    ws.set_row(4, 20)
    ws.set_row(5, 20)
    ws.merge_range(4, 0, 5, 0, "S.NO", col_fmt)
    ws.merge_range(4, 1, 5, 1, "Student Name", col_fmt)
    ws.merge_range(4, 2, 5, 2, "Roll Number", col_fmt)
    for i, subj in enumerate(subjects):
        c = subject_start_col + i
        subject_line = subj["subject"]
        if subj.get("faculty"):
            subject_line = f"{subject_line}\nTeacher: {subj['faculty']}"
        ws.write(4, c, subj.get("exam_date", ""), col_fmt)
        ws.write(5, c, subject_line, col_fmt)

    ws.merge_range(4, total_col, 5, total_col, "Total", col_fmt)
    ws.merge_range(4, percentage_col, 5, percentage_col, "% Percentage", col_fmt)
    ws.merge_range(4, pass_fail_col, 5, pass_fail_col, "Pass/Fail", col_fmt)

    # Data rows
    status_values: list[str] = []
    for row_i, (_, row) in enumerate(work.iterrows()):
        r = 6 + row_i
        ws.write(r, 0, row_i + 1, cell_fmt)
        ws.write(r, 1, row.get("Name", ""), cell_fmt)
        ws.write(r, 2, row.get("Roll Number", ""), cell_fmt)
        total_marks = 0.0
        appeared_subjects = 0
        failed_in_any_subject = False
        for c_i, subj in enumerate(subjects):
            raw = row.get(subj["col"])
            num = None
            if pd.notna(raw):
                coerced = pd.to_numeric(raw, errors="coerce")
                if pd.notna(coerced):
                    num = float(coerced)
            # Treat missing/non-numeric subject marks as failed for strict per-subject eligibility.
            fmt = fail_fmt if (num is None or num < pass_threshold) else cell_fmt
            if num is not None:
                total_marks += num
                appeared_subjects += 1
                if num < pass_threshold:
                    failed_in_any_subject = True
            if pd.isna(raw):
                display_value = ""
            else:
                display_value = str(raw).strip()
                if display_value.lower() in {"nan", "none", "nat"}:
                    display_value = ""
            ws.write(r, subject_start_col + c_i, display_value, fmt)

        percentage = 0.0
        if appeared_subjects > 0 and max_marks_per_subject > 0:
            percentage = round((total_marks / (appeared_subjects * max_marks_per_subject)) * 100)

        status = "FAIL" if (appeared_subjects < len(subjects) or failed_in_any_subject) else "PASS"
        status_fmt = fail_fmt if status == "FAIL" else cell_fmt
        status_values.append(status)

        ws.write(r, total_col, round(total_marks), cell_fmt)
        ws.write(r, percentage_col, percentage, cell_fmt)
        ws.write(r, pass_fail_col, status, status_fmt)

    work["__status__"] = status_values

    # Bottom overall result matrix (subject-wise + total)
    data_end_row = 6 + len(work) - 1
    summary_start = data_end_row + 2
    matrix_label_col = 2
    matrix_value_start_col = 3

    ws.merge_range(
        summary_start,
        matrix_value_start_col,
        summary_start,
        pass_fail_col,
        "Overall Result",
        summary_title_fmt,
    )

    subject_labels = [s["subject"] for s in subjects] + ["Total"]
    for idx, label in enumerate(subject_labels):
        ws.write(summary_start + 1, matrix_value_start_col + idx, label, col_fmt)

    metric_labels = [
        "Total Students",
        "Total Absent",
        "Total Present in Exam",
        "Total Student Passed",
        "Percentage",
    ]

    subject_stats = []
    for subj in subjects:
        marks = pd.to_numeric(work[subj["col"]], errors="coerce") if subj["col"] in work.columns else pd.Series(dtype=float)
        total_students = len(work)
        absent = int(marks.isna().sum())
        present = total_students - absent
        passed = int((marks >= pass_threshold).sum())
        pct = (passed / present * 100.0) if present > 0 else 0.0
        subject_stats.append((total_students, absent, present, passed, pct))

    # Overall totals across students
    total_students = len(work)
    any_mark = pd.Series(False, index=work.index)
    for subj in subjects:
        if subj["col"] in work.columns:
            any_mark = any_mark | pd.to_numeric(work[subj["col"]], errors="coerce").notna()
    overall_absent = int((~any_mark).sum())
    overall_present = total_students - overall_absent
    overall_passed = int((work["__status__"] if "__status__" in work.columns else pd.Series(dtype=str)).eq("PASS").sum())
    overall_pct = (overall_passed / overall_present * 100.0) if overall_present > 0 else 0.0

    totals_tuple = (total_students, overall_absent, overall_present, overall_passed, overall_pct)

    for r_offset, metric in enumerate(metric_labels):
        row_no = summary_start + 2 + r_offset
        ws.write(row_no, matrix_label_col, metric, summary_key_fmt)
        for c_offset, values in enumerate(subject_stats + [totals_tuple]):
            val = values[r_offset]
            if metric == "Percentage":
                ws.write(row_no, matrix_value_start_col + c_offset, float(val), pct_fmt)
            else:
                ws.write(row_no, matrix_value_start_col + c_offset, int(val), cell_fmt)


def _build_section_excel(
    work: pd.DataFrame,
    subjects: list[dict],
    institute: str,
    department: str,
    exam_title: str,
    section: str,
    pass_threshold: float,
    max_marks_per_subject: float,
) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        wb = writer.book
        used_names: set[str] = set()
        section_series = _clean_text_series(work["Section"]) if "Section" in work.columns else pd.Series("", index=work.index)
        fallback_section = section.strip() if section.strip() else "Section"
        effective_section = section_series.where(section_series != "", fallback_section)

        has_section_col = "Section" in work.columns and effective_section.ne("").any()
        if has_section_col:
            grouped = [
                (sec_name, sec_df.reset_index(drop=True))
                for sec_name, sec_df in work.groupby(effective_section, sort=True)
            ]
        else:
            default_name = fallback_section
            grouped = [(default_name, work.reset_index(drop=True))]

        for sec_name, sec_work in grouped:
            sheet_name = _safe_sheet_name(sec_name, used_names)
            ws = wb.add_worksheet(sheet_name)
            section_heading = f"Section: {sec_name}" if sec_name else f"Section: {sheet_name}"
            _write_section_sheet(
                wb,
                ws,
                sec_work.copy(),
                subjects,
                institute,
                department,
                exam_title,
                section_heading,
                pass_threshold,
                max_marks_per_subject,
            )

    return buf.getvalue()


def _build_summary_excel(summary_df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
    return buf.getvalue()


def render_tab_result_analysis() -> None:
    st.header("Result Analysis")
    st.caption("Upload result file, add subjects with faculty names, and export a styled section-wise workbook.")

    t1, t2 = st.columns(2)
    t1.download_button(
        "Download Result Analysis Template (Excel)",
        data=_to_xlsx_bytes(RESULT_TEMPLATE_DF, sheet_name="ResultTemplate"),
        file_name="result_analysis_template.xlsx",
        mime=XLSX_MIME,
        use_container_width=True,
    )
    t2.download_button(
        "Download Result Analysis Template (CSV)",
        data=_to_csv_bytes(RESULT_TEMPLATE_DF),
        file_name="result_analysis_template.csv",
        mime=CSV_MIME,
        use_container_width=True,
    )

    st.info(
        "How to upload Excel: 1) Download template. 2) Fill Roll/Name and subject marks. "
        "3) Keep column headers unchanged. 4) Upload .xlsx/.xls. 5) Select sheet and map Roll, Name, Section. "
        "6) Add subjects and faculty, then click Generate Result Analysis."
    )

    # ── Header Information ─────────────────────────────────────────────────────
    st.subheader("Header Information")
    hi1, hi2 = st.columns(2)
    institute  = hi1.text_input("Institute Name", value="SAGAR INSTITUTE OF RESEARCH & TECHNOLOGY", key="ra_institute")
    department = hi2.text_input("Department",     value="DEPARTMENT OF CSIT",                        key="ra_department")
    hi3, hi4 = st.columns(2)
    exam_title = hi3.text_input("Exam Title",  value="I MID SEM EXAMINATION (JAN-JUN 2026)", key="ra_exam_title")
    section    = hi4.text_input("Section",     placeholder="CSIT- 6th Sem - CSIT--A",        key="ra_section")

    # ── File Upload ────────────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        "Upload result file (.xlsx / .xls / .csv)",
        type=["xlsx", "xls", "csv"],
        key="result_analysis_upload",
    )

    if uploaded is None:
        st.info("Upload a file to continue.")
        return

    selected_sheet = None
    if uploaded.name.lower().endswith((".xlsx", ".xls")):
        xl = pd.ExcelFile(uploaded)
        selected_sheet = st.selectbox("Select sheet", xl.sheet_names, key="result_analysis_sheet")
        uploaded.seek(0)

    source_key = f"{uploaded.name}::{selected_sheet or ''}"
    previous_source_key = st.session_state.get("ra_source_key")
    if previous_source_key is None:
        st.session_state["ra_source_key"] = source_key
    elif previous_source_key != source_key:
        st.session_state["ra_source_key"] = source_key
        st.session_state["ra_subjects"] = []
        st.warning("File/sheet changed. Subject mapping has been reset to avoid inaccurate output.")

    try:
        df = _read_uploaded_table(uploaded, selected_sheet=selected_sheet)
    except Exception as exc:
        st.error(f"Failed to read file: {exc}")
        return

    if df.empty:
        st.error("Uploaded file has no rows.")
        return

    df.columns = [str(c).strip() for c in df.columns]
    st.subheader("Preview")
    st.dataframe(df.head(10), use_container_width=True)

    # ── Column Mapping ─────────────────────────────────────────────────────────
    st.subheader("Column Mapping")
    detected = _detect_columns(list(df.columns))
    all_cols = [""] + list(df.columns)
    cm1, cm2, cm3 = st.columns(3)
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
    section_col = cm3.selectbox(
        "Section column (optional)", all_cols,
        index=all_cols.index(detected["section"]) if detected["section"] in all_cols else 0,
        key="ra_section_col",
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
        s_date = st.text_input("Exam Date (optional)", placeholder="e.g. 06-Apr-26")
        if add_subj:
            if not s_code.strip() or not s_col:
                st.error("Subject Code and Marks Column are required.")
            elif any(existing.get("col") == s_col for existing in st.session_state["ra_subjects"]):
                st.error("This marks column is already mapped. Choose a different column.")
            else:
                st.session_state["ra_subjects"].append(
                    {
                        "subject": s_code.strip(),
                        "faculty": s_faculty.strip(),
                        "col": s_col,
                        "exam_date": s_date.strip(),
                    }
                )

    if st.session_state["ra_subjects"]:
        subj_preview = pd.DataFrame(st.session_state["ra_subjects"])
        subj_preview.index = range(1, len(subj_preview) + 1)
        st.dataframe(
            subj_preview.rename(
                columns={
                    "subject": "Subject",
                    "faculty": "Faculty",
                    "col": "File Column",
                    "exam_date": "Exam Date",
                }
            ),
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
    pass_threshold = st.number_input("Pass Marks", min_value=0.0, max_value=1000.0, value=10.0, step=1.0)
    max_marks_per_subject = st.number_input(
        "Max Marks Per Subject",
        min_value=1.0,
        max_value=1000.0,
        value=20.0,
        step=1.0,
    )

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
    missing_subject_cols = sorted({subj["col"] for subj in subjects if subj["col"] not in df.columns})
    if missing_subject_cols:
        st.error(f"These mapped subject columns are missing in current file/sheet: {', '.join(missing_subject_cols)}")
        return

    # ── Build work dataframe ───────────────────────────────────────────────────
    work = pd.DataFrame()
    work["Roll Number"] = _clean_text_series(df[roll_col]) if roll_col else ""
    work["Name"]        = _clean_text_series(df[name_col]) if name_col else ""
    if section_col:
        work["Section"] = _clean_text_series(df[section_col])
    else:
        work["Section"] = section.strip()
    for subj in subjects:
        if subj["col"] in df.columns:
            work[subj["col"]] = df[subj["col"]]

    # Remove entirely blank rows to avoid inflated counts and empty entries in exports.
    has_subject_data = pd.Series(False, index=work.index)
    for subj in subjects:
        has_subject_data = has_subject_data | _clean_text_series(work[subj["col"]]).ne("")
    keep_mask = work["Roll Number"].ne("") | work["Name"].ne("") | has_subject_data
    work = work[keep_mask].reset_index(drop=True)
    if work.empty:
        st.error("No usable student rows found after removing blank rows.")
        return

    invalid_rows = []
    for subj in subjects:
        _, invalid_mask = _numeric_with_invalid_mask(work[subj["col"]])
        invalid_count = int(invalid_mask.sum())
        if invalid_count > 0:
            invalid_rows.append({
                "Subject": subj["subject"],
                "Column": subj["col"],
                "Invalid Marks": invalid_count,
            })
    if invalid_rows:
        st.warning("Some marks are non-numeric and will be treated as absent/failed in strict evaluation.")
        st.dataframe(pd.DataFrame(invalid_rows), use_container_width=True, hide_index=True)

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
        max_marks_per_subject,
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

