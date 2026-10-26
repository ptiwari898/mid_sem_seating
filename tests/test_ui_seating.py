from __future__ import annotations

from streamlit.testing.v1 import AppTest

INFO = {"institute": "I", "department": "DEPARTMENT OF CSIT", "exam_title": "E", "semester": "6th Sem"}


def _add_room(app: AppTest, name: str) -> None:
    room_box = next(t for t in app.text_input if t.label == "Room Number")
    room_box.set_value(name)
    next(b for b in app.button if b.label == "Add").click().run()


def test_room_names_are_stripped_so_padded_duplicates_are_caught():
    app = AppTest.from_string(
        "from ui.tab_generate import render_tab_generate\n"
        f"render_tab_generate({INFO!r})",
        default_timeout=30,
    ).run()
    _add_room(app, "  F-307 ")
    assert [r["Room Number"] for r in app.session_state["rooms_with_info"]] == ["F-307"]

    _add_room(app, "F-307")
    assert [e.value for e in app.error] == ["Room F-307 already added."]

    _add_room(app, "   ")
    assert len(app.session_state["rooms_with_info"]) == 1


def test_generated_plan_is_remembered_for_the_admin_page(tmp_path, monkeypatch):
    import pandas as pd

    from exam_seating import marks_store
    from exam_seating.models import SeatingSummary
    from ui.tab_generate import _remember_plan

    monkeypatch.setattr(marks_store, "DB_PATH", tmp_path / "plans.db")
    rooms = {
        "F-307": pd.DataFrame({"Roll Number": ["001", "002", "003"]}),
        "F-308": pd.DataFrame({"Roll Number": []}),
    }
    _remember_plan(INFO, 40.0, SeatingSummary(5, 3, 2, 3, 0, 2, 40, 40), rooms, b"zipbytes", None)

    (plan,) = marks_store.list_plans()
    assert (plan.total, plan.eligible, plan.debarred, plan.allocated) == (5, 3, 2, 3)
    assert plan.rooms == [
        {"Room": "F-307", "Students": 3, "From": "001", "To": "003"},
        {"Room": "F-308", "Students": 0, "From": "", "To": ""},
    ]
    assert marks_store.get_plan_archive(plan.id) == b"zipbytes"


def test_rooms_and_subjects_are_listed_once_with_edit_and_delete_buttons():
    app = AppTest.from_string(
        "from ui.tab_generate import render_tab_generate\n"
        f"render_tab_generate({INFO!r})",
        default_timeout=30,
    ).run()
    _add_room(app, "F-307")

    subject_box = next(t for t in app.text_input if t.label == "Subject")
    subject_box.set_value("CSIT-301")
    adds = [b for b in app.button if b.label == "Add"]
    adds[-1].click().run()  # the timetable's Add button comes after the room form's

    assert not app.exception
    assert len(app.dataframe) == 0  # no read-only copy of the rows
    labels = [b.label for b in app.button]
    assert labels.count("Edit") == 2 and labels.count("Delete") == 2  # one pair per room and subject
    shown = [m.value for m in app.markdown]
    assert shown.count("F-307") == 1 and shown.count("CSIT-301") == 1  # each row appears once
