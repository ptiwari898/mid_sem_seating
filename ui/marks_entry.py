from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from exam_seating import marks_store

MAX_PIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 900


def lockout_seconds_left(
    failed_attempts: int, last_failure: float, now: float | None = None
) -> int:
    """Seconds a PIN form stays blocked after too many wrong tries; 0 means try again."""
    if failed_attempts < MAX_PIN_ATTEMPTS:
        return 0
    elapsed = (time.time() if now is None else now) - last_failure
    return max(0, int(LOCKOUT_SECONDS - elapsed))


def show_active_pin(slot=None) -> None:
    """Remind the coordinator of the PIN made in this browser session.

    Pass the same st.empty() slot on every call in one run: a later call replaces
    the earlier output. The download button gets a fresh key each call because
    Streamlit rejects a repeated key within one run even when the slot is replaced.
    """
    info = st.session_state.get("marks_session_info")
    if not info:
        return
    st.session_state["_marks_pin_renders"] = st.session_state.get("_marks_pin_renders", 0) + 1
    with (slot.container() if slot is not None else st.container()):
        st.info(
            f"Marks entry is open for **{info['exam_title']}**. "
            f"Teacher PIN: **{info['pin']}** (valid {marks_store.SESSION_DAYS} days). "
            "Teachers enter it on the *Marks Entry* page (link: `/marks-entry`)."
        )
        marks = marks_store.export_marks(info["session_id"])
        st.download_button(
            "Download marks entered so far (CSV)",
            data=marks.to_csv(index=False).encode("utf-8"),
            file_name="marks_entered.csv",
            mime="text/csv",
            key=f"marks_csv_download_{st.session_state['_marks_pin_renders']}",
        )


def open_marks_session(
    exam_title: str, subjects: list[str], eligible: pd.DataFrame, max_marks: float, slot=None
) -> int | None:
    """Create the session from the eligible students and show its PIN. Returns its id."""
    try:
        pin, session = marks_store.create_session(
            exam_title, subjects, eligible, max_marks
        )
    except marks_store.MarksError as exc:
        st.error(str(exc))
        return None
    st.session_state["marks_session_info"] = {
        "pin": pin, "exam_title": session.exam_title, "session_id": session.id,
    }
    show_active_pin(slot)
    return session.id


def render_teacher_marks_entry() -> None:
    """Teacher flow: enter the PIN, pick any subject, enter marks for eligible students."""
    st.subheader("Enter the session PIN")
    st.caption("Use the PIN given by the exam coordinator to load the eligible students.")

    session: marks_store.MarksSession | None = st.session_state.get("teacher_marks_session")

    if session is None:
        pin = st.text_input("Session PIN", type="password", max_chars=6, key="tm_pin")
        if st.button("Open", key="tm_open"):
            wait = lockout_seconds_left(
                st.session_state.get("tm_failed", 0), st.session_state.get("tm_last_failure", 0.0)
            )
            if wait:
                st.error(f"Too many wrong PINs. Try again in {wait // 60 + 1} min.")
                return
            try:
                found = marks_store.find_session(pin) if pin.strip() else None
            except marks_store.MarksError as exc:
                st.error(str(exc))
                return
            if found is None:
                st.session_state["tm_failed"] = st.session_state.get("tm_failed", 0) + 1
                st.session_state["tm_last_failure"] = time.time()
                st.error("Invalid or expired PIN.")
                return
            st.session_state["tm_failed"] = 0
            st.session_state["teacher_marks_session"] = found
            st.rerun()
        return

    top, close = st.columns([5, 1])
    top.success(f"Exam: {session.exam_title}  |  Max marks: {session.max_marks:g}")
    if close.button("Close", key="tm_close"):
        st.session_state.pop("teacher_marks_session")
        st.rerun()

    locked = marks_store.is_locked(session.id)
    if locked:
        st.warning("Marks entry is locked by the coordinator. You can view marks but not change them.")
    subjects = marks_store.list_subjects(session.id)
    subject = st.selectbox(
        "Subject (all subjects are listed)", subjects, format_func=lambda s: s.name, key="tm_subject"
    )
    sections = marks_store.list_sections(session.id)
    section = (
        st.selectbox("Section", ["All"] + sections, key="tm_section") if sections else "All"
    )
    teacher = st.text_input("Your name", key="tm_teacher")

    table = marks_store.get_marks_table(
        session.id, subject.id, None if section == "All" else section
    )
    entered = int((table["Marks"].notna() | table["Absent"]).sum())
    st.caption(f"{entered} of {len(table)} students already have an entry for this subject.")

    edited = st.data_editor(
        table,
        key=f"tm_editor_{session.id}_{subject.id}_{section}",
        hide_index=True,
        use_container_width=True,
        disabled=True if locked else ["Roll Number", "Name", "Branch", "Section"],
        column_config={
            "Marks": st.column_config.NumberColumn(
                "Marks", min_value=0.0, max_value=float(session.max_marks), step=0.5
            ),
            "Absent": st.column_config.CheckboxColumn("Absent"),
        },
    )
    if st.button("💾 Save Marks", type="primary", key="tm_save", disabled=locked):
        if not teacher.strip():
            st.error("Enter your name before saving.")
            return
        try:
            saved = marks_store.save_marks(session, subject.id, edited, teacher, original=table)
        except marks_store.MarksError as exc:
            st.error(str(exc))
            return
        st.success(f"Saved {saved} changed row(s) in {subject.name}.")
