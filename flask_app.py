"""
Flask web app for the Automatic Exam Seating Arrangement System.

Routes:
  GET  /                  – Home (redirect to /generate)
  GET  /convert           – Upload result workbook & extract students/rooms
  POST /convert           – Process uploaded result workbook
  GET  /generate          – Seating plan form
  POST /generate          – Generate seating plan & return download links
  GET  /result_analysis   – Result analysis & statistics
  POST /result_analysis   – Process results file for analysis
  GET  /download/<run_id>/<filename>  – Download a generated file
  GET  /download_analysis/<run_id>/<report_type>  – Download analysis report
  GET  /template/<name>   – Download an input template
"""
from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path
from uuid import uuid4

import pandas as pd
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from convert_result_to_students import convert_result_file, extract_timetable_from_workbook
from exam_seating.io_utils import DataValidationError
from exam_seating.result_analyzer import ResultDatabase
from exam_seating.service import SeatingConfig, run_seating_system
from exam_seating.sirt_exporters import (
    export_sirt_debarred_excel,
    export_sirt_main_seating_excel,
    export_sirt_section_attendance_excel,
)

app = Flask(__name__)
app.secret_key = os.urandom(24)

WEB_RUNS = Path("web_runs")
WEB_RUNS.mkdir(exist_ok=True)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def _make_students_template() -> bytes:
    df = pd.DataFrame([
        {"Roll Number": "0133CI231002", "Name": "AARBI DHAKAD",       "Attendance Percentage": 82},
        {"Roll Number": "0133CI231008", "Name": "ABHISHEK KUMAR",     "Attendance Percentage": 61},
        {"Roll Number": "0133CI231014", "Name": "ADITYA KUMAR SHAH",  "Attendance Percentage": 75},
        {"Roll Number": "0133CI231024", "Name": "AMANJEET SINGH",     "Attendance Percentage": 38},
        {"Roll Number": "0133CI231035", "Name": "ANJALI SHRIVASTAVA", "Attendance Percentage": 55},
    ])
    return _df_to_excel_bytes(df)


def _make_rooms_template() -> bytes:
    df = pd.DataFrame([
        {"Room Number": "F-307", "Capacity": 40},
        {"Room Number": "F-308", "Capacity": 40},
        {"Room Number": "F-309", "Capacity": 40},
        {"Room Number": "F-310", "Capacity": 30},
    ])
    return _df_to_excel_bytes(df)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("generate"))


@app.route("/convert", methods=["GET", "POST"])
def convert():
    if request.method == "GET":
        return render_template("convert.html")

    # POST – process uploaded result workbook
    if "result_file" not in request.files or request.files["result_file"].filename == "":
        return render_template("convert.html", error="No file uploaded.")

    f = request.files["result_file"]
    run_id = uuid4().hex[:8]
    tmp_dir = WEB_RUNS / run_id / "input"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    result_path = tmp_dir / f.filename
    f.save(str(result_path))

    # List sheets for selection
    try:
        xl = pd.ExcelFile(result_path)
        all_sheets = xl.sheet_names
    except Exception as exc:
        return render_template("convert.html", error=f"Could not read file: {exc}")

    selected_sheets = request.form.getlist("sheets") or [
        s for s in all_sheets
        if "debarred" not in s.lower()
        and s.lower() not in {"sheet1", "over all result", "exam duty chart", "main seating"}
    ]

    # If sheet form not yet submitted (first POST), return sheet selector
    if "do_extract" not in request.form:
        return render_template(
            "convert.html",
            all_sheets=all_sheets,
            selected_sheets=selected_sheets,
            run_id=run_id,
            filename=f.filename,
        )

    # Second POST – extract
    try:
        students, rooms = convert_result_file(
            result_path,
            sheets=selected_sheets,
            skip_debarred=False,
        )
        timetable = extract_timetable_from_workbook(result_path)
    except Exception as exc:
        return render_template("convert.html", error=f"Extraction failed: {exc}")

    if students.empty:
        return render_template("convert.html", error="No student records found in the selected sheets.")

    # Save extracted files
    out_dir = WEB_RUNS / run_id / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    students_path = out_dir / "students_extracted.xlsx"
    rooms_path    = out_dir / "rooms_extracted.xlsx"
    students.to_excel(students_path, index=False)
    rooms.to_excel(rooms_path, index=False)

    # Save timetable as JSON for use in generate step
    import json as _json
    timetable_path = out_dir / "timetable.json"
    timetable_path.write_text(_json.dumps(timetable), encoding="utf-8")

    students_preview = students.head(20).to_dict(orient="records")
    rooms_preview    = rooms.to_dict(orient="records")

    return render_template(
        "convert.html",
        extracted=True,
        run_id=run_id,
        total_students=len(students),
        total_rooms=len(rooms),
        timetable=timetable,
        sections=students["Section"].nunique() if "Section" in students.columns else "—",
        students_preview=students_preview,
        students_columns=list(students.columns),
        rooms_preview=rooms_preview,
        rooms_columns=list(rooms.columns),
    )


@app.route("/generate", methods=["GET", "POST"])
def generate():
    if request.method == "GET":
        return render_template("generate.html")

    # ── Collect inputs ─────────────────────────────────────────────────────────
    students_file = request.files.get("students_file")
    rooms_file    = request.files.get("rooms_file")

    # Institute info
    institute   = request.form.get("institute",   "SAGAR INSTITUTE OF RESEARCH & TECHNOLOGY")
    department  = request.form.get("department",  "DEPARTMENT OF CSIT")
    exam_title  = request.form.get("exam_title",  "I MID SEM EXAMINATION (JAN-JUN 2026)")
    semester    = request.form.get("semester",    "6th Sem")

    # Options
    try:
        attendance_cutoff = float(request.form.get("attendance_cutoff", 40))
    except ValueError:
        attendance_cutoff = 40.0
    shuffle        = "shuffle" in request.form
    try:
        seed = int(request.form.get("seed", 42))
    except ValueError:
        seed = 42
    alt_seats  = "alt_seats"  in request.form
    export_pdf = "export_pdf" in request.form

    # Timetable: from hidden field OR auto-extracted from the students file
    import json
    timetable_raw = request.form.get("timetable", "[]")
    try:
        timetable = json.loads(timetable_raw)
    except Exception:
        timetable = []

    if not students_file or students_file.filename == "":
        return render_template("generate.html", error="Please upload a students file.")
    if not rooms_file or rooms_file.filename == "":
        return render_template("generate.html", error="Please upload a rooms file.")

    run_id  = uuid4().hex[:8]
    in_dir  = WEB_RUNS / run_id / "input"
    out_dir = WEB_RUNS / run_id / "output"
    in_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    s_path = in_dir / students_file.filename
    r_path = in_dir / rooms_file.filename
    students_file.save(str(s_path))
    rooms_file.save(str(r_path))

    # Auto-extract timetable from the uploaded file if not provided manually
    if not timetable and s_path.suffix in {".xlsx", ".xls"}:
        try:
            timetable = extract_timetable_from_workbook(s_path)
        except Exception:
            timetable = []

    # ── Run seating ────────────────────────────────────────────────────────────
    try:
        config = SeatingConfig(
            students_file=str(s_path),
            rooms_file=str(r_path),
            attendance_cutoff=attendance_cutoff,
            output_dir=str(out_dir),
            shuffle_students=shuffle,
            random_seed=seed if shuffle else None,
            alternate_seats=alt_seats,
            export_pdf_file=export_pdf,
        )
        result = run_seating_system(config)
    except (DataValidationError, FileNotFoundError) as exc:
        return render_template("generate.html", error=str(exc))
    except Exception as exc:
        return render_template("generate.html", error=f"Unexpected error: {exc}")

    # ── Enrich allocations with Section/Branch ────────────────────────────────
    raw_students = (
        pd.read_excel(s_path) if s_path.suffix in {".xlsx", ".xls"} else pd.read_csv(s_path)
    )
    has_section = "Section" in raw_students.columns
    has_branch  = "Branch"  in raw_students.columns
    extra_cols  = (["Section"] if has_section else []) + (["Branch"] if has_branch else [])

    alloc_sheets = pd.read_excel(out_dir / "exam_seating_output.xlsx", sheet_name=None)
    room_allocations: dict[str, pd.DataFrame] = {}
    for sheet_name, df in alloc_sheets.items():
        if not sheet_name.startswith("Room_"):
            continue
        room_no = sheet_name[len("Room_"):]
        if extra_cols:
            lookup = raw_students[["Roll Number"] + extra_cols].copy()
            lookup["Roll Number"] = lookup["Roll Number"].astype(str).str.strip()
            df["Roll Number"]     = df["Roll Number"].astype(str).str.strip()
            df = df.merge(lookup, on="Roll Number", how="left")
        room_allocations[room_no] = df

    not_eligible_df = pd.read_excel(out_dir / "exam_seating_output.xlsx", sheet_name="Not_Eligible")
    if extra_cols:
        lookup = raw_students[["Roll Number"] + extra_cols].copy()
        lookup["Roll Number"] = lookup["Roll Number"].astype(str).str.strip()
        not_eligible_df["Roll Number"] = not_eligible_df["Roll Number"].astype(str).str.strip()
        not_eligible_df = not_eligible_df.merge(lookup, on="Roll Number", how="left")

    # ── SIRT exports ──────────────────────────────────────────────────────────
    info = dict(institute=institute, department=department, exam_title=exam_title, semester=semester)
    info_no_sem = dict(institute=institute, department=department, exam_title=exam_title)

    export_sirt_main_seating_excel(room_allocations, out_dir, **info)
    export_sirt_debarred_excel(
        not_eligible_df, out_dir,
        institute=institute, department=department,
        exam_title=exam_title, attendance_cutoff=attendance_cutoff,
    )
    export_sirt_section_attendance_excel(
        room_allocations, out_dir, timetable=timetable, **info
    )

    # ── Build download list ───────────────────────────────────────────────────
    downloads = []
    priority = [
        ("SIRT_Main_Seating.xlsx",       "Main Seating Plan (SIRT)"),
        ("SIRT_Debarred_List.xlsx",       "Debarred List (SIRT)"),
        ("SIRT_Section_Attendance.xlsx",  "Attendance Sheet (Section-wise)"),
        ("exam_seating_output.xlsx",      "Full Output (Excel)"),
    ]
    for fname, label in priority:
        fp = out_dir / fname
        if fp.exists():
            downloads.append({"label": label, "filename": fname, "run_id": run_id})

    for txt in ["room_wise_seating_plan.txt", "attendance_sheet.txt",
                "not_eligible_students.txt", "summary.txt"]:
        fp = out_dir / txt
        if fp.exists():
            downloads.append({"label": txt, "filename": txt, "run_id": run_id})

    summary = result.summary
    return render_template(
        "generate.html",
        done=True,
        run_id=run_id,
        total_students=summary.total_students,
        eligible=summary.eligible_students,
        allocated=summary.allocated_students,
        debarred=summary.not_eligible_students,
        downloads=downloads,
    )


@app.route("/download/<run_id>/<filename>")
def download_file(run_id: str, filename: str):
    # Validate run_id and filename to prevent path traversal
    safe_id   = Path(run_id).name
    safe_name = Path(filename).name
    fp = WEB_RUNS / safe_id / "output" / safe_name
    if not fp.exists():
        return "File not found.", 404
    mime = (
        XLSX_MIME       if safe_name.endswith(".xlsx") else
        "text/plain"    if safe_name.endswith(".txt")  else
        "application/pdf" if safe_name.endswith(".pdf") else
        "application/octet-stream"
    )
    return send_file(str(fp), mimetype=mime, as_attachment=True, download_name=safe_name)


@app.route("/result_analysis", methods=["GET", "POST"])
def result_analysis():
    """Handle result analysis upload and statistics generation."""
    if request.method == "GET":
        return render_template("result_analysis.html")

    # POST – process uploaded results file
    if "results_file" not in request.files or request.files["results_file"].filename == "":
        return render_template("result_analysis.html", error="No file uploaded.")

    f = request.files["results_file"]
    run_id = uuid4().hex[:8]
    tmp_dir = WEB_RUNS / run_id / "input"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    result_path = tmp_dir / f.filename

    try:
        f.save(str(result_path))

        # Read file
        if f.filename.endswith(".csv"):
            df = pd.read_csv(result_path)
        else:
            df = pd.read_excel(result_path)

        # Get parameters
        try:
            pass_threshold = float(request.form.get("pass_threshold", 40))
        except ValueError:
            pass_threshold = 40.0

        semester = request.form.get("semester", "Unknown")

        # Initialize database
        db_path = str(WEB_RUNS / run_id / "result_analysis.db")
        db = ResultDatabase(db_path)

        # Import data
        db.import_from_dataframe(df, pass_threshold=pass_threshold, semester=semester)

        # Get analysis data
        overall_stats = db.get_overall_statistics()
        faculty_analysis = db.get_faculty_wise_analysis()
        subject_analysis = db.get_subject_wise_analysis()
        section_analysis = db.get_section_wise_analysis()

        # Get preview of first 10 rows
        preview_data = df.head(10).to_dict(orient="records")
        preview_columns = list(df.columns)

        db.close()

        return render_template(
            "result_analysis.html",
            run_id=run_id,
            overall_stats=overall_stats,
            faculty_analysis=faculty_analysis,
            subject_analysis=subject_analysis,
            section_analysis=section_analysis,
            preview_data=preview_data,
            preview_columns=preview_columns,
            success=f"Analysis completed! {overall_stats['total_students']} students analyzed.",
        )

    except Exception as exc:
        return render_template("result_analysis.html", error=f"Error processing file: {str(exc)}")


@app.route("/download_analysis/<run_id>/<report_type>")
def download_analysis_report(run_id: str, report_type: str):
    """Download analysis report in Excel format."""
    # Validate run_id (basic security)
    if not run_id.replace("-", "").replace("_", "").isalnum() or len(run_id) > 20:
        return "Invalid run_id", 400

    # Initialize database
    db_path = str(WEB_RUNS / run_id / "result_analysis.db")
    if not Path(db_path).exists():
        return "Analysis not found", 404

    try:
        db = ResultDatabase(db_path)

        # Generate report based on type
        if report_type == "overall":
            stats = db.get_overall_statistics()
            df = pd.DataFrame([stats])
            filename = "overall_statistics.xlsx"

        elif report_type == "faculty":
            data = db.get_faculty_wise_analysis()
            df = pd.DataFrame(data)
            filename = "faculty_wise_analysis.xlsx"

        elif report_type == "subject":
            data = db.get_subject_wise_analysis()
            df = pd.DataFrame(data)
            filename = "subject_wise_analysis.xlsx"

        elif report_type == "section":
            data = db.get_section_wise_analysis()
            df = pd.DataFrame(data)
            filename = "section_wise_analysis.xlsx"

        else:
            return "Invalid report type", 400

        db.close()

        # Generate Excel file
        buf = io.BytesIO()
        df.to_excel(buf, index=False, sheet_name="Analysis")
        buf.seek(0)

        return send_file(
            buf,
            mimetype=XLSX_MIME,
            as_attachment=True,
            download_name=filename,
        )

    except Exception as exc:
        return f"Error generating report: {str(exc)}", 500


@app.route("/template/<name>")
def template_download(name: str):
    if name == "students":
        return send_file(
            io.BytesIO(_make_students_template()),
            mimetype=XLSX_MIME,
            as_attachment=True,
            download_name="students_template.xlsx",
        )
    if name == "rooms":
        return send_file(
            io.BytesIO(_make_rooms_template()),
            mimetype=XLSX_MIME,
            as_attachment=True,
            download_name="rooms_template.xlsx",
        )
    return "Template not found.", 404


if __name__ == "__main__":
    app.run(debug=True, port=5000)
