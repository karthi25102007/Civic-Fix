"""Complaint submission, upload, tracking and support tests."""

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


def test_report_page_renders(client):
    login(client, "priya@example.demo")
    response = client.get("/report")
    assert response.status_code == 200
    assert "Report a Civic Issue" in response.get_data(as_text=True)
    assert "reportMap" in response.get_data(as_text=True)


def test_valid_submission_creates_complaint_with_history(client):
    login(client, "priya@example.demo")
    token = token_for(client, "/report")
    response = client.post("/report", data={
        "csrf_token": token,
        "title": "Broken traffic signal at test junction",
        "category_id": "1",
        "severity": "High",
        "description": "The traffic signal has been dark for several days and drivers are confused.",
        "additional_details": "Near the small shop",
        "location_address": "Test Junction, Chennai",
        "latitude": "13.0827000",
        "longitude": "80.2707000",
        "location_importance": "junction",
        "safety_impact": "1",
    })
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    tracking = re.search(r"CFX-\d{4}-\d{5}", html).group(0)
    row = query("SELECT * FROM complaints WHERE tracking_number = %s", (tracking,), one=True)
    assert row["status"] == "Submitted"
    assert row["priority"] in {"Low", "Medium", "High", "Urgent"}
    assert row["priority_reason"]
    assert row["additional_details"] == "Near the small shop"
    history = query("SELECT COUNT(*) AS c FROM complaint_updates WHERE complaint_id = %s", (row["id"],), one=True)
    assert history["c"] >= 1
    notice = query("SELECT COUNT(*) AS c FROM notifications WHERE complaint_id = %s", (row["id"],), one=True)
    assert notice["c"] >= 1
    execute("DELETE FROM complaints WHERE id = %s", (row["id"],))


def test_image_upload_is_validated_and_saved(client):
    login(client, "priya@example.demo")
    token = token_for(client, "/report")
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8AAAwAB/AF+HrW7AAAAAElFTkSuQmCC")
    response = client.post("/report", data={
        "csrf_token": token,
        "title": "Pothole with photo evidence",
        "category_id": "1",
        "severity": "Medium",
        "description": "A wide pothole has appeared after the recent rain and needs urgent repair.",
        "location_address": "Test Street, Chennai",
        "images": (io.BytesIO(png), "pothole.png", "image/png"),
    }, content_type="multipart/form-data")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    tracking = re.search(r"CFX-\d{4}-\d{5}", html).group(0)
    row = query("SELECT id FROM complaints WHERE tracking_number = %s", (tracking,), one=True)
    images = query("SELECT file_path FROM complaint_images WHERE complaint_id = %s", (row["id"],))
    assert len(images) == 1
    execute("DELETE FROM complaints WHERE id = %s", (row["id"],))


def test_invalid_upload_is_rejected(client):
    login(client, "priya@example.demo")
    token = token_for(client, "/report")
    response = client.post("/report", data={
        "csrf_token": token,
        "title": "Invalid upload attempt",
        "category_id": "1",
        "severity": "Low",
        "description": "This submission should fail because the uploaded file is not an image.",
        "location_address": "Test Street, Chennai",
        "images": (io.BytesIO(b"not an image"), "notes.txt", "text/plain"),
    }, content_type="multipart/form-data")
    assert response.status_code == 200
    assert "Unsupported file type" in response.get_data(as_text=True)


def test_duplicate_api_suggests_existing_complaint(client):
    login(client, "priya@example.demo")
    response = client.post("/api/complaints/duplicate-check", json={
        "title": "Garbage pile near bus stand", "category_id": 2,
        "latitude": 13.085, "longitude": 80.275
    }, headers={"X-CSRF-Token": token_for(client, "/report")})
    assert response.status_code == 200
    matches = response.get_json()["matches"]
    assert any(item["tracking_number"] == "CFX-2026-00002" for item in matches)


def test_public_tracking_hides_personal_information(client):
    response = client.post("/track", data={
        "csrf_token": token_for(client, "/track"), "tracking_number": "CFX-2026-00002"
    })
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Garbage pile near bus stand" in html
    assert "rohan@example.demo" not in html
    assert "Progress timeline" in html


def test_support_toggle_and_own_complaint_view(client):
    login(client, "priya@example.demo")
    complaint = query("SELECT id FROM complaints WHERE tracking_number = %s", ("CFX-2026-00005",), one=True)
    cid = complaint["id"]
    token = token_for(client, "/complaints/my")
    support_sql = "SELECT COUNT(*) AS c FROM complaint_supports WHERE complaint_id = %s"
    execute("DELETE FROM complaint_supports WHERE complaint_id = %s AND user_id = %s", (cid, 2))
    before = query(support_sql, (cid,), one=True)["c"]
    assert client.post(f"/complaints/{cid}/support", data={"csrf_token": token}).status_code == 302
    after = query(support_sql, (cid,), one=True)["c"]
    assert after == before + 1
    client.post(f"/complaints/{cid}/support", data={"csrf_token": token})
    restored = query(support_sql, (cid,), one=True)["c"]
    assert restored == before


def test_citizen_cannot_view_other_private_complaint(client):
    login(client, "rohan@example.demo")
    cid = query("SELECT id FROM complaints WHERE tracking_number = %s", ("CFX-2026-00001",), one=True)["id"]
    execute("UPDATE complaints SET is_public = 0 WHERE id = %s", (cid,))
    assert client.get(f"/complaints/{cid}").status_code == 403
    execute("UPDATE complaints SET is_public = 1 WHERE id = %s", (cid,))


def test_reopen_resolved_complaint(client):
    login(client, "priya@example.demo")
    row = query("SELECT id, status FROM complaints WHERE tracking_number = %s", ("CFX-2026-00001",), one=True)
    token = token_for(client, f"/complaints/{row['id']}")
    response = client.post(f"/complaints/{row['id']}/reopen", data={"csrf_token": token})
    assert response.status_code == 302
    assert query("SELECT status FROM complaints WHERE id = %s", (row["id"],), one=True)["status"] == "Reopened"
    execute("UPDATE complaints SET status = %s WHERE id = %s", (row["status"], row["id"]))
