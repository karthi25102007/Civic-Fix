"""Server-side validation helpers."""

import re
from datetime import datetime

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^[0-9+()\-\s]{7,20}$")
TRACKING_RE = re.compile(r"^CFX-\d{4}-\d{5}$")

STATUSES = [
    "Submitted",
    "Under Review",
    "Verified",
    "Assigned",
    "In Progress",
    "Resolved",
    "Reopened",
    "Rejected",
]
PRIORITIES = ["Low", "Medium", "High", "Urgent"]


def valid_email(value: str) -> bool:
    return bool(value and EMAIL_RE.fullmatch(value.strip()))


def valid_phone(value: str) -> bool:
    return not value or bool(PHONE_RE.fullmatch(value.strip()))


def password_errors(password: str) -> list:
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if not re.search(r"[A-Za-z]", password):
        errors.append("Password must contain a letter.")
    if not re.search(r"\d", password):
        errors.append("Password must contain a number.")
    return errors


def validate_registration(data: dict) -> list:
    errors = []
    name = (data.get("full_name") or "").strip()
    if len(name) < 2 or len(name) > 120:
        errors.append("Full name must be between 2 and 120 characters.")
    if not valid_email(data.get("email", "")):
        errors.append("Enter a valid email address.")
    if not valid_phone(data.get("phone", "")):
        errors.append("Enter a valid phone number or leave it blank.")
    errors.extend(password_errors(data.get("password", "")))
    if data.get("password") != data.get("confirm_password"):
        errors.append("Passwords do not match.")
    return errors


def validate_login(data: dict) -> list:
    errors = []
    if not valid_email(data.get("email", "")):
        errors.append("Enter a valid email address.")
    if not data.get("password"):
        errors.append("Enter your password.")
    return errors


def safe_next_url(value: str | None, fallback: str) -> str:
    if value and value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    return fallback


def parse_date(value: str | None, field: str, errors: list):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        errors.append(f"Invalid {field} date.")
        return None


def clean_text(value, max_length: int = 5000) -> str:
    return (value or "").strip()[:max_length]
