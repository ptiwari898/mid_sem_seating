from __future__ import annotations

import streamlit as st


def sidebar_institute_info() -> dict:
    st.sidebar.header("Institute Info")
    institute = st.sidebar.text_input("Institute Name", "SAGAR INSTITUTE OF RESEARCH & TECHNOLOGY")
    department = st.sidebar.text_input("Department", "DEPARTMENT OF CSIT")
    exam_title = st.sidebar.text_input("Exam Title", "I MID SEM EXAMINATION (JAN-JUN 2026)")
    semester = st.sidebar.text_input("Semester", "6th Sem")

    return {
        "institute": institute,
        "department": department,
        "exam_title": exam_title,
        "semester": semester,
    }
