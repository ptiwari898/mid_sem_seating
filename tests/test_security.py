from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.index import MAX_UPLOAD_BYTES, app
from ui import tab_data_management as tdm


@pytest.fixture
def pin_env(monkeypatch):
    state = {"pin_attempts": 0, "pin_time": 0, "marks_authenticated": False}
    fake_st = SimpleNamespace(
        session_state=state,
        secrets={"MARKS_PIN": "4321"},
        error=lambda *a, **k: None,
    )
    monkeypatch.setattr(tdm, "st", fake_st)
    return state


def test_wrong_pin_locks_after_three_tries_even_for_correct_pin(pin_env, monkeypatch):
    monkeypatch.setattr(tdm.time, "time", lambda: 1000.0)
    for _ in range(3):
        assert tdm._validate_pin("0000") is False
    assert tdm._validate_pin("4321") is False
    assert pin_env["marks_authenticated"] is False


def test_pin_works_again_after_lockout_expires(pin_env, monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(tdm.time, "time", lambda: now["t"])
    for _ in range(3):
        tdm._validate_pin("0000")
    now["t"] += tdm.LOCKOUT_SECONDS + 1
    assert tdm._validate_pin("4321") is True
    assert pin_env["marks_authenticated"] is True


def test_api_returns_400_for_missing_columns():
    response = TestClient(app).post(
        "/api/generate-seating",
        files={
            "students_file": ("s.csv", "a,b\n1,2"),
            "rooms_file": ("r.csv", "Room Number,Capacity\nR1,5"),
        },
    )
    assert response.status_code == 400
    assert "Roll Number" in response.json()["detail"]


def test_api_returns_413_for_oversized_upload():
    response = TestClient(app).post(
        "/api/generate-seating",
        files={
            "students_file": ("s.csv", b"x" * (MAX_UPLOAD_BYTES + 1)),
            "rooms_file": ("r.csv", "x"),
        },
    )
    assert response.status_code == 413


@pytest.mark.parametrize("cutoff", ["150", "-1"])
def test_api_returns_400_for_cutoff_outside_0_to_100(cutoff):
    response = TestClient(app).post(
        "/api/generate-seating",
        files={
            "students_file": ("s.csv", "Roll Number,Name,Attendance Percentage\n1,A,90"),
            "rooms_file": ("r.csv", "Room Number,Capacity\nR1,5"),
        },
        data={"attendance_cutoff": cutoff},
    )
    assert response.status_code == 400
    assert "attendance_cutoff" in response.json()["detail"]


def test_unsafe_download_route_is_gone():
    assert TestClient(app).get("/api/download/a.txt", params={"content_base64": "aGk="}).status_code == 404
