"""Administrator complaint and management workflow tests."""

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


def complaint_by_tracking(tracking):
    return query("SELECT id, status FROM complaints WHERE tracking_number = %s", (tracking,), one=True)


def test_admin_pages_render(client):
    login(client, "admin@civicfix.demo")
    for path, expected in [
        ("/admin/complaints", "All Complaints"),
        ("/admin/departments", "Departments"),
        ("/admin/staff", "Staff Management"),
        ("/admin/citizens", "Citizens"),
        ("/admin/audit", "Audit Logs"),
        ("/admin/settings", "Settings"),
    ]:
        response = client.get(path)
        assert response.status_code == 200, path
        assert expected in response.get_data(as_text=True), path


def test_admin_complaint_detail_and_filters(client):
    login(client, "admin@civicfix.demo")
    row = complaint_by_tracking("CFX-2026-00001")
    response = client.get(f"/admin/complaints/{row['id']}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Report details" in html
    assert "Update status" in html
    assert "Override priority" in html
    filtered = client.get("/admin/complaints?status=Submitted")
    assert filtered.status_code == 200
    assert "1 complaint" not in filtered.get_data(as_text=True) or "complaints found" in filtered.get_data(as_text=True)


def test_non_admin_cannot_manage_complaints(client):
    login(client, "priya@example.demo")
    assert client.get("/admin/complaints").status_code == 403
    assert client.get("/admin/departments").status_code == 403
    assert client.get("/admin/staff").status_code == 403


def test_admin_status_change_is_audited(client):
    login(client, "admin@civicfix.demo")
    row = complaint_by_tracking("CFX-2026-00006")
    original = row["status"]
    new_status = "Under Review" if original != "Under Review" else "Verified"
    token = token_for(client, f"/admin/complaints/{row['id']}")
    response = client.post(f"/admin/complaints/{row['id']}/status", data={
        "csrf_token": token, "status": new_status, "note": "Administrative review test"
    })
    assert response.status_code == 302
    assert complaint_by_tracking("CFX-2026-00006")["status"] == new_status
    audit = query(
        "SELECT id FROM audit_logs WHERE entity_type = 'complaint' AND entity_id = %s "
        "AND action = 'change_status' ORDER BY id DESC LIMIT 1", (row["id"],), one=True
    )
    assert audit
    execute("UPDATE complaints SET status = %s WHERE id = %s", (original, row["id"]))


def test_admin_priority_override(client):
    login(client, "admin@civicfix.demo")
    row = query("SELECT id, priority FROM complaints WHERE tracking_number = %s", ("CFX-2026-00006",), one=True)
    new_priority = "Urgent" if row["priority"] != "Urgent" else "Low"
    token = token_for(client, f"/admin/complaints/{row['id']}")
    response = client.post(f"/admin/complaints/{row['id']}/priority", data={
        "csrf_token": token, "priority": new_priority, "note": "Escalated after review"
    })
    assert response.status_code == 302
    assert query("SELECT priority FROM complaints WHERE id = %s", (row["id"],), one=True)["priority"] == new_priority
    execute("UPDATE complaints SET priority = %s WHERE id = %s", (row["priority"], row["id"]))


def test_admin_assignment_updates_current_department(client):
    login(client, "admin@civicfix.demo")
    row = complaint_by_tracking("CFX-2026-00006")
    original_status = row["status"]
    original = query(
        "SELECT id FROM complaint_assignments WHERE complaint_id = %s AND is_current = 1",
        (row["id"],), one=True
    )
    department = query("SELECT id FROM departments WHERE is_active = 1 ORDER BY id LIMIT 1", one=True)
    staff = query("SELECT id FROM users WHERE role = 'staff' AND department_id = %s LIMIT 1", (department["id"],), one=True)
    token = token_for(client, f"/admin/complaints/{row['id']}")
    response = client.post(f"/admin/complaints/{row['id']}/assign", data={
        "csrf_token": token,
        "department_id": str(department["id"]),
        "staff_id": str(staff["id"]) if staff else "",
        "note": "Assignment test",
    })
    assert response.status_code == 302
    current = query(
        "SELECT department_id, staff_id FROM complaint_assignments WHERE complaint_id = %s AND is_current = 1",
        (row["id"],), one=True
    )
    assert current["department_id"] == department["id"]
    execute("UPDATE complaint_assignments SET is_current = 0 WHERE complaint_id = %s AND is_current = 1", (row["id"],))
    if original:
        execute("UPDATE complaint_assignments SET is_current = 1 WHERE id = %s", (original["id"],))
    execute("UPDATE complaints SET status = %s WHERE id = %s", (original_status, row["id"]))


def test_department_create_and_update(client):
    login(client, "admin@civicfix.demo")
    token = token_for(client, "/admin/departments")
    assert client.post("/admin/departments", data={
        "csrf_token": token, "name": "Test Department", "code": "TESTDPT", "description": "Temporary test department"
    }).status_code == 302
    department = query("SELECT id FROM departments WHERE code = %s", ("TESTDPT",), one=True)
    assert department
    token = token_for(client, "/admin/departments")
    response = client.post(f"/admin/departments/{department['id']}", data={
        "csrf_token": token, "name": "Test Department Updated", "code": "TESTDPT", "description": "Updated", "is_active": "1"
    })
    assert response.status_code == 302
    assert query("SELECT name FROM departments WHERE id = %s", (department["id"],), one=True)["name"] == "Test Department Updated"
    execute("DELETE FROM departments WHERE id = %s", (department["id"],))


def test_staff_account_creation(client):
    login(client, "admin@civicfix.demo")
    department = query("SELECT id FROM departments WHERE is_active = 1 ORDER BY id LIMIT 1", one=True)
    token = token_for(client, "/admin/staff")
    response = client.post("/admin/staff", data={
        "csrf_token": token,
        "full_name": "Test Staff Member",
        "email": "test.staff@civicfix.demo",
        "phone": "9876500099",
        "department_id": str(department["id"]),
        "password": "TestPass123",
    })
    assert response.status_code == 302
    created = query("SELECT id FROM users WHERE email = %s", ("test.staff@civicfix.demo",), one=True)
    assert created
    execute("DELETE FROM users WHERE id = %s", (created["id"],))


def test_citizen_status_toggle(client):
    login(client, "admin@civicfix.demo")
    citizen = query("SELECT id, is_active FROM users WHERE email = %s", ("rohan@example.demo",), one=True)
    token = token_for(client, "/admin/citizens")
    response = client.post(f"/admin/citizens/{citizen['id']}/toggle", data={"csrf_token": token})
    assert response.status_code == 302
    assert query("SELECT is_active FROM users WHERE id = %s", (citizen["id"],), one=True)["is_active"] != citizen["is_active"]
    execute("UPDATE users SET is_active = %s WHERE id = %s", (citizen["is_active"], citizen["id"]))
