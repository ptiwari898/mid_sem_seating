from __future__ import annotations

import base64
import io
import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

import pandas as pd

from exam_seating.allocator import allocate_students_to_rooms, split_eligibility
from exam_seating.exporters import (
    collect_generated_files,
    export_attendance_text,
    export_excel,
    export_not_eligible_text,
    export_pdf,
    export_roomwise_text,
    export_summary_text,
)
from exam_seating.io_utils import DataValidationError, load_rooms, load_students
from exam_seating.models import SeatingSummary

app = FastAPI(title="SIRT Seating API")


class SeatingConfig(BaseModel):
    attendance_cutoff: float = Field(default=40.0, ge=0, le=100)
    shuffle_students: bool = False
    random_seed: Optional[int] = None
    alternate_seats: bool = False
    export_pdf_file: bool = False


class SeatingSummaryResponse(BaseModel):
    total_students: int
    eligible_students: int
    not_eligible_students: int
    allocated_students: int
    unallocated_students: int
    room_count: int
    total_capacity: int
    effective_capacity: int


class SeatingResponse(BaseModel):
    summary: SeatingSummaryResponse
    files: dict[str, str]
    pdf_generated: bool


@app.get("/")
async def root():
    return JSONResponse({
        "message": "SIRT Seating API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "generate_seating": "/api/generate-seating (POST)",
            "generate_seating_multipart": "/api/generate-seating-multipart (POST multipart/form-data)",
        }
    })


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


def _read_file_content(file: UploadFile) -> bytes:
    content = file.file.read()
    file.file.seek(0)
    return content


def _save_uploaded_file(content: bytes, filename: str) -> Path:
    suffix = Path(filename).suffix or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(content)
        return Path(f.name)


def _process_seating(
    students_file: Path,
    rooms_file: Path,
    config: SeatingConfig,
    output_dir: Path,
) -> SeatingResponse:
    if config.attendance_cutoff < 0 or config.attendance_cutoff > 100:
        raise DataValidationError("Attendance cutoff must be between 0 and 100.")

    students = load_students(students_file)
    rooms = load_rooms(rooms_file)

    eligible, not_eligible = split_eligibility(students, config.attendance_cutoff)

    room_allocations, unallocated, allocation_order, effective_capacity = allocate_students_to_rooms(
        eligible_students=eligible,
        rooms=rooms,
        alternate_seats=config.alternate_seats,
        shuffle=config.shuffle_students,
        random_seed=config.random_seed,
    )

    summary = SeatingSummary(
        total_students=len(students),
        eligible_students=len(eligible),
        not_eligible_students=len(not_eligible),
        allocated_students=len(allocation_order) - len(unallocated),
        unallocated_students=len(unallocated),
        room_count=len(rooms),
        total_capacity=int(rooms["Capacity"].sum()),
        effective_capacity=effective_capacity,
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    roomwise_text_file = export_roomwise_text(room_allocations, output_dir)
    not_eligible_text_file = export_not_eligible_text(not_eligible, output_dir)
    attendance_text_file = export_attendance_text(room_allocations, output_dir)
    summary_text_file = export_summary_text(summary, output_dir)
    excel_file = export_excel(room_allocations, not_eligible, summary, output_dir)

    pdf_file = None
    if config.export_pdf_file:
        pdf_file = export_pdf(room_allocations, output_dir)

    generated = collect_generated_files([
        roomwise_text_file,
        not_eligible_text_file,
        attendance_text_file,
        summary_text_file,
        excel_file,
        pdf_file,
    ])

    files_dict = {}
    for file_path in generated:
        path = Path(file_path)
        with open(path, "rb") as f:
            content = f.read()
        files_dict[path.name] = base64.b64encode(content).decode("utf-8")

    return SeatingResponse(
        summary=SeatingSummaryResponse(
            total_students=summary.total_students,
            eligible_students=summary.eligible_students,
            not_eligible_students=summary.not_eligible_students,
            allocated_students=summary.allocated_students,
            unallocated_students=summary.unallocated_students,
            room_count=summary.room_count,
            total_capacity=summary.total_capacity,
            effective_capacity=summary.effective_capacity,
        ),
        files=files_dict,
        pdf_generated=pdf_file is not None,
    )


@app.post("/api/generate-seating", response_model=SeatingResponse)
async def generate_seating(
    students_file: UploadFile = File(...),
    rooms_file: UploadFile = File(...),
    attendance_cutoff: float = Form(40.0),
    shuffle_students: bool = Form(False),
    random_seed: Optional[int] = Form(None),
    alternate_seats: bool = Form(False),
    export_pdf_file: bool = Form(False),
):
    students_content = _read_file_content(students_file)
    rooms_content = _read_file_content(rooms_file)

    students_path = _save_uploaded_file(students_content, students_file.filename or "students.csv")
    rooms_path = _save_uploaded_file(rooms_content, rooms_file.filename or "rooms.csv")

    config = SeatingConfig(
        attendance_cutoff=attendance_cutoff,
        shuffle_students=shuffle_students,
        random_seed=random_seed,
        alternate_seats=alternate_seats,
        export_pdf_file=export_pdf_file,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "output"
        try:
            result = _process_seating(students_path, rooms_path, config, output_dir)
        finally:
            students_path.unlink(missing_ok=True)
            rooms_path.unlink(missing_ok=True)

    return result


@app.post("/api/generate-seating-json", response_model=SeatingResponse)
async def generate_seating_json(
    students_file_base64: str,
    rooms_file_base64: str,
    students_filename: str = "students.csv",
    rooms_filename: str = "rooms.csv",
    attendance_cutoff: float = 40.0,
    shuffle_students: bool = False,
    random_seed: Optional[int] = None,
    alternate_seats: bool = False,
    export_pdf_file: bool = False,
):
    try:
        students_content = base64.b64decode(students_file_base64)
        rooms_content = base64.b64decode(rooms_file_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 encoding: {e}")

    students_path = _save_uploaded_file(students_content, students_filename)
    rooms_path = _save_uploaded_file(rooms_content, rooms_filename)

    config = SeatingConfig(
        attendance_cutoff=attendance_cutoff,
        shuffle_students=shuffle_students,
        random_seed=random_seed,
        alternate_seats=alternate_seats,
        export_pdf_file=export_pdf_file,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "output"
        try:
            result = _process_seating(students_path, rooms_path, config, output_dir)
        finally:
            students_path.unlink(missing_ok=True)
            rooms_path.unlink(missing_ok=True)

    return result


@app.post("/api/generate-seating-multipart", response_model=SeatingResponse)
async def generate_seating_multipart(
    students_file: UploadFile = File(...),
    rooms_file: UploadFile = File(...),
    attendance_cutoff: float = Form(40.0),
    shuffle_students: bool = Form(False),
    random_seed: Optional[int] = Form(None),
    alternate_seats: bool = Form(False),
    export_pdf_file: bool = Form(False),
):
    return await generate_seating(
        students_file=students_file,
        rooms_file=rooms_file,
        attendance_cutoff=attendance_cutoff,
        shuffle_students=shuffle_students,
        random_seed=random_seed,
        alternate_seats=alternate_seats,
        export_pdf_file=export_pdf_file,
    )


@app.get("/api/download/{filename}")
async def download_file(filename: str, content_base64: str):
    try:
        content = base64.b64decode(content_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 content")

    media_type = "application/octet-stream"
    if filename.endswith(".xlsx"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif filename.endswith(".pdf"):
        media_type = "application/pdf"
    elif filename.endswith(".txt"):
        media_type = "text/plain"

    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )