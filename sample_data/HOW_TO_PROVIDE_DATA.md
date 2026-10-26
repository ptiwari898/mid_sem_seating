# How to Provide Data

The app has three pages. **Seating & Results** has the tabs **Seating Plan**, **Result Analysis** and
**Saved Students**. **Marks Entry** (`/marks-entry`) is a separate page for teachers, and **Admin**
(`/admin`) is the password-protected page for the coordinator.

## 1. Student file

Required columns: `Roll Number`, `Name`, `Attendance Percentage`.
Optional columns: `Section`, `Branch` (used for per-section sheets and for filtering marks entry).
Formats: `.xlsx`, `.xls`, `.csv` (and `.db` / `.sqlite` in the Seating Plan tab).

Attendance can be written as `82`, `82%`, or as an Excel percent cell (shown as 82%, stored as 0.82).
All three are read as 82. See `students.csv` for an example.

## 2. Seating plan and marks entry

1. In **Seating Plan**, upload students, add rooms, and add the exam subjects in step 3.
2. Tick **"Also open marks entry for the eligible students"** and set the maximum marks.
3. Click **Generate Seating Plan**. The app shows a 6-digit **PIN** and a CSV download button.
   Give the PIN to the teachers. It stays valid for 7 days.

## 3. Teachers enter marks

1. Open the **Marks Entry** page (add `/marks-entry` to the app address) and enter the PIN.
2. Choose any subject (all subjects are listed), optionally a section, and type your name.
3. Fill in marks (or tick **Absent**) and press **Save Marks**. Only changed rows are saved.

After 5 wrong PINs from one browser, that form locks for 15 minutes. Across all browsers, 30 wrong
PINs in 15 minutes pause every PIN check.

## 4. Admin page

Set `ADMIN_PASSWORD` in the app secrets (`.streamlit/secrets.toml` locally, the Secrets panel on
Streamlit Cloud), then open `/admin` (also linked from the sidebar of the Seating & Results page).

- **Seating plans**: every plan you generated, with student counts, per-room allocation, the linked
  marks entry, and a download of all reports as a zip.
- **Marks entries**: each session's PIN (useful if it was lost), progress per subject, all marks,
  CSV downloads for the marks and the edit history, **Lock (finalise)** / unlock, and delete.
- **Backup**: download or restore the whole database.

Deleting needs the "I am sure" box ticked first. The database file (`marks_sessions.db`) can be lost
when a cloud host restarts the app, so download a backup after each round.

## 5. Result analysis

In **Result Analysis**, choose where the data comes from:

- **Upload a file** (see `sample_results.csv` and `result_analysis_template.csv`)
- **Saved student data** from the Saved Students tab
- **Marks entry session (PIN)**: loads every subject's marks; press **Add all session subjects**
  to create the subject list. Absent students show as `AB` and count as not appeared.

Fill in the header fields (institute, department, exam title, section), set the pass marks and
press **Generate Result Analysis**.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Missing required columns" | The students file needs Roll Number, Name, Attendance Percentage. |
| Everyone is ineligible | Check the attendance column; values should be 0-100 or percent cells. |
| "Invalid or expired PIN" | PINs expire after 7 days; ask the coordinator for the PIN. |
| "Marks entry is locked" | The coordinator finalised the session; ask them to unlock it. |
| Marks gone after a restart | Restore the backup on the Admin page (Backup tab). |
