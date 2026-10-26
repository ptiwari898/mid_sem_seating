"""
Streamlit entrypoint for the SIRT Exam Seating System (modular UI).

Two pages share this entry point:
  - Seating & Results: the coordinator's tabs (seating plan, result analysis, saved data).
  - Marks Entry (/marks-entry): the page teachers open with a session PIN.
"""
from __future__ import annotations

import streamlit as st

from ui.marks_entry import render_teacher_marks_entry
from ui.runtime import cleanup_old_web_runs
from ui.sidebar import sidebar_institute_info
from ui.tab_data_management import render_tab_data_management
from ui.tab_generate import render_tab_generate
from ui.tab_result_analysis import render_tab_result_analysis


def coordinator_page() -> None:
    info = sidebar_institute_info()
    st.caption(f"• {info['institute']}  •  {info['department']}")

    tab1, tab2, tab3 = st.tabs([
        "Seating Plan",
        "Result Analysis",
        "Data & Coordinator",
    ])

    with tab1:
        render_tab_generate(info)
    with tab2:
        render_tab_result_analysis()
    with tab3:
        render_tab_data_management()


def marks_entry_page() -> None:
    st.header("Marks Entry")
    render_teacher_marks_entry()


def main() -> None:
    cleanup_old_web_runs()

    st.set_page_config(
        page_title="SIRT Exam Seating System",
        page_icon="🪑",
        layout="wide",
    )

    navigation = st.navigation(
        [
            st.Page(coordinator_page, title="Seating & Results", icon="🪑", default=True),
            st.Page(marks_entry_page, title="Marks Entry", icon="📝", url_path="marks-entry"),
        ]
    )
    navigation.run()


if __name__ == "__main__":
    main()
