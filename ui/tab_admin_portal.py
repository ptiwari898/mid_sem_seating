from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from teacher_portal import auth
from teacher_portal import db


def _export_filename(exam_session: str) -> str:
    safe_session = "_".join(exam_session.split())
    return f"mid_sem_result_{safe_session}.xlsx"


def render_tab_admin_portal() -> None:
    st.header("Admin Portal")

    admin_password = st.secrets.get("ADMIN_PASSWORD")
    if not admin_password:
        st.error("Set ADMIN_PASSWORD in .streamlit/secrets.toml before using the Admin Portal.")
        return

    if "admin_portal_authenticated" not in st.session_state:
        st.session_state["admin_portal_authenticated"] = False

    if not st.session_state["admin_portal_authenticated"]:
        password = st.text_input("Admin Password", type="password", key="admin_portal_password")
        if st.button("Login", key="admin_portal_login"):
            if password == admin_password:
                st.session_state["admin_portal_authenticated"] = True
                st.rerun()
            st.error("Invalid admin password.")
        return

    top_left, top_right = st.columns([5, 1])
    top_left.caption("Manage teachers, session-wise assignments, and submitted mid-sem marks.")
    if top_right.button("Logout", key="admin_portal_logout"):
        st.session_state["admin_portal_authenticated"] = False
        st.rerun()

    st.subheader("Teachers")
    teachers = db.get_all_teachers()
    if teachers:
        teacher_df = pd.DataFrame([{"ID": t.id, "Name": t.name, "Email": t.email} for t in teachers])
        st.dataframe(teacher_df, use_container_width=True, hide_index=True)
    else:
        st.info("No teachers added yet.")

    with st.form("admin_add_teacher_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 2, 1])
        teacher_name = c1.text_input("Teacher Name")
        teacher_email = c2.text_input("Teacher Email")
        create_teacher = c3.form_submit_button("Add Teacher")

    if create_teacher:
        if not teacher_name.strip() or not teacher_email.strip():
            st.error("Teacher name and email are required.")
        else:
            teacher_code = auth.generate_code()
            try:
                db.add_teacher(teacher_name, teacher_email, auth.hash_code(teacher_code))
                st.success(
                    "Teacher created successfully. One-time login code: "
                    f"`{teacher_code}`"
                )
            except Exception as exc:
                st.error(f"Could not create teacher: {exc}")

    st.divider()
    st.subheader("Assignments")
    assignments = db.get_all_assignments()
    teacher_lookup = {teacher.id: teacher.name for teacher in teachers}
    if assignments:
        assignment_df = pd.DataFrame(
            [
                {
                    "Teacher": teacher_lookup.get(a.teacher_id, str(a.teacher_id)),
                    "Exam Session": a.exam_session,
                    "Class": a.class_name,
                    "Subject": a.subject,
                    "Subject Code": a.subject_code,
                    "Max Marks": a.max_marks,
                }
                for a in assignments
            ]
        )
        st.dataframe(assignment_df, use_container_width=True, hide_index=True)
    else:
        st.info("No assignments created yet.")

    if not teachers:
        st.caption("Add at least one teacher before creating assignments.")
    else:
        teacher_options = {
            f"{teacher.name} ({teacher.email})": teacher.id
            for teacher in teachers
        }
        with st.form("admin_add_assignment_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            selected_teacher = c1.selectbox("Teacher", list(teacher_options.keys()))
            exam_session = c2.text_input("Exam Session", value="Jan-Jun 2026")
            c3, c4 = st.columns(2)
            class_name = c3.text_input("Class Name", value="6th Sem CSIT A")
            subject = c4.text_input("Subject")
            c5, c6 = st.columns(2)
            subject_code = c5.text_input("Subject Code")
            max_marks = c6.number_input("Max Marks", min_value=1, max_value=100, value=30, step=1)
            save_assignment = st.form_submit_button("Save Assignment")

        if save_assignment:
            if not exam_session.strip() or not class_name.strip() or not subject.strip() or not subject_code.strip():
                st.error("Exam session, class, subject, and subject code are required.")
            else:
                try:
                    db.add_assignment(
                        teacher_id=teacher_options[selected_teacher],
                        exam_session=exam_session,
                        class_name=class_name,
                        subject=subject,
                        subject_code=subject_code,
                        max_marks=int(max_marks),
                    )
                    st.success("Assignment saved.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not save assignment: {exc}")

    st.divider()
    st.subheader("Submitted Marks")
    summary_df = db.get_all_marks_summary()
    if summary_df.empty:
        st.info("No marks submitted yet.")
        return

    col1, col2, col3 = st.columns(3)
    selected_session = col1.selectbox(
        "Exam Session",
        ["All"] + sorted(summary_df["exam_session"].dropna().unique().tolist(), reverse=True),
        key="admin_marks_session_filter",
    )
    filtered_df = db.get_all_marks_summary(selected_session)
    selected_class = col2.selectbox(
        "Class",
        ["All"] + sorted(filtered_df["class_name"].dropna().unique().tolist()),
        key="admin_marks_class_filter",
    )
    if selected_class != "All":
        filtered_df = filtered_df[filtered_df["class_name"] == selected_class]
    selected_subject = col3.selectbox(
        "Subject",
        ["All"] + sorted(filtered_df["subject"].dropna().unique().tolist()),
        key="admin_marks_subject_filter",
    )
    if selected_subject != "All":
        filtered_df = filtered_df[filtered_df["subject"] == selected_subject]

    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    export_session = selected_session if selected_session != "All" else "all_sessions"
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        filtered_df.to_excel(writer, sheet_name="Mid-Sem Marks", index=False)
    st.download_button(
        "Download Excel",
        data=output.getvalue(),
        file_name=_export_filename(export_session),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="admin_download_marks",
    )
