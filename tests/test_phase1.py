"""Smoke tests for public pages and authentication."""

import re

import pytest

from app import app


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def csrf_token(response):
    match = re.search(r'name="csrf-token" content="([^"]+)"', response.get_data(as_text=True))
    assert match, "CSRF meta tag missing"
    return match.group(1)


@pytest.mark.parametrize(
    "path", ["/", "/login", "/register", "/about", "/contact", "/privacy", "/terms", "/health", "/forgot-password"]
)
def test_public_pages_render(client, path):
    assert client.get(path).status_code == 200


def test_landing_statistics_come_from_database(client):
    html = client.get("/").get_data(as_text=True)
    assert "Total complaints" in html
    assert "Resolved complaints" in html
    assert re.search(r"CFX-\d{4}-\d{5}", html)


def test_csrf_is_required(client):
    response = client.post(
        "/login", data={"email": "admin@civicfix.demo", "password": "Demo@123"}
    )
    assert response.status_code == 403


def test_login_sets_role_session(client):
    token = csrf_token(client.get("/login"))
    response = client.post(
        "/login",
        data={"csrf_token": token, "email": "admin@civicfix.demo", "password": "Demo@123"},
    )
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert session["role"] == "admin"
        assert session["email"] == "admin@civicfix.demo"


def test_bad_password_is_rejected(client):
    token = csrf_token(client.get("/login"))
    response = client.post(
        "/login",
        data={"csrf_token": token, "email": "admin@civicfix.demo", "password": "wrong-password"},
    )
    assert response.status_code == 200
    with client.session_transaction() as session:
        assert "user_id" not in session


def test_duplicate_registration_is_rejected(client):
    token = csrf_token(client.get("/register"))
    response = client.post(
        "/register",
        data={
            "csrf_token": token,
            "full_name": "Duplicate User",
            "email": "admin@civicfix.demo",
            "password": "Testpass123",
            "confirm_password": "Testpass123",
        },
    )
    assert response.status_code == 200
    assert "already exists" in response.get_data(as_text=True)


def test_password_hashes_are_not_plaintext():
    from database.db import query

    row = query("SELECT password_hash FROM users WHERE email = %s", ("admin@civicfix.demo",), one=True)
    assert row["password_hash"] != "Demo@123"
    assert row["password_hash"].startswith("pbkdf2:")
