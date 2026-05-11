from __future__ import annotations

import streamlit as st

from teacher_portal.db import init_db
from ui.runtime import cleanup_old_web_runs
from ui.sidebar import sidebar_institute_info
from ui.tab_admin_portal import render_tab_admin_portal
from ui.tab_generate import render_tab_generate
from ui.tab_result_analysis import render_tab_result_analysis
from ui.tab_teacher_portal import render_tab_teacher_portal


def main() -> None:
    cleanup_old_web_runs()
    init_db()

    st.set_page_config(
        page_title="SIRT Exam Seating System",
        page_icon="🪑",
        layout="wide",
    )
    st.title("SIRT - Automatic Exam Seating Arrangement")

    info = sidebar_institute_info()
    tab_seating, tab_result, tab_admin, tab_teacher = st.tabs([
        "Seating Plan",
        "Result Analysis",
        "Admin Portal",
        "Teacher Portal",
    ])

    with tab_seating:
        render_tab_generate(info)
    with tab_result:
        render_tab_result_analysis()
    with tab_admin:
        render_tab_admin_portal()
    with tab_teacher:
        render_tab_teacher_portal()


if __name__ == "__main__":
    main()
