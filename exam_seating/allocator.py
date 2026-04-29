from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd


def _roll_sort_columns(students: pd.DataFrame) -> pd.DataFrame:
    temp = students.copy()
    temp["_roll_num"] = pd.to_numeric(temp["Roll Number"], errors="coerce")
    temp["_is_numeric"] = temp["_roll_num"].notna()
    temp = temp.sort_values(
        by=["_is_numeric", "_roll_num", "Roll Number"],
        ascending=[False, True, True],
        kind="mergesort",
    )
    return temp.drop(columns=["_roll_num", "_is_numeric"]).reset_index(drop=True)


def split_eligibility(students: pd.DataFrame, attendance_cutoff: float) -> Tuple[pd.DataFrame, pd.DataFrame]:
    eligible = students[students["Attendance Percentage"] >= attendance_cutoff].copy()
    not_eligible = students[students["Attendance Percentage"] < attendance_cutoff].copy()
    return eligible.reset_index(drop=True), not_eligible.reset_index(drop=True)


def allocate_students_to_rooms(
    eligible_students: pd.DataFrame,
    rooms: pd.DataFrame,
    alternate_seats: bool = False,
    shuffle: bool = False,
    random_seed: int | None = None,
) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame, int]:
    if shuffle:
        allocation_pool = eligible_students.sample(frac=1, random_state=random_seed).reset_index(drop=True)
    else:
        allocation_pool = _roll_sort_columns(eligible_students)

    room_allocations: Dict[str, pd.DataFrame] = {}
    cursor = 0
    effective_capacity_total = 0

    for _, room in rooms.iterrows():
        room_no = str(room["Room Number"]).strip()
        capacity = int(room["Capacity"])

        if alternate_seats:
            seat_numbers: List[int] = list(range(1, capacity + 1, 2))
        else:
            seat_numbers = list(range(1, capacity + 1))

        available = len(seat_numbers)
        effective_capacity_total += available

        assigned = allocation_pool.iloc[cursor : cursor + available].copy()
        cursor += len(assigned)

        assigned = assigned.reset_index(drop=True)
        assigned.insert(0, "Seat Number", seat_numbers[: len(assigned)])

        room_allocations[room_no] = assigned[
            ["Seat Number", "Roll Number", "Name", "Attendance Percentage"]
        ]

    unallocated = allocation_pool.iloc[cursor:].copy().reset_index(drop=True)
    return room_allocations, unallocated, allocation_pool, effective_capacity_total
