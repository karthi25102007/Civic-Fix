"""In-app notification routes."""

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from database.db import query
from services.notification_service import mark_all_read, mark_read, unread_count
from utils.decorators import current_user, login_required

notifications = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications.route("")
@notifications.route("/")
@login_required
def listing():
    user = current_user()
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 20
    offset = (page - 1) * per_page
    filter_mode = "unread" if request.args.get("filter") == "unread" else "all"
    where = "user_id = %s" + (" AND is_read = 0" if filter_mode == "unread" else "")
    rows = query(
        "SELECT id, complaint_id, title, message, type, is_read, created_at, read_at "
        "FROM notifications WHERE " + where + " ORDER BY created_at DESC LIMIT %s OFFSET %s",
        (user["id"], per_page, offset),
    )
    total = unread_count(user["id"])
    count_row = query("SELECT COUNT(*) AS count FROM notifications WHERE " + where, (user["id"],), one=True)
    total_all = (count_row or {}).get("count") or 0
    for row in rows:
        if not row["complaint_id"]:
            row["link"] = "#"
        elif user["role"] == "admin":
            row["link"] = f"/admin/complaints/{row['complaint_id']}"
        elif user["role"] == "staff":
            assigned = query(
                "SELECT id FROM complaint_assignments WHERE complaint_id = %s AND staff_id = %s AND is_current = 1",
                (row["complaint_id"], user["id"]), one=True,
            )
            row["link"] = f"/staff/tasks/{row['complaint_id']}" if assigned else f"/complaints/{row['complaint_id']}"
        else:
            row["link"] = f"/complaints/{row['complaint_id']}"
    return render_template(
        "notifications.html",
        notifications=rows,
        page=page,
        pages=max(1, (total_all + per_page - 1) // per_page),
        unread=total,
        filter_mode=filter_mode,
    )


@notifications.route("/<int:notification_id>/read", methods=["POST"])
@login_required
def read_one(notification_id):
    mark_read(notification_id, current_user()["id"])
    return redirect(request.referrer or url_for("notifications.listing"))


@notifications.route("/read-all", methods=["POST"])
@login_required
def read_all():
    count = mark_all_read(current_user()["id"])
    if count:
        from flask import flash

        flash(f"Marked {count} notification(s) as read.", "success")
    return redirect(url_for("notifications.listing"))


