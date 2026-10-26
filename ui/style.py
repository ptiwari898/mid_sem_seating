"""Shared look for every page. Colours, radii of controls and heading sizes live in
.streamlit/config.toml; this file only adds what the theme cannot express.

Rules (keep new UI inside them):
  - One accent colour (primaryColor). Dark is the default; light is a CSS switch (theme_toggle).
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


# Light mode inverts the dark theme and turns the hues back, so blues stay blue and reds stay red.
# Streamlit cannot change its theme at run time (that needs a page reload, which would lose
# uploaded files and open sessions), so this is done in CSS and works instantly.
_LIGHT_CSS = """
<style>
[data-testid="stApp"] { filter: invert(1) hue-rotate(180deg); }
</style>
"""

_TOGGLE_CSS = """
<style>
.st-key-theme_toggle { position: fixed; left: 1rem; bottom: 1rem; z-index: 1000001; width: auto; }
.st-key-theme_toggle button { box-shadow: 0 1px 6px rgba(0, 0, 0, 0.35); }
</style>
"""


def _flip_theme() -> None:
    st.session_state["theme"] = "light" if st.session_state.get("theme", "dark") == "dark" else "dark"


def theme_toggle() -> None:
    """Dark/light switch pinned to the bottom left of every page. Dark is the default."""
    dark = st.session_state.get("theme", "dark") == "dark"
    st.markdown(_TOGGLE_CSS if dark else _TOGGLE_CSS + _LIGHT_CSS, unsafe_allow_html=True)
    with st.container(key="theme_toggle"):
        st.button(
            "Light mode" if dark else "Dark mode",
            icon=":material/light_mode:" if dark else ":material/dark_mode:",
            key="theme_button",
            on_click=_flip_theme,
        )


def apply_theme() -> None:
    """Inject the shared stylesheet. Call once per run, before the page is drawn."""
    st.markdown(_CSS, unsafe_allow_html=True)


def hide_sidebar() -> None:
    """For pages with nothing in the sidebar (teachers' and admin pages), so no empty panel shows."""
    st.markdown(
        "<style>[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl'],"
        " [data-testid='stExpandSidebarButton'] { display: none; }</style>",
        unsafe_allow_html=True,
    )


def narrow_page(max_width_px: int = 720) -> None:
    """Centre the page in a narrow column (the teachers' PIN and marks page)."""
    st.markdown(
        f"<style>.block-container {{ max-width: {max_width_px}px; }}</style>",
        unsafe_allow_html=True,
    )
