# Code Review And Implementation Tracklist

Date: 2026-05-08

## Scope

- Reviewed core seating flow, data validation, exporters, Streamlit UI tabs, and result analyzer modules.
- Reviewed current automated tests.
- Baseline test run: `5 passed` using workspace virtual environment.

## Findings (Prioritized)

### 1) High: Capacity pre-check ignores alternate seating mode in UI

- Location: `ui/tab_generate.py`
- Problem: The pre-generation guard computes `rooms_ok` using raw room capacity only. When `alternate_seats` is enabled, effective capacity is lower, so generation can proceed even when seats are insufficient.
- Risk: Users can click generate with a misleading capacity indicator and get unexpected unallocated students.
- Suggested change:
  - Compute effective capacity in UI preview:
    - Normal mode: `sum(capacity)`
    - Alternate seats: `sum((capacity + 1) // 2)`
  - Use effective capacity in the `rooms_ok` condition and capacity metric label.

### 2) High: Result pass-rate logic appears inflated ("any-subject-pass" counting)

- Location: `experimental/result_analyzer.py`
- Problem: `get_overall_statistics()` counts students as passed if they have at least one passing subject (`r.status = 'Pass'`). In most exam workflows, "passed student" means passing all required subjects (or meeting rule-defined criteria).
- Risk: Reported overall pass percentage can be materially overstated.
- Suggested change:
  - Define explicit pass policy (all-subject pass / minimum credits / SGPA threshold).
  - Implement aggregate logic per student based on policy instead of `EXISTS pass subject` semantics.
  - Add tests with mixed-pass students to validate policy.

### 3) Medium: Attendance status normalization is inconsistent

- Location: `experimental/result_analyzer.py`
- Problem: `import_from_dataframe()` normalizes attendance to uppercase, but `add_attendance()` accepts raw input and documentation states values like `Present`/`Absent`. Analysis queries filter only `!= 'ABSENT'`, which can misclassify mixed-case values written through other code paths.
- Risk: Absent students may be included in analyses if status casing varies.
- Suggested change:
  - Normalize status to uppercase in `add_attendance()`.
  - Optionally constrain values to `PRESENT` or `ABSENT` with validation.

### 4) Medium: Documented text outputs are not generated in current service flow

- Locations: `exam_seating/service.py`, `README.md`, `exam_seating/exporters.py`
- Problem: Text exporters exist (`export_roomwise_text`, `export_not_eligible_text`, etc.) but are not called by `run_seating_system()`, while README lists them as generated outputs.
- Risk: Feature expectation mismatch for users and maintainers.
- Suggested change:
  - Either invoke text exporters in service flow and include files in `generated_files`, or update README to reflect current behavior.

### 5) Low: `clear_all()` does not clear `analysis_sessions`

- Location: `experimental/result_analyzer.py`
- Problem: `clear_all()` deletes operational tables but leaves `analysis_sessions` untouched.
- Risk: Stale session metadata after reset, surprising for users expecting full cleanup.
- Suggested change:
  - Include `DELETE FROM analysis_sessions` in `clear_all()`.

### 6) Low: Coverage gaps around validation, runtime upload flow, and result analyzer

- Location: `tests/`
- Problem: Tests currently focus on allocator/service happy paths; there are no tests for key edge cases in upload/runtime and result-analysis SQL behavior.
- Risk: Regressions in user-facing data ingestion and analytics can go undetected.
- Suggested change:
  - Add tests for:
    - Alternate-seat effective capacity preview logic.
    - SQLite table spec parsing and validation errors.
    - Result analyzer attendance normalization and pass-policy correctness.

## Implementation Tracklist

| ID | Priority | Area | Proposed Change | Impact | Effort | Status | Primary Files |
|---|---|---|---|---|---|---|---|
| CR-01 | High | Streamlit generation flow | Use effective capacity in preview + `rooms_ok` when alternate seating is enabled | Prevents misleading readiness state and avoids avoidable unallocation | Small | Implemented (2026-05-08) | `ui/tab_generate.py` |
| CR-02 | High | Result analytics | Replace any-subject pass counting with explicit pass-policy aggregation | Corrects overall pass-rate accuracy | Medium | Implemented (2026-05-08) | `experimental/result_analyzer.py`, `tests/test_result_analyzer.py` |
| CR-03 | Medium | Result analytics | Normalize and validate attendance status in write path (`add_attendance`) | Prevents case-related misclassification in SQL filters | Small | Implemented (2026-05-08) | `experimental/result_analyzer.py`, `tests/test_result_analyzer.py` |
| CR-04 | Medium | Output consistency | Align service outputs with docs: either generate text files or update docs | Removes user confusion and support churn | Small | Implemented (2026-05-08) | `exam_seating/service.py`, `tests/test_service.py` |
| CR-05 | Low | Database reset semantics | Extend `clear_all()` to wipe `analysis_sessions` | Makes reset behavior predictable | Small | Implemented (2026-05-08) | `experimental/result_analyzer.py`, `tests/test_result_analyzer.py` |
| CR-06 | Medium | Test quality | Add regression tests for upload validation + result analysis rules | Reduces future regressions | Medium | Implemented (2026-05-08) | `tests/test_service.py`, `tests/test_result_analyzer.py`, `tests/test_io_utils.py` |

## Implementation Notes

### CR-01

- Implemented in `ui/tab_generate.py`.
- Updated UI capacity preview and generation guard:
  - Normal mode uses `sum(capacity)`.
  - Alternate seats mode uses effective capacity `sum((capacity + 1) // 2)`.
- Generate button gating now compares eligible students against effective capacity, eliminating the pre-check mismatch in alternate seating mode.

### CR-02

- Implemented in `experimental/result_analyzer.py`.
- Updated `get_overall_statistics()` pass policy:
  - Student is counted as passed only when all recorded subject results are PASS.
  - Students with no recorded results are not counted as passed.
  - Absent students continue to be excluded from overall totals.
- Added regression test in `tests/test_result_analyzer.py` validating mixed outcomes and absent-student exclusion.

### CR-03

- Implemented in `experimental/result_analyzer.py`.
- `add_attendance()` now normalizes input status to uppercase and validates allowed values.
- Accepted values are `PRESENT` and `ABSENT` (case-insensitive input).
- Invalid statuses now raise a clear `ValueError`.
- Added regression tests in `tests/test_result_analyzer.py` for mixed-case normalization and invalid-status rejection.

### CR-04

- Implemented in `exam_seating/service.py`.
- `run_seating_system()` now generates the documented text outputs:
  - `room_wise_seating_plan.txt`
  - `not_eligible_students.txt`
  - `attendance_sheet.txt`
  - `summary.txt`
- These files are now included in `generated_files` along with existing Excel/PDF outputs.
- Added regression test in `tests/test_service.py` to assert file creation and generated file tracking.

### CR-05

- Implemented in `experimental/result_analyzer.py`.
- `clear_all()` now removes `analysis_sessions` records in addition to core entities.
- Added regression test in `tests/test_result_analyzer.py` to verify full cleanup behavior.

### CR-06

- Expanded regression coverage across service, analyzer, and io validation paths.
- Added `tests/test_io_utils.py` covering:
  - SQLite table spec parsing.
  - Missing default SQLite table detection.
  - Invalid `::table` spec usage on non-SQLite files.
  - Duplicate room detection from SQLite source.
- Existing additions in prior CRs already cover:
  - Alternate-seat capacity behavior in service output (`tests/test_service.py`).
  - Result analyzer pass-policy and attendance status rules (`tests/test_result_analyzer.py`).

## Suggested Execution Order

1. CR-01 (quick user-facing correctness fix)
2. CR-03 (data integrity hardening)
3. CR-02 (analytics correctness)
4. CR-04 (behavior/documentation alignment)
5. CR-05 (cleanup consistency)
6. CR-06 (expand regression safety net)
