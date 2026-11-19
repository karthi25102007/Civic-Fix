"""Dashboard, RBAC and profile tests."""

import re

import pytest

from app import app


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def login(client, email):
    token = re.search(
        r'name="csrf-token" content="([^"]+)"', client.get("/login").get_data(as_text=True)
    ).group(1)
    response = client.post(
        "/login",
        data={"csrf_token": token, "email": email, "password": "Demo@123"},
    )
    assert response.status_code == 302


def test_citizen_dashboard(client):
    login(client, "priya@example.demo")
    response = client.get("/citizen/dashboard")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Total submitted" in html
    assert "citizenStatusChart" in html


def test_admin_dashboard(client):
    login(client, "admin@civicfix.demo")
    response = client.get("/admin/dashboard")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Resolution rate" in html
    assert "adminTrendChart" in html


def test_staff_dashboard(client):
    login(client, "suresh@staff.civicfix.demo")
    response = client.get("/staff/dashboard")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Assigned tasks" in html
    assert "CFX-2026-00001" in html


def test_role_access_is_enforced(client):
    login(client, "priya@example.demo")
    assert client.get("/admin/dashboard").status_code == 403
    assert client.get("/staff/dashboard").status_code == 403


def test_private_dashboard_requires_login(client):
    response = client.get("/citizen/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_profile_update(client):
    login(client, "priya@example.demo")
    token = re.search(
        r'name="csrf-token" content="([^"]+)"', client.get("/citizen/profile").get_data(as_text=True)
    ).group(1)
    response = client.post(
        "/citizen/profile/update",
        data={"csrf_token": token, "full_name": "Priya Nair Test", "email": "priya@example.demo", "phone": "9876500002"},
    )
    assert response.status_code == 302
    from database.db import query

    row = query("SELECT full_name FROM users WHERE email = %s", ("priya@example.demo",), one=True)
    assert row["full_name"] == "Priya Nair Test"
    execute = __import__("database.db", fromlist=["execute"]).execute
    execute("UPDATE users SET full_name = %s WHERE email = %s", ("Priya Nair", "priya@example.demo"))


def test_unread_count_api(client):
    login(client, "rohan@example.demo")
    response = client.get("/api/notifications/unread-count")
    assert response.status_code == 200
    assert isinstance(response.get_json()["count"], int)
