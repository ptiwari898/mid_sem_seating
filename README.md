# Automatic Exam Seating Arrangement System

A complete Python-based system to automate exam seating arrangement using student attendance and room capacity.

## Features

- Reads students and rooms from CSV or Excel files.
- Validates input data for missing values and wrong formats.
- Filters students using attendance cutoff.
- Creates separate not-eligible list.
- Supports deterministic roll sorting or random shuffle.
- Allocates students room-wise without exceeding capacity.
- Supports alternate seating mode to leave every other seat empty.
- Generates:
  - Room-wise seating plan (text)
  - Not eligible list (text)
  - Attendance sheets (text)
  - Summary report (text)
  - Excel workbook with separate sheets for each room
- Optional PDF export for room-wise seating plan.
- Optional Tkinter GUI.

## Input Format

### Students file (CSV/Excel)
Required columns:

- `Roll Number`
- `Name`
- `Attendance Percentage`

### Rooms file (CSV/Excel)
Required columns:

- `Room Number`
- `Capacity`

## Installation

```bash
pip install -r requirements.txt
```

## CLI Usage

```bash
python main.py --students sample_data/students.csv --rooms sample_data/rooms.csv --attendance-cutoff 40 --output-dir output
```

### Useful options

```bash
--shuffle              Shuffle eligible students before allocation
--seed 42              Seed for reproducible shuffle
--alternate-seats      Allocate on alternate seat numbers only
--export-pdf           Export room-wise seating plan PDF (requires reportlab)
```

Example with all options:

```bash
python main.py --students sample_data/students.csv --rooms sample_data/rooms.csv --attendance-cutoff 40 --output-dir output --shuffle --seed 42 --alternate-seats --export-pdf
```

## GUI Usage

```bash
python gui.py
```

Use file pickers to select students and rooms files, set options, and generate output.

## Output Files

Generated in output folder:

- `room_wise_seating_plan.txt`
- `not_eligible_students.txt`
- `attendance_sheet.txt`
- `summary.txt`
- `exam_seating_output.xlsx`
- `room_wise_seating_plan.pdf` (optional, if reportlab is installed)

## Notes

- Attendance cutoff must be between 0 and 100.
- Attendance values can include `%` sign (for example `42%`) and will be parsed correctly.
- For large datasets, pandas-based vectorized processing is used.
# mid_sem_seating
