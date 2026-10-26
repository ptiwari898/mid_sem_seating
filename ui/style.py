"""Shared look for every page. Colours, radii of controls and heading sizes live in
.streamlit/config.toml; this file only adds what the theme cannot express.

Rules (keep new UI inside them):
  - One accent colour per mode (primaryColor). Neutrals follow the system light/dark setting.
  - Two corner radii: 8px for controls (the theme's baseRadius), 12px for containers (cards,
    forms, expanders, metrics).
  - Icons are Material icons (":material/name:"), never emoji.
  - Content is at most 1080px wide; the teachers' page is narrower (see narrow_page).
"""
from __future__ import annotations

import streamlit as st

_BORDER = "rgba(128, 128, 128, 0.28)"
_SURFACE = "rgba(128, 128, 128, 0.07)"

_CSS = f"""
<style>
[data-testid="stDecoration"] {{ display: none; }}

.block-container {{ max-width: 1080px; padding-top: 2.5rem; padding-bottom: 4rem; }}

/* containers: 12px */
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stForm"],
[data-testid="stExpander"], [data-testid="stFileUploaderDropzone"],
[data-testid="stAlert"] {{ border-radius: 12px !important; }}
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stForm"] {{
    border-color: {_BORDER} !important;
}}
[data-testid="stMetric"] {{
    background: {_SURFACE}; border: 1px solid {_BORDER}; border-radius: 12px;
    padding: 0.75rem 1rem;
}}
[data-testid="stMetricValue"] {{ font-variant-numeric: tabular-nums; }}

[data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap: 0.5rem; }}
[data-testid="stSidebar"] [data-testid="stExpander"] {{ border-radius: 12px; }}
[data-testid="stCaptionContainer"] {{ line-height: 1.45; }}
hr {{ margin: 1.25rem 0; opacity: 0.5; }}
</style>
"""


def apply_theme() -> None:
    """Inject the shared stylesheet. Call once per run, before the page is drawn."""
    st.markdown(_CSS, unsafe_allow_html=True)


def narrow_page(max_width_px: int = 640) -> None:
    """Centre the page in a narrow column (the teachers' PIN and marks page)."""
    st.markdown(
        f"<style>.block-container {{ max-width: {max_width_px}px; }}</style>",
        unsafe_allow_html=True,
    )
