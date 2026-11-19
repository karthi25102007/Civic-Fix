"""End-to-end lifecycle: citizen report -> admin assignment -> staff resolution."""

import re

import pytest

from app import app
from database.db import execute, query


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def token_from(html):
    return re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)


def login(client, email):
    token = token_from(client.get("/login").get_data(as_text=True))
    assert client.post("/login", data={"csrf_token": token, "email": email, "password": "Demo@123"}).status_code == 302


def logout(client):
    token = token_from(client.get("/").get_data(as_text=True))
    assert client.post("/logout", data={"csrf_token": token}).status_code == 302


def token_for(client, path):
    return token_from(client.get(path).get_data(as_text=True))


def test_full_complaint_lifecycle(client):
    login(client, "priya@example.demo")
    token = token_for(client, "/report")
    response = client.post("/report", data={
        "csrf_token": token,
        "title": "End-to-end test pothole",
        "category_id": "1",
        "severity": "High",
        "description": "A deep pothole is causing traffic problems and may damage vehicles.",
        "location_address": "Lifecycle Test Street, Chennai",
        "latitude": "13.0827000",
        "longitude": "80.2707000",
        "location_importance": "junction",
        "safety_impact": "1",
    })
    assert response.status_code == 200
    tracking = re.search(r"CFX-\d{4}-\d{5}", response.get_data(as_text=True)).group(0)
    row = query("SELECT id, status FROM complaints WHERE tracking_number = %s", (tracking,), one=True)
    complaint_id = row["id"]
    assert row["status"] == "Submitted"

    try:
        logout(client)
        login(client, "admin@civicfix.demo")
        staff = query(
            "SELECT id, department_id FROM users WHERE email = %s AND role = 'staff' AND is_active = 1",
            ("suresh@staff.civicfix.demo",), one=True,
        )
        assert staff and staff["department_id"]
        department = query("SELECT id FROM departments WHERE id = %s AND is_active = 1", (staff["department_id"],), one=True)
        assert department
        token = token_for(client, f"/admin/complaints/{complaint_id}")
        response = client.post(f"/admin/complaints/{complaint_id}/assign", data={
            "csrf_token": token,
            "department_id": str(department["id"]),
            "staff_id": str(staff["id"]),
            "note": "Lifecycle test assignment",
        })
        assert response.status_code == 302
        assert query("SELECT status FROM complaints WHERE id = %s", (complaint_id,), one=True)["status"] == "Assigned"

        logout(client)
        login(client, "suresh@staff.civicfix.demo")
        token = token_for(client, f"/staff/tasks/{complaint_id}")
        response = client.post(f"/staff/tasks/{complaint_id}/progress", data={
            "csrf_token": token, "body": "Repair crew has been scheduled for this location."
        })
        assert response.status_code == 302
        token = token_for(client, f"/staff/tasks/{complaint_id}")
        response = client.post(f"/staff/tasks/{complaint_id}/resolve", data={
            "csrf_token": token, "note": "Pothole filled and road surface verified after repair."
        })
        assert response.status_code == 302
        assert query("SELECT status FROM complaints WHERE id = %s", (complaint_id,), one=True)["status"] == "Resolved"

        logout(client)
        login(client, "priya@example.demo")
        html = client.get(f"/complaints/{complaint_id}").get_data(as_text=True)
        assert "Resolved" in html
        assert "Repair crew has been scheduled" in html
        assert "Pothole filled and road surface verified" in html
    finally:
        execute("DELETE FROM complaints WHERE id = %s", (complaint_id,))
