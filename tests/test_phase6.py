"""Map, analytics, duplicate detection and notification polish tests."""

import re

import pytest

from app import app
from database.db import query


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def login(client, email):
    token = re.search(r'name="csrf-token" content="([^"]+)"', client.get("/login").get_data(as_text=True)).group(1)
    assert client.post("/login", data={"csrf_token": token, "email": email, "password": "Demo@123"}).status_code == 302


def token_for(client, path):
    return re.search(r'name="csrf-token" content="([^"]+)"', client.get(path).get_data(as_text=True)).group(1)


def test_city_map_page_renders_public_complaints(client):
    response = client.get("/map")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "City Issue Map" in html
    assert "cityMap" in html
    assert "Garbage pile near bus stand" in html
    assert "mapCategory" in html


def test_analytics_page_renders_charts(client):
    response = client.get("/analytics")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "City Analytics" in html
    assert "analyticsCategory" in html
    assert "analyticsTrend" in html
    assert "window.civicfixAnalytics" in html


def test_duplicate_check_finds_similar_report(client):
    login(client, "priya@example.demo")
    response = client.post("/api/complaints/duplicate-check", json={
        "title": "Garbage pile near bus stand", "category_id": 2,
        "latitude": 13.085, "longitude": 80.275,
    }, headers={"X-CSRF-Token": token_for(client, "/report")})
    assert response.status_code == 200
    matches = response.get_json()["matches"]
    assert matches
    assert matches[0]["similarity"] > 0


def test_priority_service_explains_decision(client):
    from services.priority_service import suggest_priority

    result = suggest_priority({
        "title": "Huge pothole at busy junction",
        "description": "Deep pothole causing accidents and traffic congestion near a school.",
        "severity": "High",
        "location_importance": "junction",
        "safety_impact": "1",
    })
    assert result["priority"] in {"Low", "Medium", "High", "Urgent"}
    assert result["score"] >= 0
    assert "reason" in result and result["reason"]


def test_notifications_unread_filter(client):
    login(client, "suresh@staff.civicfix.demo")
    all_response = client.get("/notifications?filter=all")
    unread_response = client.get("/notifications?filter=unread")
    assert all_response.status_code == 200
    assert unread_response.status_code == 200
    assert "Unread" in unread_response.get_data(as_text=True)


def test_admin_dashboard_chart_assets_present(client):
    login(client, "admin@civicfix.demo")
    html = client.get("/admin/dashboard").get_data(as_text=True)
    assert "adminTrendChart" in html
    assert "js/admin.js" in html
