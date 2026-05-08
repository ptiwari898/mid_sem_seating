from __future__ import annotations

from typing import Callable


def render_tab_convert(tab_callback: Callable[[], None]) -> None:
    """Render Step 1 tab using an injected callback."""
    tab_callback()
