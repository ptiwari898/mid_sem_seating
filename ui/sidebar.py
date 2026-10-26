from __future__ import annotations

import streamlit as st


def sidebar_institute_info() -> dict:
    """Show the institute as the sidebar title; the editable fields stay folded away."""
    brand = st.sidebar.empty()

    with st.sidebar.expander("Institute details"):
        institute = st.text_input("Institute name", "SAGAR INSTITUTE OF RESEARCH & TECHNOLOGY")
        department = st.text_input("Department", "DEPARTMENT OF CSIT")
        exam_title = st.text_input("Exam title", "I MID SEM EXAMINATION (JAN-JUN 2026)")
        semester = st.text_input("Semester", "6th Sem")

    brand.markdown(f"**{institute}**  \n{department}")

    return {
        "institute": institute,
        "department": department,
        "exam_title": exam_title,
        "semester": semester,
    }
