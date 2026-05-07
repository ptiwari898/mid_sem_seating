"""
run.py — Launcher for the Automatic Exam Seating Arrangement System.

Usage:
    python run.py          → interactive menu
    python run.py gui      → launch Tkinter GUI
    python run.py web      → launch Streamlit web app
    python run.py cli      → run CLI with sample data (edit args below)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent


def run_gui() -> None:
    print("Starting Tkinter GUI...")
    from gui import main
    main()


def run_web() -> None:
    print("Starting Streamlit web app...")
    print("Open  http://localhost:8501  in your browser.")
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(BASE / "streamlit_app.py")],
        check=True,
    )


def run_cli() -> None:
    """Run the CLI with sample data. Edit the arguments below as needed."""
    args = [
        sys.executable, str(BASE / "main.py"),
        "--students",        str(BASE / "sample_data" / "students.csv"),
        "--rooms",           str(BASE / "sample_data" / "rooms.csv"),
        "--attendance-cutoff", "40",
        "--output-dir",      str(BASE / "output"),
    ]
    print("Running CLI with sample data...")
    print("Command:", " ".join(args))
    subprocess.run(args, check=True)
    print("\nOutput files written to:", BASE / "output")


MENU = {
    "1": ("Tkinter GUI",          run_gui),
    "2": ("Streamlit Web App",    run_web),
    "3": ("CLI (sample data)",    run_cli),
}


def interactive_menu() -> None:
    print("=" * 50)
    print("  Exam Seating Arrangement System — Launcher")
    print("=" * 50)
    for key, (label, _) in MENU.items():
        print(f"  [{key}] {label}")
    print("  [q] Quit")
    print("=" * 50)
    choice = input("Select an option: ").strip().lower()
    if choice == "q":
        sys.exit(0)
    if choice not in MENU:
        print("Invalid choice.")
        sys.exit(1)
    _, fn = MENU[choice]
    fn()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        dispatch = {"gui": run_gui, "web": run_web, "cli": run_cli}
        if mode not in dispatch:
            print(f"Unknown mode '{mode}'. Use: gui | web | cli")
            sys.exit(1)
        dispatch[mode]()
    else:
        interactive_menu()
