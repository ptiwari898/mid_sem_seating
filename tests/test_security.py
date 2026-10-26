from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.index import MAX_UPLOAD_BYTES, app


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
