from __future__ import annotations

import re
import shutil
import time
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st

from exam_seating.io_utils import DataValidationError, load_rooms, load_students

WEB_RUNS_DIR = Path("web_runs")
RUN_RETENTION_SECONDS = 3600


def cleanup_old_web_runs(retention_seconds: int = RUN_RETENTION_SECONDS) -> None:
    if not WEB_RUNS_DIR.exists():
        return

    cutoff = time.time() - retention_seconds
    for item in WEB_RUNS_DIR.iterdir():
        if not item.is_dir():
            continue
        try:
            if item.stat().st_mtime < cutoff:
                shutil.rmtree(item, ignore_errors=True)
        except OSError:
            continue


def get_session_input_dir() -> Path:
    if "upload_run_id" not in st.session_state:
        st.session_state["upload_run_id"] = uuid4().hex[:8]
    return WEB_RUNS_DIR / st.session_state["upload_run_id"] / "input"


def save_uploaded(uploaded_file, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)

    # Keep only latest upload in session folder to bound file growth.
    for item in target_dir.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            item.unlink(missing_ok=True)

    path = target_dir / uploaded_file.name
    path.write_bytes(uploaded_file.getbuffer())
    return path


def load_students_from_upload(uploaded_file, sqlite_table: str) -> pd.DataFrame:
    path = save_uploaded(uploaded_file, get_session_input_dir() / "students")
    suffix = path.suffix.lower()

    if suffix in {".db", ".sqlite", ".sqlite3"}:
        file_spec = f"{path}::{sqlite_table.strip()}" if sqlite_table.strip() else str(path)
        return load_students(file_spec)

    if suffix == ".csv":
        return pd.read_csv(path)

    xl = pd.ExcelFile(path)
    sheet_frames = []
    required = {"Roll Number", "Name", "Attendance Percentage"}
    skipped_sheets = []

    for sheet in xl.sheet_names:
        df_sheet = pd.read_excel(xl, sheet_name=sheet)
        df_sheet.columns = [c.strip() for c in df_sheet.columns]
        if required.issubset(set(df_sheet.columns)):
            if "Section" not in df_sheet.columns:
                m = re.search(r"\b([A-Z])\s*$", sheet.strip())
                df_sheet["Section"] = m.group(1) if m else sheet.strip()
            if "Branch" not in df_sheet.columns:
                branch_part = re.sub(r"\s*[A-Z]\s*$", "", sheet.strip()).strip()
                df_sheet["Branch"] = branch_part if branch_part else "CSIT"
            sheet_frames.append(df_sheet)
        else:
            skipped_sheets.append(sheet)

    if not sheet_frames:
        raise DataValidationError(
            f"None of the {len(xl.sheet_names)} sheet(s) contain the required columns: "
            "Roll Number, Name, Attendance Percentage."
        )

    students_df = pd.concat(sheet_frames, ignore_index=True)
    if skipped_sheets:
        st.caption(f"Skipped sheets (missing required columns): {', '.join(skipped_sheets)}")

    return students_df


def load_rooms_from_upload(uploaded_file, sqlite_table: str) -> pd.DataFrame:
    path = save_uploaded(uploaded_file, get_session_input_dir() / "rooms")
    suffix = path.suffix.lower()

    if suffix in {".db", ".sqlite", ".sqlite3"}:
        file_spec = f"{path}::{sqlite_table.strip()}" if sqlite_table.strip() else str(path)
        return load_rooms(file_spec)

    if suffix == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)

    required = {"Room Number", "Capacity"}
    missing = required - set(df.columns)
    if missing:
        raise DataValidationError(f"Missing columns in uploaded rooms file: {', '.join(sorted(missing))}")

    return df[["Room Number", "Capacity"]].copy()


def create_new_run_input_dir() -> Path:
    cleanup_old_web_runs()
    run_id = uuid4().hex[:8]
    input_dir = WEB_RUNS_DIR / run_id / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    return input_dir


def create_new_run_dirs() -> tuple[Path, Path, Path]:
    cleanup_old_web_runs()
    run_id = uuid4().hex[:8]
    base_dir = WEB_RUNS_DIR / run_id
    input_dir = base_dir / "input"
    output_dir = base_dir / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    return base_dir, input_dir, output_dir
