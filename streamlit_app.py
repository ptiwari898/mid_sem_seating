"""
Streamlit entrypoint for the SIRT Exam Seating System (modular UI).

Two pages share this entry point:
  - Seating & Results: seating plan, result analysis and saved students.
  - Marks Entry (/marks-entry): the page teachers open with a session PIN.
  - Admin (/admin): every generated plan and marks entry; needs ADMIN_PASSWORD.
"""
from __future__ import annotations

import streamlit as st

from ui.admin_page import render_admin_page
from ui.marks_entry import render_teacher_marks_entry
from ui.runtime import cleanup_old_web_runs
from ui.sidebar import sidebar_institute_info
from ui.tab_data_management import render_tab_data_management
from ui.tab_generate import render_tab_generate
from ui.tab_result_analysis import render_tab_result_analysis


def coordinator_page() -> None:
    info = sidebar_institute_info()
    st.sidebar.page_link(MARKS_PAGE, label="Marks Entry page (for teachers)", icon="📝")
    st.sidebar.page_link(ADMIN_PAGE, label="Admin page (plans and marks)", icon="🗂️")
    st.caption(f"• {info['institute']}  •  {info['department']}")

    tab1, tab2, tab3 = st.tabs([
        "Seating Plan",
        "Result Analysis",
        "Saved Students",
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


def admin_page() -> None:
    render_admin_page()


# The sidebar navigation is hidden so the teachers' page shows no link to the coordinator
# page. The coordinator reaches Marks Entry through the link above.
COORDINATOR_PAGE = st.Page(coordinator_page, title="Seating & Results", icon="🪑", default=True)
MARKS_PAGE = st.Page(marks_entry_page, title="Marks Entry", icon="📝", url_path="marks-entry")
ADMIN_PAGE = st.Page(admin_page, title="Admin", icon="🗂️", url_path="admin")


def main() -> None:
    cleanup_old_web_runs()

    st.set_page_config(
        page_title="SIRT Exam Seating System",
        page_icon="🪑",
        layout="wide",
    )

    st.navigation([COORDINATOR_PAGE, MARKS_PAGE, ADMIN_PAGE], position="hidden").run()


if __name__ == "__main__":
    main()
