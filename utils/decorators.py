"""Security decorators and session helpers."""

import secrets
from functools import wraps

from flask import (
    abort,
    flash,
    g,
    jsonify,
    redirect,
    request,
    session,
    url_for,
)

from database.db import query


def generate_csrf_token() -> str:
    if not session.get("_csrf_token"):
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return session["_csrf_token"]


def csrf_validate() -> None:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    if not token and request.is_json:
        token = (request.get_json(silent=True) or {}).get("csrf_token")
    expected = session.get("_csrf_token")
    if not expected or not token or not secrets.compare_digest(str(expected), str(token)):
        if request.path.startswith("/api/"):
            abort(403, description="Invalid CSRF token")
        abort(403, description="Invalid CSRF token")


def current_user():
    """Return the logged-in user's database row, or None."""
    if not hasattr(g, "civicfix_user"):
        user_id = session.get("user_id")
        g.civicfix_user = (
            query(
                "SELECT id, full_name, email, phone, role, department_id, is_active, "
                "last_login_at, created_at FROM users WHERE id = %s",
                (user_id,),
                one=True,
            )
            if user_id
            else None
        )
    return g.civicfix_user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or not user["is_active"]:
            session.clear()
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required"}), 401
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            user = current_user()
            if user["role"] not in roles:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "You do not have permission for this action"}), 403
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def dashboard_url(role: str) -> str:
    return {
        "admin": url_for("admin.dashboard"),
        "staff": url_for("staff.dashboard"),
        "citizen": url_for("citizen.dashboard"),
    }.get(role, url_for("main.index"))
