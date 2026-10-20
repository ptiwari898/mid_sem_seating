import pandas as pd
import pytest
from exam_seating.allocator import split_eligibility

def test_split_eligibility_basic():
    df = pd.DataFrame({
        "Roll Number": ["1", "2", "3", "4"],
        "Name": ["A", "B", "C", "D"],
        "Attendance Percentage": [75.0, 35.0, 40.0, 100.0]
    })
    cutoff = 40.0
    eligible, not_eligible = split_eligibility(df, cutoff)

    assert len(eligible) == 3
    assert len(not_eligible) == 1
    assert all(eligible["Attendance Percentage"] >= cutoff)
    assert all(not_eligible["Attendance Percentage"] < cutoff)
    assert "2" in not_eligible["Roll Number"].values
    assert "3" in eligible["Roll Number"].values
    # Verify index is reset
    assert eligible.index.tolist() == [0, 1, 2]
    assert not_eligible.index.tolist() == [0]

def test_split_eligibility_all_eligible():
    df = pd.DataFrame({
        "Attendance Percentage": [40.0, 50.0, 60.0]
    })
    eligible, not_eligible = split_eligibility(df, 40.0)
    assert len(eligible) == 3
    assert len(not_eligible) == 0
    assert eligible.index.tolist() == [0, 1, 2]

def test_split_eligibility_none_eligible():
    df = pd.DataFrame({
        "Attendance Percentage": [10.0, 20.0, 30.0]
    })
    eligible, not_eligible = split_eligibility(df, 40.0)
    assert len(eligible) == 0
    assert len(not_eligible) == 3
    assert not_eligible.index.tolist() == [0, 1, 2]

def test_split_eligibility_empty():
    df = pd.DataFrame(columns=["Attendance Percentage"])
    eligible, not_eligible = split_eligibility(df, 40.0)
    assert len(eligible) == 0
    assert len(not_eligible) == 0

def test_split_eligibility_boundary():
    df = pd.DataFrame({
        "Attendance Percentage": [39.9, 40.0, 40.1]
    })
    eligible, not_eligible = split_eligibility(df, 40.0)
    assert len(eligible) == 2
    assert len(not_eligible) == 1
    assert 40.0 in eligible["Attendance Percentage"].values
    assert 39.9 in not_eligible["Attendance Percentage"].values
