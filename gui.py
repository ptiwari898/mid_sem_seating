from __future__ import annotations

import csv
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from exam_seating.io_utils import DataValidationError
from exam_seating.service import SeatingConfig, run_seating_system


class SeatingApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Exam Seating Arrangement")
        self.geometry("700x490")
        self.resizable(False, False)

        self.students_path = tk.StringVar()
        self.rooms_path = tk.StringVar()
        self.output_dir = tk.StringVar(value="output")
        self.attendance_cutoff = tk.StringVar(value="40")
        self.shuffle = tk.BooleanVar(value=False)
        self.seed = tk.StringVar(value="")
        self.alternate_seats = tk.BooleanVar(value=False)
        self.export_pdf = tk.BooleanVar(value=False)

        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        # Template download row
        tpl_frame = ttk.Frame(frame)
        tpl_frame.grid(row=0, column=0, columnspan=2, sticky="we", pady=(0, 8))
        ttk.Label(tpl_frame, text="Need a template?").pack(side=tk.LEFT)
        ttk.Button(tpl_frame, text="Download Students Template", command=self._save_students_template).pack(side=tk.LEFT, padx=(10, 4))
        ttk.Button(tpl_frame, text="Download Rooms Template", command=self._save_rooms_template).pack(side=tk.LEFT, padx=4)

        ttk.Label(frame, text="Students File (CSV/Excel)").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.students_path, width=60).grid(row=2, column=0, sticky="we")
        ttk.Button(frame, text="Browse", command=self._browse_students).grid(row=2, column=1, padx=8)

        ttk.Label(frame, text="Rooms File (CSV/Excel)").grid(row=3, column=0, sticky="w", pady=(12, 0))
        ttk.Entry(frame, textvariable=self.rooms_path, width=60).grid(row=4, column=0, sticky="we")
        ttk.Button(frame, text="Browse", command=self._browse_rooms).grid(row=4, column=1, padx=8)

        ttk.Label(frame, text="Output Directory").grid(row=5, column=0, sticky="w", pady=(12, 0))
        ttk.Entry(frame, textvariable=self.output_dir, width=60).grid(row=6, column=0, sticky="we")
        ttk.Button(frame, text="Browse", command=self._browse_output).grid(row=6, column=1, padx=8)

        options = ttk.Frame(frame)
        options.grid(row=7, column=0, columnspan=2, sticky="we", pady=(16, 0))

        ttk.Label(options, text="Attendance Cutoff (%)").grid(row=0, column=0, sticky="w")
        ttk.Entry(options, textvariable=self.attendance_cutoff, width=10).grid(row=0, column=1, sticky="w", padx=(8, 20))

        ttk.Checkbutton(options, text="Shuffle Students", variable=self.shuffle).grid(row=0, column=2, sticky="w")
        ttk.Label(options, text="Seed").grid(row=0, column=3, sticky="w", padx=(12, 0))
        ttk.Entry(options, textvariable=self.seed, width=10).grid(row=0, column=4, sticky="w", padx=(8, 0))

        ttk.Checkbutton(
            options,
            text="Use Alternate Seats",
            variable=self.alternate_seats,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        ttk.Checkbutton(
            options,
            text="Export PDF (requires reportlab)",
            variable=self.export_pdf,
        ).grid(row=1, column=2, columnspan=3, sticky="w", pady=(8, 0))

        ttk.Button(frame, text="Generate Seating Plan", command=self._generate).grid(
            row=8, column=0, columnspan=2, pady=(22, 0)
        )

        self.status = tk.Text(frame, height=8, width=80)
        self.status.grid(row=9, column=0, columnspan=2, pady=(14, 0))
        self.status.configure(state=tk.DISABLED)

    def _save_students_template(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="students_template.csv",
            title="Save Students Template",
        )
        if not path:
            return
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Roll Number", "Name", "Attendance Percentage"])
            writer.writerow(["1001", "Example Student 1", "85"])
            writer.writerow(["1002", "Example Student 2", "42"])
        messagebox.showinfo("Template Saved", f"Students template saved to:\n{path}")

    def _save_rooms_template(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="rooms_template.csv",
            title="Save Rooms Template",
        )
        if not path:
            return
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Room Number", "Capacity"])
            writer.writerow(["A101", "30"])
            writer.writerow(["A102", "30"])
        messagebox.showinfo("Template Saved", f"Rooms template saved to:\n{path}")

    def _browse_students(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("CSV/Excel", "*.csv *.xlsx *.xls"), ("All files", "*.*")]
        )
        if path:
            self.students_path.set(path)

    def _browse_rooms(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("CSV/Excel", "*.csv *.xlsx *.xls"), ("All files", "*.*")]
        )
        if path:
            self.rooms_path.set(path)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)

    def _append_status(self, text: str) -> None:
        self.status.configure(state=tk.NORMAL)
        self.status.insert(tk.END, text + "\n")
        self.status.see(tk.END)
        self.status.configure(state=tk.DISABLED)

    def _generate(self) -> None:
        students = self.students_path.get().strip()
        rooms = self.rooms_path.get().strip()

        if not students or not rooms:
            messagebox.showerror("Missing Input", "Please select both student and room files.")
            return

        try:
            cutoff = float(self.attendance_cutoff.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Attendance cutoff must be a number.")
            return

        seed_text = self.seed.get().strip()
        seed = int(seed_text) if seed_text else None

        config = SeatingConfig(
            students_file=students,
            rooms_file=rooms,
            attendance_cutoff=cutoff,
            output_dir=self.output_dir.get().strip() or str(Path("output")),
            shuffle_students=self.shuffle.get(),
            random_seed=seed,
            alternate_seats=self.alternate_seats.get(),
            export_pdf_file=self.export_pdf.get(),
        )

        try:
            result = run_seating_system(config)
        except (FileNotFoundError, DataValidationError) as exc:
            messagebox.showerror("Failed", str(exc))
            return
        except Exception as exc:  # pragma: no cover
            messagebox.showerror("Failed", f"Unexpected error: {exc}")
            return

        self._append_status("Generation complete.")
        self._append_status(f"Total students: {result.summary.total_students}")
        self._append_status(f"Eligible: {result.summary.eligible_students}")
        self._append_status(f"Allocated: {result.summary.allocated_students}")
        self._append_status(f"Unallocated: {result.summary.unallocated_students}")
        self._append_status("Generated files:")
        for path in result.generated_files:
            self._append_status(f"  {path}")

        if config.export_pdf_file and not result.pdf_generated:
            self._append_status("PDF export skipped because reportlab is not installed.")

        messagebox.showinfo("Success", "Seating plan generated successfully.")


def main() -> None:
    app = SeatingApp()
    app.mainloop()


if __name__ == "__main__":
    main()
