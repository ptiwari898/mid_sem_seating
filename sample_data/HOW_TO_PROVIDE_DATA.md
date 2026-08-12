# SIRT Exam Seating System: How to Provide Data

This guide explains how to provide student and marks data using the new **Data & Marks Management** tab.

---

## 📋 Overview

The system now has **3 tabs**:
1. **Seating Plan** - Generate exam seating arrangements
2. **Result Analysis** - Analyze subject-wise results
3. **Data & Marks Management** - 🆕 Save student data + Faculty marks entry with PIN security

---

## 🎯 Step 1: Provide Student Data

### Format Required
Your student file must have these **minimum columns**:
- **Roll Number** (unique identifier)
- **Name** (student full name)
- **Attendance Percentage** (0-100)

### Supported File Types
- `.xlsx` (Excel)
- `.xls` (Excel older format)
- `.csv` (Comma-separated values)

### Example Student Data (`students.csv`)

```csv
Roll Number,Name,Attendance Percentage
0133CI231001,AARAV SINGH,82
0133CI231002,DIYA PATEL,38
0133CI231003,ROHAN MEHTA,67
0133CI231004,ANNYA DAS,91
0133CI231005,KARAN VERMA,45
```

### How to Save Student Data

1. Go to the **Data & Marks Management** tab
2. Click **"Upload Students File"**
3. Browse and select your `.xlsx`, `.xls`, or `.csv` file
4. Click **Save** 
5. ✅ Data is now stored in session and available in other tabs

> 💡 **Tip**: Student data persists for the current browser session. 
> Save it once and it will be available when you switch to Result Analysis tab.

---

## 🔐 Step 2: Faculty Marks Entry (PIN Protected)

### PIN Code
- Default PIN: **`1234`**
- Configured in `.streamlit/secrets.toml`
- Contact admin to change if needed

### How to Enter Marks

1. Go to the **Data & Marks Management** tab
2. Enter the **4-digit PIN code** in the authentication field
3. Click **Submit**
4. ✅ Authentication successful - marks entry interface appears

### Marks Entry Interface

You'll see a table with these columns:

| Roll No. | Student Name | Marks (0-30) | Absent ✓ |
|----------|-------------|--------------|----------|
| 0133CI231001 | AARAV SINGH | 25 | ✗ |
| 0133CI231002 | DIYA PATEL | 30 | ✗ |
| 0133CI231003 | ROHAN MEHTA | 20 | ✓ (check if absent) |

**Features:**
- ✅ **Marks**: Auto-validated between 0-30, step=1
- ✅ **Absent**: Checkbox to mark student as absent
- ✅ **Roll No & Name**: Read-only (auto-populated from saved students)
- ✅ **Data Editor**: Full editing capability for marks and absent status

### Faculty Information Form

After PIN auth, you'll also fill:
- **Faculty Name**: e.g., "Prof. John Smith"
- **Subject Name/Code**: e.g., "CSIT-601" or "Computer Networks"
- **Exam Name**: e.g., "I MID SEM EXAMINATION"

### Submit Marks

1. Enter marks for all students in the editor
2. Click **"Submit Marks"** (primary button)
3. ✅ Marks saved to session
4. Click **Cancel** to exit without saving

> 💡 **Important**: Marks are stored in `st.session_state["submitted_marks"]` and can be 
> loaded in the Result Analysis tab for inclusion in summaries.

---

## 📊 Step 3: Use Data in Result Analysis

### Auto-Load Saved Students

1. Go to the **Result Analysis** tab
2. Look for **"Use saved student data"** dropdown (appears automatically if data is saved)
3. ✅ Student list auto-populates from Data & Marks tab
4. Continue with normal column mapping and subject setup

### Load Faculty Marks Data

1. In Result Analysis tab, look for **"Load faculty marks data"** option
2. ✅ Marks previously entered (PIN-authenticated) will be loaded
3. Summary calculations include the faculty-entered marks
4. Generate result Excel/CSV as normal

### What Gets Integrated

- **Student count and list** from saved data
- **Marks distribution** from faculty entry
- **Pass/fail analysis** includes all marked students
- **Summary metrics**: average, pass %, topper, etc.

---

## 📁 Sample Files Provided

| File | Purpose | Format |
|------|---------|--------|
| `students.csv` | Sample student data | CSV (Roll No, Name, Attendance %) |
| `mark_entry_template.xlsx` | Marks entry demo | Excel (Roll No, Name, Marks, Absent) |
| `mark_entry_template.csv` | Marks entry demo | CSV (same as above) |

### Sample Data Files Location
```
F:\mid sem project\sample_data\
```

### Using Sample Files

1. **For students**: Use `students.csv` as template or replace with your data
2. **For marks entry**: Open `marks_entry_template.xlsx` to see the expected format
3. **Upload**: Browse to these files when prompted in the Data & Marks tab

---

## 🔄 Complete Data Flow Example

```
Step 1: Upload students.csv in Data & Marks Tab
    ↓
✅ 30 students saved to session

Step 2: Enter PIN "1234" → Authenticate
    ↓
✅ Faculty marks interface unlocked

Step 3: Enter marks (0-30) + mark absent students
    ↓
✅ Marks submitted successfully

Step 4: Switch to Result Analysis Tab
    ↓
✅ Student list auto-loaded from saved data
✅ Faculty marks loaded for analysis
✅ Generate result summary includes all data

Step 5: Download result Excel/CSV
    ↓
✅ Contains: student info + marks + analysis
```

---

## ⚠️ Important Notes

### Data Persistence
- Student data: Stored in browser **session state**
- Marks data: Stored in browser **session state**
- **Both reset if you close/refresh the browser** (or clear cookies)
- For permanent storage, consider exporting data ( Export All Data button )

### PIN Security
- 3 failed attempts → 15-minute lockout
- After lockout, PIN resets automatically
- Default PIN: `1234` (change via `.streamlit/secrets.toml`)

### File Requirements

**Students file must have:**
```
Required columns: Roll Number, Name, Attendance Percentage
```

**Marks entry has:**
```
Roll Number (read-only, from saved students)
Name (read-only, from saved students)
Marks (0-30, numeric, step=1)
Absent (checkbox, optional)
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| "Missing required columns" | Ensure students file has: Roll Number, Name, Attendance Percentage |
| "Invalid PIN" | Check PIN is 4 digits, default is 1234 |
| "No student data saved" | Save students first in Data & Marks tab |
| Marks not appearing in Results | Ensure "Load faculty marks data" is selected in Result Analysis |
| Data lost after refresh | Session state expires; re-upload and resave |

---

## 💡 Best Practices

1. **Save student data first** - Do this once per exam session
2. **Use consistent Roll Numbers** - Match across all tabs for seamless integration
3. **Mark attendance first** - Helps identify eligible students before entering marks
4. **Export data periodically** - Use "Export All Data" button if you need persistent copies
5. **Change default PIN** - Update `.streamlit/secrets.toml` for production use

---

## 🆘 Need Help?

- **Check `.streamlit/secrets.toml`** - Ensure `MARKS_PIN` is configured
- **Run tests**: `python -m pytest tests/ -v` (all 15 tests should pass)
- **Sample files** are in `sample_data/` directory
- **Contact admin** to change the default PIN (`1234`)

---
*Generated for SIRT Exam Seating System v2.0*