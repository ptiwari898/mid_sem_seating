"""
Compatibility shim for the experimental result analyzer.

Ownership decision:
- The result analyzer is currently an experimental feature.
- Runtime seating flow does not depend on it.
- Source implementation lives in experimental/result_analyzer.py.
"""

from __future__ import annotations

from warnings import warn

warn(
    "exam_seating.result_analyzer is experimental and may change. "
    "Use experimental.result_analyzer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from experimental.result_analyzer import *  # noqa: F401,F403
