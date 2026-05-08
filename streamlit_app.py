from __future__ import annotations

import streamlit as st

from ui.runtime import cleanup_old_web_runs
from ui.sidebar import sidebar_institute_info
from ui.tab_generate import render_tab_generate
from ui.tab_result_analysis import render_tab_result_analysis


def main() -> None:
    cleanup_old_web_runs()

    st.set_page_config(
        page_title="SIRT Exam Seating System",
        page_icon="🪑",
        layout="wide",
    )
    st.title("SIRT - Automatic Exam Seating Arrangement")

    info = sidebar_institute_info()
    tab_seating, tab_result = st.tabs([
        "Seating Plan",
        "Result Analysis",
    ])

    with tab_seating:
        render_tab_generate(info)
    with tab_result:
        render_tab_result_analysis()


if __name__ == "__main__":
    main()
