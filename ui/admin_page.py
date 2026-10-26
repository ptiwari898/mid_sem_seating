"""Admin / coordinator page: every generated seating plan and every marks entry."""
from __future__ import annotations

import hmac
import time

import pandas as pd
import streamlit as st

from exam_seating import marks_store
from ui.marks_entry import lockout_seconds_left


def _unlocked() -> bool:
    """Password gate. ADMIN_PASSWORD comes from the app secrets; wrong tries lock the form."""
    password = st.secrets.get("ADMIN_PASSWORD")
    if not password:
        st.info("Set ADMIN_PASSWORD in the app secrets to use the admin page.")
        return False
    if st.session_state.get("coordinator_ok"):
        return True

    typed = st.text_input("Admin password", type="password", key="co_password")
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
    return False


def _csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def _delete_button(label: str, key: str, on_confirm) -> None:
    """Deleting cannot be undone, so it needs a ticked confirmation box first."""
    sure = st.checkbox("I am sure", key=f"{key}_sure")
    if st.button(label, key=key, disabled=not sure):
        on_confirm()
        st.rerun()


def _render_plans(sessions_by_id: dict[int, marks_store.SessionSummary]) -> None:
    plans = marks_store.list_plans()
    if not plans:
        st.info("No seating plans yet. Plans are saved here each time one is generated.")
        return
    st.caption(f"{len(plans)} saved plan(s), newest first.")
    for plan in plans:
        with st.expander(f"#{plan.id} · {plan.exam_title} · {plan.semester} · {plan.created_at}"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Students", plan.total)
            c2.metric("Eligible", plan.eligible)
            c3.metric("Debarred", plan.debarred)
            c4.metric("Allocated", plan.allocated)
            st.caption(f"{plan.department} · attendance cutoff {plan.cutoff:g}%")

            if plan.rooms:
                st.dataframe(pd.DataFrame(plan.rooms), use_container_width=True, hide_index=True)
            if plan.session_id is None:
                st.caption("No marks entry was opened with this plan.")
            elif plan.session_id in sessions_by_id:
                linked = sessions_by_id[plan.session_id]
                st.caption(f"Marks entry opened with this plan: session #{linked.id}, PIN {linked.pin}.")
            else:
                st.caption("The marks session opened with this plan was deleted.")

            archive = marks_store.get_plan_archive(plan.id)
            if archive:
                st.download_button(
                    "Download all reports (.zip)", data=archive,
                    file_name=f"SIRT_Reports_plan_{plan.id}.zip", mime="application/zip",
                    key=f"plan_dl_{plan.id}",
                )
            _delete_button("Delete plan", f"plan_del_{plan.id}", lambda p=plan.id: marks_store.delete_plan(p))


def _render_marks(sessions: list[marks_store.SessionSummary]) -> None:
    if not sessions:
        st.info("No marks entries yet. Tick the marks-entry option when generating a seating plan.")
        return
    for item in sessions:
        status = "locked" if item.locked else ("expired" if item.expired else "open")
        with st.expander(f"#{item.id} · {item.exam_title} · created {item.created_at} · {status}"):
            st.write(f"PIN: **{item.pin}**")
            st.progress(
                item.entries / item.slots if item.slots else 0.0,
                text=f"{item.entries} of {item.slots} entries done",
            )
            st.dataframe(marks_store.subject_progress(item.id), use_container_width=True, hide_index=True)

            marks = marks_store.export_marks(item.id)
            st.markdown("**All marks** (AB = absent, blank = not entered yet)")
            st.dataframe(marks, use_container_width=True, hide_index=True)

            c1, c2, c3 = st.columns(3)
            c1.download_button(
                "Download marks (CSV)", data=_csv(marks), file_name=f"marks_{item.id}.csv",
                mime="text/csv", key=f"co_dl_{item.id}",
            )
            c2.download_button(
                "Edit history (CSV)", data=_csv(marks_store.export_history(item.id)),
                file_name=f"marks_history_{item.id}.csv", mime="text/csv", key=f"co_hist_{item.id}",
            )
            if c3.button("Unlock" if item.locked else "Lock (finalise)", key=f"co_lock_{item.id}"):
                marks_store.set_locked(item.id, not item.locked)
                st.rerun()
            _delete_button("Delete marks session", f"co_del_{item.id}", lambda s=item.id: marks_store.delete_session(s))


def _render_backup() -> None:
    st.caption(
        "The database is a file on the server and can be lost when the app restarts or is "
        "redeployed. Download a backup after each round and restore it if that happens. "
        "It contains plans, marks sessions, PINs and edit history."
    )
    b1, b2 = st.columns(2)
    b1.download_button(
        "Download full backup", data=marks_store.backup_bytes(),
        file_name="marks_backup.db", mime="application/octet-stream", key="co_backup",
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


def render_admin_page() -> None:
    st.header("Admin / Coordinator")
    if not _unlocked():
        return

    if st.button("Lock", key="co_lock_page"):
        st.session_state["coordinator_ok"] = False
        st.rerun()

    sessions = marks_store.list_sessions()
    plans_tab, marks_tab, backup_tab = st.tabs(["Seating plans", "Marks entries", "Backup"])
    with plans_tab:
        _render_plans({s.id: s for s in sessions})
    with marks_tab:
        _render_marks(sessions)
    with backup_tab:
        _render_backup()
