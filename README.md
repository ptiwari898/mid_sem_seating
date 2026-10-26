# Automatic Exam Seating Arrangement System

[GitHub Repository](https://github.com/ptiwari898/mid_sem_seating)

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).
See the [LICENSE](LICENSE) file for full license text.

A complete Python-based system to automate exam seating arrangement using student attendance and room capacity.

## Features

- Reads students and rooms from CSV or Excel files.
- Reads students and rooms from SQLite databases (`.db`, `.sqlite`, `.sqlite3`).
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
- Streamlit web app with three pages: Seating & Results (tabs: Seating Plan, Result Analysis, Saved Students), a separate Marks Entry page for teachers (`/marks-entry`), and a password-protected Admin page (`/admin`).
- Institute-style Excel reports: main seating sheet, debarred list and section-wise attendance sheets.
- Attendance written as `82`, `82%` or an Excel percent cell (0.82) is read as 82.
- Optional PIN-based marks entry for the eligible students (see below).
- Result Analysis from an uploaded file, saved students, or a marks-entry session.

## Marks Entry

Tick "Also open marks entry" when generating a plan to get a 6-digit PIN. Teachers open the separate
**Marks Entry** page (`/marks-entry`; the coordinator page links to it, the page itself has no link back to the seating page), enter the PIN, pick any subject (and section)
and enter marks for the eligible students.
The **Admin** page (`/admin`) lists every generated seating plan (with its reports as a zip) and every marks
entry (PIN, progress per subject, all marks). The admin can lock the marks, download marks and edit history,
delete old records, and back up the database. See [sample_data/HOW_TO_PROVIDE_DATA.md](sample_data/HOW_TO_PROVIDE_DATA.md).

## Configuration

| Setting | Where | Purpose |
|---------|-------|---------|
| `ADMIN_PASSWORD` | Streamlit secrets | Unlocks the Admin page. If it is not set, the page stays disabled. |
| `MARKS_DB_PATH` | Environment variable | Location of the marks database (default `marks_sessions.db`). |
| `API_KEY` | Environment variable (Vercel) | Requires an `X-API-Key` header on the API endpoints. |

Secrets files and `*.db` files are git-ignored. Never commit them.

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

## Project Structure

```
streamlit_app.py    Streamlit entry point (run.py launches it)
gui.py              Optional Tkinter desktop app
api/                FastAPI app deployed on Vercel
exam_seating/       Core logic: loading, allocation, exports, marks_store (SQLite: plans and marks)
ui/                 Streamlit tabs, pages and helpers
tests/              pytest suite
sample_data/        Example input files
docs/               Extra documentation
```

## Look and Feel

Dark is the default. A Light mode / Dark mode button at the bottom left of every page switches instantly and keeps your
work (it is done in CSS, because Streamlit can only change its theme with a page reload). Colours, radii and heading
sizes are set in `.streamlit/config.toml` (one blue accent);
`ui/style.py` adds the rest and documents the rules: one accent, 8px controls, 12px cards, Material icons
instead of emoji, and a narrow centred layout for the teachers' and admin password pages.

## API Deployment Notes

- The FastAPI app in `api/index.py` is deployed on Vercel using `requirements-prod.txt`.
- Set the `API_KEY` environment variable to require an `X-API-Key` header on the three
  `generate-seating` endpoints. Without it the API is open. `/health` is always open.
- Uploads are limited to 5 MB per file. Vercel functions are stateless, so there is no
  built-in rate limit; put one in front (for example Vercel Firewall) if the URL is public.

## Output Files

Generated in output folder:

- `room_wise_seating_plan.txt`
- `not_eligible_students.txt`
- `attendance_sheet.txt`
- `summary.txt`
- `exam_seating_output.xlsx`
- `room_wise_seating_plan.pdf` (optional, if reportlab is installed)

## Tests

```bash
python -m pytest -q
```

## Notes

- Attendance cutoff must be between 0 and 100.
- Attendance values can include `%` sign (for example `42%`) and will be parsed correctly.
- For large datasets, pandas-based vectorized processing is used.
