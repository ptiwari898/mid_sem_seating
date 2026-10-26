from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from exam_seating import marks_store
from ui.marks_entry import LOCKOUT_SECONDS, MAX_PIN_ATTEMPTS, lockout_seconds_left


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(marks_store, "DB_PATH", tmp_path / "marks.db")


@pytest.fixture
def opened():
    students = pd.DataFrame({"Roll Number": ["1", "2", "3"], "Name": ["A", "B", "C"]})
    return marks_store.create_session("Mid Sem", ["Maths", "Physics"], students, max_marks=30)


def test_pin_opens_session_and_wrong_pin_does_not(opened):
    pin, session = opened
    assert len(pin) == 6 and pin.isdigit()
    assert marks_store.find_session(pin) == session
    assert marks_store.find_session("000000" if pin != "000000" else "111111") is None


def test_every_subject_is_listed_and_loads_all_students(opened):
    _, session = opened
    subjects = marks_store.list_subjects(session.id)
    assert [s.name for s in subjects] == ["Maths", "Physics"]
    assert marks_store.get_marks_table(session.id, subjects[0].id)["Roll Number"].tolist() == ["1", "2", "3"]


def test_saved_marks_come_back_and_absent_clears_marks(opened):
    _, session = opened
    maths = marks_store.list_subjects(session.id)[0]
    table = marks_store.get_marks_table(session.id, maths.id)
    table["Marks"] = [25.0, 18.5, 30.0]
    table.loc[1, "Absent"] = True
    marks_store.save_marks(session, maths.id, table, "Prof X")

    saved = marks_store.get_marks_table(session.id, maths.id)
    assert saved["Marks"].tolist()[0] == 25.0
    assert pd.isna(saved["Marks"][1]) and bool(saved["Absent"][1]) is True
    exported = marks_store.export_marks(session.id)
    assert exported["Maths"].tolist() == ["25", "AB", "30"]
    assert exported["Physics"].tolist() == ["", "", ""]


def test_marks_above_maximum_are_rejected(opened):
    _, session = opened
    maths = marks_store.list_subjects(session.id)[0]
    table = marks_store.get_marks_table(session.id, maths.id)
    table["Marks"] = [31.0, 1.0, 2.0]
    with pytest.raises(marks_store.MarksError, match="between 0 and 30"):
        marks_store.save_marks(session, maths.id, table, "Prof X")


def test_subject_of_another_session_cannot_be_written(opened):
    _, session = opened
    other = marks_store.create_session(
        "Other", ["Chem"], pd.DataFrame({"Roll Number": ["9"], "Name": ["Z"]})
    )[1]
    foreign = marks_store.list_subjects(other.id)[0]
    table = marks_store.get_marks_table(session.id, foreign.id)
    with pytest.raises(marks_store.MarksError, match="Unknown subject"):
        marks_store.save_marks(session, foreign.id, table, "Prof X")


def test_expired_session_pin_is_refused(opened, monkeypatch):
    pin, _ = opened
    later = datetime.now() + timedelta(days=marks_store.SESSION_DAYS + 1)
    monkeypatch.setattr(marks_store, "_now", lambda: later)
    assert marks_store.find_session(pin) is None


def test_session_needs_subjects_and_students():
    students = pd.DataFrame({"Roll Number": ["1"], "Name": ["A"]})
    with pytest.raises(marks_store.MarksError):
        marks_store.create_session("X", [" "], students)
    with pytest.raises(marks_store.MarksError):
        marks_store.create_session("X", ["Maths"], students.iloc[0:0])


def test_pin_form_lockout_window():
    assert lockout_seconds_left(MAX_PIN_ATTEMPTS - 1, 100, now=101) == 0
    assert lockout_seconds_left(MAX_PIN_ATTEMPTS, 100, now=101) > 0
    assert lockout_seconds_left(MAX_PIN_ATTEMPTS, 100, now=100 + LOCKOUT_SECONDS) == 0


def test_stale_table_does_not_blank_marks_saved_by_another_teacher(opened):
    _, session = opened
    maths = marks_store.list_subjects(session.id)[0]
    stale = marks_store.get_marks_table(session.id, maths.id)  # teacher A opens blank table

    other = stale.copy()
    other["Marks"] = [20.0, 25.0, 10.0]
    marks_store.save_marks(session, maths.id, other, "Prof B")

    mine = stale.copy()
    mine.loc[2, "Marks"] = 7.0  # teacher A only fills the third row
    assert marks_store.save_marks(session, maths.id, mine, "Prof A", original=stale) == 1

    assert marks_store.get_marks_table(session.id, maths.id)["Marks"].tolist() == [20.0, 25.0, 7.0]


def test_clearing_a_saved_mark_is_still_possible(opened):
    _, session = opened
    maths = marks_store.list_subjects(session.id)[0]
    table = marks_store.get_marks_table(session.id, maths.id)
    table["Marks"] = [20.0, 25.0, 10.0]
    marks_store.save_marks(session, maths.id, table, "Prof A")

    loaded = marks_store.get_marks_table(session.id, maths.id)
    cleared = loaded.copy()
    cleared.loc[0, "Marks"] = float("nan")
    marks_store.save_marks(session, maths.id, cleared, "Prof A", original=loaded)
    assert pd.isna(marks_store.get_marks_table(session.id, maths.id)["Marks"][0])


def test_sections_filter_the_roster_and_old_databases_are_upgraded(tmp_path, monkeypatch):
    import sqlite3

    old = tmp_path / "old.db"
    with sqlite3.connect(old) as conn:  # a database made before Section/Branch existed
        conn.executescript(
            "CREATE TABLE students (session_id INTEGER, roll_no TEXT, name TEXT, "
            "PRIMARY KEY (session_id, roll_no));"
        )
    monkeypatch.setattr(marks_store, "DB_PATH", old)

    students = pd.DataFrame(
        {
            "Roll Number": ["1", "2", "3"],
            "Name": ["A", "B", "C"],
            "Section": ["A", "B", "A"],
            "Branch": ["CSIT", "CSIT", "CSIT"],
        }
    )
    _, session = marks_store.create_session("Mid", ["Maths"], students)
    maths = marks_store.list_subjects(session.id)[0]

    assert marks_store.list_sections(session.id) == ["A", "B"]
    only_a = marks_store.get_marks_table(session.id, maths.id, "A")
    assert only_a["Roll Number"].tolist() == ["1", "3"]
    assert marks_store.get_marks_table(session.id, maths.id)["Roll Number"].tolist() == ["1", "2", "3"]


def test_coordinator_can_list_sessions_with_progress_and_delete_one(opened):
    pin, session = opened
    maths = marks_store.list_subjects(session.id)[0]
    table = marks_store.get_marks_table(session.id, maths.id)
    table.loc[0, "Marks"] = 12.0
    table.loc[1, "Absent"] = True
    marks_store.save_marks(session, maths.id, table, "Prof A")

    (item,) = marks_store.list_sessions()
    assert (item.pin, item.entries, item.slots, item.expired) == (pin, 2, 6, False)

    marks_store.delete_session(session.id)
    assert marks_store.list_sessions() == []
    assert marks_store.find_session(pin) is None
