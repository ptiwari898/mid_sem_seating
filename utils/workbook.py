from __future__ import annotations

import io
import zipfile
from pathlib import Path

ZIP_MIME = "application/zip"


def bundle_reports_zip(paths: list[Path], archive_names: list[str]) -> bytes:
    """Bundle generated reports into a single zip download without rewriting workbooks."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, archive_name in zip(paths, archive_names):
            zf.writestr(archive_name, path.read_bytes())
    return buf.getvalue()
