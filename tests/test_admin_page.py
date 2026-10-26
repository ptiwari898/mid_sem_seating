from __future__ import annotations

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from exam_seating import marks_store

PAGE = "import streamlit_app\nstreamlit_app.admin_page()"


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(marks_store, "DB_PATH", tmp_path / "admin.db")


@pytest.fixture
def data():
    students = pd.DataFrame({"Roll Number": ["1", "2"], "Name": ["A", "B"]})
    pin, session = marks_store.create_session("Mid Sem", ["Maths", "Physics"], students)
    maths = marks_store.list_subjects(session.id)[0]
    blank = marks_store.get_marks_table(session.id, maths.id)
    edited = blank.copy()
    edited.loc[0, "Marks"] = 21.0
    marks_store.save_marks(session, maths.id, edited, "Prof A", original=blank)
    plan_id = marks_store.save_plan(
        exam_title="Mid Sem", department="CSIT", semester="6th Sem", cutoff=40.0, total=2,
        eligible=2, debarred=0, allocated=2,
        rooms=[{"Room": "F-307", "Students": 2, "From": "1", "To": "2"}],
        archive=b"zip", session_id=session.id,
    )
    return pin, session, plan_id


def _admin(password: str | None = "pw") -> AppTest:
    app = AppTest.from_string(PAGE, default_timeout=30)
    if password is not None:
        app.secrets["ADMIN_PASSWORD"] = password
    return app.run()


def _unlock(app: AppTest, typed: str = "pw") -> AppTest:
    app.text_input[0].set_value(typed)
    next(b for b in app.button if b.label == "Unlock").click().run()
    return app


def test_page_is_disabled_without_an_admin_password(data):
    app = _admin(password=None)
    assert not app.exception
    assert "ADMIN_PASSWORD" in app.info[0].value
    assert not app.tabs


def test_wrong_password_shows_nothing(data):
    app = _unlock(_admin(), "nope")
    assert [e.value for e in app.error] == ["Wrong password."]
    assert not app.tabs


def test_admin_sees_the_plan_and_the_marks_entries(data):
    pin, session, plan_id = data
    app = _unlock(_admin())
    assert not app.exception
    assert [t.label for t in app.tabs] == ["Seating plans", "Marks entries", "Backup"]

    labels = [e.label for e in app.expander]
    assert any(label.startswith(f"#{plan_id} · Mid Sem") for label in labels)
    assert any(label.startswith(f"#{session.id} · Mid Sem") and label.endswith("open") for label in labels)
    text = " ".join(m.value for m in app.markdown) + " ".join(c.value for c in app.caption)
    assert f"PIN: **{pin}**" in text and f"PIN {pin}" in text  # shown in both places
    assert {d.label for d in app.get("download_button")} >= {
        "Download all reports (.zip)", "Download marks (CSV)", "Edit history (CSV)", "Download full backup",
    }


def test_admin_can_lock_a_marks_entry(data):
    _, session, _ = data
    app = _unlock(_admin())
    next(b for b in app.button if b.label == "Lock (finalise)").click().run()
    assert marks_store.is_locked(session.id)


def test_deleting_needs_the_confirmation_box_first(data):
    _, session, plan_id = data
    app = _unlock(_admin())
    delete = next(b for b in app.button if b.key == f"plan_del_{plan_id}")
    assert delete.disabled

    next(c for c in app.checkbox if c.key == f"plan_del_{plan_id}_sure").check().run()
    next(b for b in app.button if b.key == f"plan_del_{plan_id}").click().run()
    assert marks_store.list_plans() == []
    assert marks_store.list_sessions()  # the marks session is untouched
