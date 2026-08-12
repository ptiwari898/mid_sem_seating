"""
Streamlit entrypoint for the SIRT Exam Seating System (modular UI).
This file initializes runtime housekeeping, the DB, and mounts UI tabs.
"""
from __future__ import annotations

import streamlit as st

from ui.runtime import cleanup_old_web_runs
from ui.sidebar import sidebar_institute_info
from ui.tab_generate import render_tab_generate
from ui.tab_result_analysis import render_tab_result_analysis
from ui.tab_data_management import render_tab_data_management


def main() -> None:
    cleanup_old_web_runs()

    st.set_page_config(
        page_title="SIRT Exam Seating System",
        page_icon="🪑",
        layout="wide",
    )

    info = sidebar_institute_info()
    st.caption(f"• {info['institute']}  •  {info['department']}")

    tab1, tab2, tab3 = st.tabs([
        "Seating Plan",
        "Result Analysis",
        "Data & Marks Management",
    ])

    with tab1:
        render_tab_generate(info)
    with tab2:
        render_tab_result_analysis()
    with tab3:
        render_tab_data_management()


if __name__ == "__main__":
    main()