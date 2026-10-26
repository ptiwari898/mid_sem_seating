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
