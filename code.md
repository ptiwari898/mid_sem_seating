
---

**What the project does well**

The overall design is solid. Separating extraction (`convert_result_to_students.py`) from the seating engine (`exam_seating/service.py`) from the UI is the right layering. The header-scanning loop in `_extract_from_sheet()` — trying each row as a potential header until required columns appear — is a genuinely clever way to handle the inconsistent SIRT result workbooks without knowing in advance how many title rows precede the data.

---

**Issue 1 — `tab_convert()` is dead code (critical)**

`main()` in `streamlit_app.py` never calls `tab_convert()`. The entire "Step 1 — Convert Result Workbook" tab is defined but not reachable. Fix:

```python
def main() -> None:
    st.set_page_config(...)
    info = _sidebar_institute_info()
    tab1, tab2 = st.tabs(["📂 Step 1 — Convert Workbook", "🪑 Step 2 — Generate Plan"])
    with tab1:
        tab_convert()
    with tab2:
        tab_generate(info)
```

**Issue 2 — `web_runs/` grows forever (reliability)**

Every seating run writes uuid-named directories under `web_runs/` and never cleans them up. On a shared deployment this fills disk. Use Python's `tempfile.TemporaryDirectory` as a context manager, or add a background thread that deletes folders older than 1 hour.

**Issue 3 — `_parse_section_branch()` always returns `"CSIT"` (logic bug)**

The branch is hardcoded as `"CSIT"` regardless of the sheet name. A sheet named `"6th ME-B"` or `"6th EC-A"` will still get `Branch = "CSIT"`. The fix is straightforward — parse the branch prefix:

```python
def _parse_section_branch(sheet_name: str) -> tuple[str, str]:
    name = sheet_name.strip()
    m = re.search(r"\b([A-Z])\s*$", name)
    section = m.group(1) if m else ""
    branch_part = re.sub(r"\s*[A-Z]\s*$", "", name).strip()
    branch = branch_part if branch_part else "CSIT"
    return branch, section
```

**Issue 4 — imports inside loops**

In `tab_generate()`, `import re as _re` appears inside a for-loop over sheets, and `import io as _io` and `from openpyxl import ...` appear inside `_merge_workbooks()`. Python caches imports after the first hit so this isn't a crash, but it's misleading and makes linters flag it. Move all imports to the top of the file.

**Issue 5 — `streamlit_app.py` at 809 lines is too large**

The file contains template generation, workbook merging, UI tab logic, sidebar config, and seating orchestration all in one place. Suggested split:

- `ui/tab_convert.py` — Step 1 tab
- `ui/tab_generate.py` — Step 2 tab
- `ui/sidebar.py` — `_sidebar_institute_info()`
- `ui/templates.py` — `_make_students_template()`, `_make_rooms_template()`, `_make_sample_result_workbook()`
- `utils/workbook.py` — `_merge_workbooks()`, `_df_to_excel_bytes()`

**Issue 6 — no version pins in `requirements.txt`**

Without pinned versions, `pandas`, `openpyxl`, `streamlit`, and `xlsxwriter` can all silently introduce breaking changes on `pip install`. Add:

```
pandas==2.2.*
openpyxl==3.1.*
streamlit==1.35.*
xlsxwriter==3.2.*
reportlab==4.2.*
```

**Issue 7 — no tests, no CI**

The core allocation logic in `exam_seating/service.py` is completely untested. At minimum, add:
- A pytest fixture with a 30-student, 2-room dataset.
- Tests for: all students eligible, none eligible, more students than capacity, alternate seats mode, shuffle reproducibility.
- A `.github/workflows/test.yml` to run tests on push.

**Issue 8 — `_merge_workbooks()` cell-style copy is fragile**

Manually copying `font`, `fill`, `border`, and `alignment` using `copy()` misses several attributes (`number_format`, `protection`, named styles) and is slow for large sheets. A simpler approach for the "all in one" download is to just zip the three separate files and serve a `.zip` — or use `openpyxl`'s `copy_worksheet` if you need a single workbook.

**Issue 9 — silent NaN drops without user feedback**

When attendance values are `"N/A"`, `"-"`, or blank, `pd.to_numeric(..., errors="coerce")` silently converts them to NaN and `dropna()` removes those students entirely. The user never knows. After the drop, show: `st.warning(f"{n} students had unparseable attendance and were excluded.")`.

---

## Task List

| Status | Task | Priority | Scope | Deliverable | Acceptance Criteria |
|---|---|---|---|---|---|
| [x] | Task 1: Re-enable Step 1 Convert UI | P0 | Wire Step 1 and Step 2 into app entrypoint so both are reachable. | `main()` creates two tabs and calls both flows. | Step 1 renders in Streamlit; extraction workflow can be executed from UI. |
| [x] | Task 2: Add cleanup policy for `web_runs` | P1 | Prevent unbounded growth of run directories. | Delete stale run folders older than a threshold (for example 1 hour) at app startup and/or before a new run. | Old folders are removed automatically; active/current run folders are preserved. |
| [x] | Task 3: Fix branch parsing logic | P1 | Remove hardcoded branch fallback when branch is present in sheet name. | Central parser for `(branch, section)` using sheet name. | `6th ME-B` -> Branch `6th ME`, Section `B`; `6th EC-A` -> Branch `6th EC`, Section `A`; unknown patterns still fall back safely. |
| [x] | Task 4: Add warning for dropped invalid attendance rows | P1 | Make excluded rows visible to users. | Track count of rows dropped after attendance coercion and show warning. | UI shows exact excluded count whenever rows are dropped; remaining valid rows continue processing. |
| [x] | Task 5: Add core allocation tests | P1 | Add automated tests for the seating engine. | Pytest setup + fixture with 30 students and 2 rooms + tests for all eligible, none eligible, overflow capacity, alternate seats, shuffle reproducibility. | Tests pass locally and are deterministic. |
| [x] | Task 6: Add CI workflow for tests | P1 | Run tests automatically on push/PR. | `.github/workflows/test.yml` with Python setup + dependency install + pytest run. | Workflow triggers on push and pull requests; failing tests fail CI. |
| [x] | Task 7: Move inline imports to top-level | P2 | Remove imports from loops/functions where unnecessary. | `streamlit_app.py` imports consolidated at module top. | No inline import in hot paths; lint warnings for inline imports are removed. |
| [x] | Task 8: Pin dependency versions | P2 | Improve reproducibility and reduce dependency drift. | Update `requirements.txt` to pinned compatible versions. | Fresh install is reproducible; app and scripts run with pinned versions. |
| [x] | Task 9: Replace fragile workbook merge approach | P2 | Avoid style-loss and performance issues in merged workbook generation. | Replace all-in-one xlsx merge with zip bundle of generated files (or robust merge utility). | Download contains all outputs; formatting in individual exported files stays intact. |
| [~] | Task 10: Refactor oversized `streamlit_app.py` | P2 | Split large file into maintainable modules. | `ui/tab_convert.py`, `ui/tab_generate.py`, `ui/sidebar.py`, `ui/templates.py`, `utils/workbook.py`. | Module files created and wired in main app flow; full extraction/generation logic migration is in progress. |

## Suggested Execution Order

| Order | Task |
|---|---|
| 1 | Task 1 |
| 2 | Task 3 |
| 3 | Task 4 |
| 4 | Task 2 |
| 5 | Task 5 |
| 6 | Task 6 |
| 7 | Task 8 |
| 8 | Task 7 |
| 9 | Task 9 |
| 10 | Task 10 |

## Additional Findings (May 2026)

| Type | Finding | Impact | Recommended Action |
|---|---|---|---|
| Bug | CI may fail when `pytest -q` cannot import `exam_seating`. | Bare `pytest -q` may not resolve project imports in some CI environments. | Use `python -m pytest -q` in workflow and/or add root-level `conftest.py` for path bootstrap. |
| Bug | `web_runs/` test folders are tracked in git history. | UUID run folders may include real/sensitive student output artifacts. | Untrack committed data using `git rm -r --cached web_runs/` and keep ignore rule active. |
| Warning | Dead functions in `streamlit_app.py`. | Unused code increases maintenance noise and confusion. | Remove or relocate `_sidebar_institute_info()`, `_make_room_exam_config_template()`, and duplicate `_bundle_reports_zip()`. |
| Warning | `ui/tab_convert.py` and `ui/tab_generate.py` are thin wrappers. | Refactor indirection exists without real logic movement. | Move full tab logic into modules or remove wrappers and call tab functions directly. |
| Warning | `exam_seating/result_analyzer.py` appears unused. | Large unused module adds package bloat and ownership ambiguity. | Integrate as active feature or move to separate branch/module until needed. |
| Warning | Function-local imports in `extract_timetable_from_workbook()`. | Lint/readability issues; function appears unused in current app flow. | Move `datetime` and `openpyxl` imports to top-level; decide whether to keep/remove function. |
| Warning | `_get_session_input_dir()` can leave uploads for active sessions. | Files can persist longer than expected while session remains active. | Add session-start cleanup and/or shift to memory-first upload handling where possible. |
| Info | `streamlit==1.35.*` is old for current date. | Potential missed fixes and compatibility/security updates. | Validate on newer Streamlit line and update pin after compatibility checks. |

## Extended Task List

| Status | Task | Priority | Scope | Deliverable | Acceptance Criteria |
|---|---|---|---|---|---|
| [x] | Task 11: Harden CI pytest invocation | P1 | Ensure CI import path resolution is stable. | Update workflow to `python -m pytest -q` and/or add `conftest.py` path bootstrap. | CI uses `python -m pytest -q` to avoid module path import failures. |
| [x] | Task 12: Untrack committed `web_runs` artifacts | P0 | Remove generated student artifacts from repository tracking. | Untrack `web_runs/` from git index and preserve ignore behavior. | `git rm -r --cached web_runs/` applied; future generated files remain ignored. |
| [x] | Task 13: Remove dead helper functions | P2 | Eliminate unused helpers from `streamlit_app.py`. | Delete or relocate `_sidebar_institute_info`, `_make_room_exam_config_template`, and duplicate `_bundle_reports_zip`. | Unused helper functions removed and shared zip utility reused. |
| [x] | Task 14: Complete tab module refactor | P2 | Move real tab logic into `ui/tab_convert.py` and `ui/tab_generate.py`. | Streamlit app imports and runs tab implementations from module files directly. | Full tab logic now lives in ui modules; `streamlit_app.py` is a lightweight entrypoint. |
| [x] | Task 15: Resolve unused `result_analyzer` module direction | P3 | Decide keep/integrate/archive strategy for `exam_seating/result_analyzer.py`. | Either wire module into product feature or move out of main path. | Implementation moved to `experimental/result_analyzer.py` with compatibility shim and ownership boundary. |
| [x] | Task 16: Move function-local imports to top-level | P3 | Improve readability and lint consistency in extractor utilities. | Top-level imports for `datetime` and `openpyxl` in converter module. | Function-local imports removed from extractor utility. |
| [x] | Task 17: Improve upload lifecycle handling | P2 | Reduce chance of stale per-session upload files. | Session-start cleanup or memory-first upload strategy update. | Session cleanup plus per-session latest-file retention keeps uploads bounded and predictable. |
| [x] | Task 18: Rebaseline Streamlit version pin | P2 | Modernize dependency while preserving app compatibility. | Upgrade Streamlit pin after compatibility testing and fixups. | Streamlit pin updated to `1.44.*`, installed (`1.44.1`), and tests passed. |




