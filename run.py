"""
run.py — Streamlit launcher for the Automatic Exam Seating Arrangement System.

Usage:
    python run.py
    python run.py web
    python run.py streamlit
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent


def run_streamlit() -> None:
    print("Starting Streamlit web app...")
    print("Open  http://localhost:8501  in your browser.")
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(BASE / "streamlit_app.py")],
        check=True,
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        dispatch = {"web": run_streamlit, "streamlit": run_streamlit}
        if mode not in dispatch:
            print(f"Unknown mode '{mode}'. Use: web | streamlit")
            sys.exit(1)
        dispatch[mode]()
    else:
        run_streamlit()
