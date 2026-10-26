from __future__ import annotations

import hmac
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


def render_coordinator_panel() -> None:
    """Coordinator view: find a lost PIN, download marks, delete a session. Needs ADMIN_PASSWORD."""
    st.subheader("🗂️ Coordinator: Marks Sessions")
    password = st.secrets.get("ADMIN_PASSWORD")
    if not password:
        st.caption("Set ADMIN_PASSWORD in the app secrets to manage marks sessions.")
        return

    if not st.session_state.get("coordinator_ok"):
        typed = st.text_input("Coordinator password", type="password", key="co_password")
        if st.button("Unlock", key="co_unlock"):
            wait = lockout_seconds_left(
                st.session_state.get("co_failed", 0), st.session_state.get("co_last_failure", 0.0)
            )
            if wait:
                st.error(f"Too many wrong passwords. Try again in {wait // 60 + 1} min.")
            elif hmac.compare_digest(typed.encode("utf-8"), str(password).encode("utf-8")):
                st.session_state["co_failed"] = 0
                st.session_state["coordinator_ok"] = True
                st.rerun()
            else:
                st.session_state["co_failed"] = st.session_state.get("co_failed", 0) + 1
                st.session_state["co_last_failure"] = time.time()
                st.error("Wrong password.")
        return

    if st.button("Lock", key="co_lock"):
        st.session_state["coordinator_ok"] = False
        st.rerun()

    sessions = marks_store.list_sessions()
    if not sessions:
        st.info("No marks sessions yet. Tick the marks-entry option when generating a seating plan.")
        _backup_controls()
        return
    for item in sessions:
        status = "locked" if item.locked else ("expired" if item.expired else "open")
        with st.expander(f"{item.exam_title} — created {item.created_at} ({status})"):
            st.write(f"PIN: **{item.pin}**")
            st.progress(
                item.entries / item.slots if item.slots else 0.0,
                text=f"{item.entries} of {item.slots} entries done",
            )
            c1, c2, c3, c4 = st.columns(4)
            c1.download_button(
                "Download marks (CSV)",
                data=marks_store.export_marks(item.id).to_csv(index=False).encode("utf-8"),
                file_name=f"marks_{item.id}.csv",
                mime="text/csv",
                key=f"co_dl_{item.id}",
            )
            c2.download_button(
                "Edit history (CSV)",
                data=marks_store.export_history(item.id).to_csv(index=False).encode("utf-8"),
                file_name=f"marks_history_{item.id}.csv",
                mime="text/csv",
                key=f"co_hist_{item.id}",
            )
            if c3.button("Unlock" if item.locked else "Lock (finalise)", key=f"co_lock_{item.id}"):
                marks_store.set_locked(item.id, not item.locked)
                st.rerun()
            if c4.button("Delete session", key=f"co_del_{item.id}"):
                marks_store.delete_session(item.id)
                st.rerun()
    _backup_controls()


def _backup_controls() -> None:
    """Download or restore the whole marks database."""
    st.divider()
    st.caption(
        "The database is a file on the server and can be lost when the app restarts or is "
        "redeployed. Download a backup after each marks round and restore it if that happens."
    )
    b1, b2 = st.columns(2)
    b1.download_button(
        "Download full backup",
        data=marks_store.backup_bytes(),
        file_name="marks_backup.db",
        mime="application/octet-stream",
        key="co_backup",
    )
    restore = b2.file_uploader("Restore from backup", type=["db"], key="co_restore")
    if restore is not None and st.button("Replace current data with this backup", key="co_restore_go"):
        try:
            marks_store.restore_from_bytes(restore.getvalue())
        except marks_store.MarksError as exc:
            st.error(str(exc))
        else:
            st.success("Backup restored.")
            st.rerun()
