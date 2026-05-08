from __future__ import annotations

import streamlit as st

from ui.runtime import cleanup_old_web_runs
from ui.sidebar import sidebar_institute_info
from ui.tab_convert import render_tab_convert
from ui.tab_generate import render_tab_generate


def main() -> None:
    cleanup_old_web_runs()

    st.set_page_config(
        page_title="SIRT Exam Seating System",
        page_icon="🪑",
        layout="wide",
    )
    st.title("SIRT - Automatic Exam Seating Arrangement")

    info = sidebar_institute_info()
    tab_convert_view, tab_generate_view = st.tabs([
        "Step 1 - Convert Workbook",
        "Step 2 - Generate Plan",
    ])

    with tab_convert_view:
        render_tab_convert()
    with tab_generate_view:
        render_tab_generate(info)


if __name__ == "__main__":
    main()
