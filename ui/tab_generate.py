from __future__ import annotations

from typing import Callable


def render_tab_generate(tab_callback: Callable[[], None]) -> None:
    """Render Step 2 tab using an injected callback."""
    tab_callback()
