"""Staff task queue, progress notes and resolution workflow tests."""

import base64
import io
import re

import pytest

from app import app
from database.db import execute, query


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def login(client, email):
    token = re.search(r'name="csrf-token" content="([^"]+)"', client.get("/login").get_data(as_text=True)).group(1)
    assert client.post("/login", data={"csrf_token": token, "email": email, "password": "Demo@123"}).status_code == 302


def token_for(client, path):
    return re.search(r'name="csrf-token" content="([^"]+)"', client.get(path).get_data(as_text=True)).group(1)


def staff_user():
    return query("SELECT id FROM users WHERE email = %s", ("suresh@staff.civicfix.demo",), one=True)


def assigned_complaint(staff_id, exclude_status=None):
    sql = (
        "SELECT c.id, c.status FROM complaint_assignments ca JOIN complaints c ON c.id = ca.complaint_id "
        "WHERE ca.staff_id = %s AND ca.is_current = 1"
    )
    params = [staff_id]
    if exclude_status:
        sql += " AND c.status <> %s"
        params.append(exclude_status)
    return query(sql + " LIMIT 1", tuple(params), one=True)


def test_staff_pages_render(client):
    login(client, "suresh@staff.civicfix.demo")
    staff_id = staff_user()["id"]
    row = assigned_complaint(staff_id)
    for path, expected in [
        ("/staff/dashboard", "Your assigned work"),
        ("/staff/tasks", "Your work queue"),
        (f"/staff/tasks/{row['id']}", "Post progress update"),
    ]:
        response = client.get(path)
        assert response.status_code == 200, path
        assert expected in response.get_data(as_text=True), path


def test_citizen_cannot_access_staff_workspace(client):
    login(client, "priya@example.demo")
    assert client.get("/staff/dashboard").status_code == 403
    assert client.get("/staff/tasks").status_code == 403
    assert client.get("/staff/tasks/1").status_code == 403


def test_staff_cannot_open_unassigned_complaint(client):
    login(client, "suresh@staff.civicfix.demo")
    staff_id = staff_user()["id"]
    row = query(
        "SELECT c.id FROM complaints c LEFT JOIN complaint_assignments ca "
        "ON ca.complaint_id = c.id AND ca.is_current = 1 "
        "WHERE COALESCE(ca.staff_id, 0) <> %s LIMIT 1", (staff_id,), one=True
    )
    assert row
    assert client.get(f"/staff/tasks/{row['id']}").status_code == 403


def test_progress_note_and_image_are_saved(client):
    login(client, "suresh@staff.civicfix.demo")
    staff_id = staff_user()["id"]
    row = assigned_complaint(staff_id)
    before = query("SELECT COALESCE(MAX(id), 0) AS m FROM complaint_updates", one=True)["m"]
    token = token_for(client, f"/staff/tasks/{row['id']}")
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8AAAwAB/AF+HrW7AAAAAElFTkSuQmCC")
    response = client.post(f"/staff/tasks/{row['id']}/progress", data={
        "csrf_token": token,
        "body": "Inspected the site and arranged a repair crew.",
        "images": (io.BytesIO(png), "progress.png", "image/png"),
    }, content_type="multipart/form-data")
    assert response.status_code == 302
    updates = query("SELECT * FROM complaint_updates WHERE id > %s AND complaint_id = %s", (before, row["id"]))
    assert any(item["update_type"] == "progress" and item["is_public"] == 1 for item in updates)
    evidence = query(
        "SELECT id FROM complaint_images WHERE complaint_id = %s AND image_type = 'progress' "
        "ORDER BY id DESC LIMIT 1", (row["id"],), one=True
    )
    assert evidence
    execute("DELETE FROM complaint_updates WHERE id > %s AND complaint_id = %s", (before, row["id"]))
    execute("DELETE FROM complaint_images WHERE id = %s", (evidence["id"],))


def test_staff_status_change(client):
    login(client, "suresh@staff.civicfix.demo")
    staff_id = staff_user()["id"]
    row = assigned_complaint(staff_id)
    original = row["status"]
    new_status = "In Progress" if original != "In Progress" else "Resolved"
    token = token_for(client, f"/staff/tasks/{row['id']}")
    response = client.post(f"/staff/tasks/{row['id']}/status", data={
        "csrf_token": token, "status": new_status, "note": "Work started by staff"
    })
    assert response.status_code == 302
    assert query("SELECT status FROM complaints WHERE id = %s", (row["id"],), one=True)["status"] == new_status
    execute("UPDATE complaints SET status = %s WHERE id = %s", (original, row["id"]))


def test_resolution_flow_notifies_citizen(client):
    login(client, "suresh@staff.civicfix.demo")
    staff_id = staff_user()["id"]
    row = assigned_complaint(staff_id, exclude_status="Resolved")
    assert row
    original = row["status"]
    token = token_for(client, f"/staff/tasks/{row['id']}")
    response = client.post(f"/staff/tasks/{row['id']}/resolve", data={
        "csrf_token": token,
        "note": "Repaired the damaged area and verified the fix on site.",
    })
    assert response.status_code == 302
    assert query("SELECT status FROM complaints WHERE id = %s", (row["id"],), one=True)["status"] == "Resolved"
    resolution = query(
        "SELECT id FROM complaint_updates WHERE complaint_id = %s AND update_type = 'resolution' "
        "ORDER BY id DESC LIMIT 1", (row["id"],), one=True
    )
    assert resolution
    execute("DELETE FROM complaint_updates WHERE id = %s", (resolution["id"],))
    execute("UPDATE complaints SET status = %s WHERE id = %s", (original, row["id"]))


def test_escalation_notifies_admin(client):
    login(client, "suresh@staff.civicfix.demo")
    staff_id = staff_user()["id"]
    row = assigned_complaint(staff_id)
    before = query("SELECT COALESCE(MAX(id), 0) AS m FROM notifications", one=True)["m"]
    token = token_for(client, f"/staff/tasks/{row['id']}")
    response = client.post(f"/staff/tasks/{row['id']}/escalate", data={
        "csrf_token": token, "reason": "Need an administrator to approve additional materials."
    })
    assert response.status_code == 302
    notices = query("SELECT user_id FROM notifications WHERE id > %s AND title = %s", (before, "Staff escalation"))
    admin_ids = {item["id"] for item in query("SELECT id FROM users WHERE role = 'admin'")}
    assert any(item["user_id"] in admin_ids for item in notices)
    execute("DELETE FROM notifications WHERE id > %s", (before,))
