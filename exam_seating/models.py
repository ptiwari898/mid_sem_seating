from dataclasses import dataclass


@dataclass(frozen=True)
class SeatingSummary:
    total_students: int
    eligible_students: int
    not_eligible_students: int
    allocated_students: int
    unallocated_students: int
    room_count: int
    total_capacity: int
    effective_capacity: int
