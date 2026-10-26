from __future__ import annotations

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from exam_seating import marks_store


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(marks_store, "DB_PATH", tmp_path / "marks.db")


def _make_session():
    students = pd.DataFrame(
        {"Roll Number": ["1", "2"], "Name": ["A", "B"], "Section": ["A", "B"], "Branch": ["CSIT", "CSIT"]}
    )
    return marks_store.create_session("Mid Sem", ["Maths", "Physics"], students)


TEACHER_PAGE = (
    "from ui.marks_entry import render_teacher_marks_entry\nrender_teacher_marks_entry()"
)


def _open_as_teacher(pin: str) -> AppTest:
    app = AppTest.from_string(TEACHER_PAGE, default_timeout=30).run()
    app.text_input[0].set_value(pin)
    app.button[0].click().run()
    return app


def test_pin_banner_shown_twice_in_one_run_does_not_crash():
    # Regression: the banner is drawn before and after generating a plan.
    page = (
        "import pandas as pd, streamlit as st\n"
        "from ui.marks_entry import open_marks_session, show_active_pin\n"
        "slot = st.empty()\n"
        "show_active_pin(slot)\n"
        "if st.button('go'):\n"
        "    open_marks_session('Mid', ['Maths'], pd.DataFrame({'Roll Number': ['1'], 'Name': ['A']}), 30.0, slot)\n"
    )
    app = AppTest.from_string(page, default_timeout=30).run()
    for _ in range(2):  # the second click has an older PIN already on screen
        app.button[0].click().run()
        assert not app.exception
        assert len(app.info) == 1 and len(app.get("download_button")) == 1


def test_wrong_pin_is_refused_and_right_pin_lists_all_subjects():
    pin, _ = _make_session()
    wrong = AppTest.from_string(TEACHER_PAGE, default_timeout=30).run()
    wrong.text_input[0].set_value("000000" if pin != "000000" else "111111")
    wrong.button[0].click().run()
    assert [e.value for e in wrong.error] == ["Invalid or expired PIN."]

    app = _open_as_teacher(pin)
    assert app.selectbox[0].options == ["Maths", "Physics"]


def test_section_filter_limits_the_rows_a_teacher_sees():
    pin, _ = _make_session()
    app = _open_as_teacher(pin)
    assert app.selectbox[1].options == ["All", "A", "B"]
    assert any("of 2 students" in c.value for c in app.caption)

    app.selectbox[1].select("B").run()
    assert not app.exception
    assert any("of 1 students" in c.value for c in app.caption)


def test_saving_without_a_teacher_name_is_refused():
    pin, _ = _make_session()
    app = _open_as_teacher(pin)
    next(b for b in app.button if b.label.endswith("Save Marks")).click().run()
    assert [e.value for e in app.error] == ["Enter your name before saving."]


def test_marks_entry_is_its_own_page_and_not_a_tab_of_the_coordinator_page():
    pin, _ = _make_session()
    page = AppTest.from_string(
        "import streamlit_app\nstreamlit_app.marks_entry_page()", default_timeout=30
    ).run()
    assert [h.value for h in page.header] == ["Marks Entry"]
    page.text_input[0].set_value(pin)
    page.button[0].click().run()
    assert not page.exception
    assert page.selectbox[0].options == ["Maths", "Physics"]

    home = AppTest.from_file("streamlit_app.py", default_timeout=60).run()
    assert not home.exception
    assert [t.label for t in home.tabs] == ["Seating Plan", "Result Analysis", "Data & Coordinator"]
    assert not any(t.label == "Session PIN" for t in home.text_input)  # PIN box lives on its page
