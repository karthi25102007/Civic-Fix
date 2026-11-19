"""Citizen workspace routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import DatabaseError, execute, query
from services import complaint_service
from services.notification_service import unread_count
from utils.decorators import current_user, login_required, role_required
from utils.validators import valid_email, valid_phone

citizen = Blueprint("citizen", __name__, url_prefix="/citizen")


@citizen.route("/dashboard")
@role_required("citizen")
def dashboard():
    user = current_user()
    stats = complaint_service.citizen_stats(user["id"])
    distribution = complaint_service.status_distribution(user["id"])
    categories = complaint_service.category_distribution(user["id"])
    return render_template(
        "citizen_dashboard.html",
        stats=stats,
        recent=complaint_service.recent_complaints(user["id"], limit=6),
        activity=complaint_service.citizen_activity(user["id"]),
        notifications=query(
            "SELECT id, title, message, type, is_read, created_at FROM notifications "
            "WHERE user_id = %s ORDER BY created_at DESC LIMIT 5",
            (user["id"],),
        ),
        status_labels=[row["label"] for row in distribution],
        status_values=[row["value"] for row in distribution],
        category_labels=[row["label"] for row in categories],
        category_values=[row["value"] for row in categories],
        unread=unread_count(user["id"]),
    )


@citizen.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=current_user())


@citizen.route("/profile/update", methods=["POST"])
@login_required
def profile_update():
    user = current_user()
    full_name = (request.form.get("full_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    phone = (request.form.get("phone") or "").strip()
    errors = []
    if len(full_name) < 2 or len(full_name) > 120:
        errors.append("Enter a valid full name.")
    if not valid_email(email):
        errors.append("Enter a valid email address.")
    if not valid_phone(phone):
        errors.append("Enter a valid phone number.")

    try:
        duplicate = query("SELECT id FROM users WHERE email = %s AND id <> %s", (email, user["id"]), one=True)
    except DatabaseError:
        duplicate = None
        errors.append("Profile update is temporarily unavailable.")
    if duplicate:
        errors.append("That email address is already in use.")

    new_password = request.form.get("new_password", "")
    if new_password:
        from utils.validators import password_errors

        errors.extend(password_errors(new_password))
        if new_password != request.form.get("confirm_password", ""):
            errors.append("New passwords do not match.")
        if not check_password_hash(
            query("SELECT password_hash FROM users WHERE id = %s", (user["id"]), one=True)["password_hash"],
            request.form.get("current_password", ""),
        ):
            errors.append("Current password is incorrect.")

    if errors:
        for error in errors:
            flash(error, "danger")
        return redirect(url_for("citizen.profile"))

    try:
        if new_password:
            execute(
                "UPDATE users SET full_name = %s, email = %s, phone = %s, password_hash = %s WHERE id = %s",
                (full_name, email, phone or None, generate_password_hash(new_password, method="pbkdf2:sha256:260000"), user["id"]),
            )
        else:
            execute(
                "UPDATE users SET full_name = %s, email = %s, phone = %s WHERE id = %s",
                (full_name, email, phone or None, user["id"]),
            )
        flash("Profile updated successfully.", "success")
    except DatabaseError:
        flash("Profile update failed. Please try again.", "danger")
    return redirect(url_for("citizen.profile"))
