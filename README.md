# Automatic Exam Seating Arrangement System

[GitHub Repository](https://github.com/ptiwari898/mid_sem_seating)

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).
See the [LICENSE](LICENSE) file for full license text.

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
- Streamlit web app.

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

## Web App Usage (Streamlit)

```bash
python run.py
```

or

```bash
streamlit run streamlit_app.py
```

Then open the local URL shown in terminal (usually `http://localhost:8501`) and:

- Upload student file (CSV/Excel)
- Upload room file (CSV/Excel)
- Set cutoff and options (shuffle, alternate seats, PDF)
- Click **Generate Seating Plan**
- Download generated reports directly from the page

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
