"""Department staff workspace: assigned complaints and field updates."""

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from database.db import execute, query
from services import complaint_service
from services.notification_service import notify, notify_status, unread_count
from utils.decorators import current_user, role_required
from utils.upload_utils import UploadError, save_images

staff = Blueprint("staff", __name__, url_prefix="/staff")

ALLOWED_STAFF_STATUSES = ("In Progress", "Resolved")
PRIORITIES = ("Low", "Medium", "High", "Urgent")
STATUSES = (
    "Submitted", "Under Review", "Verified", "Assigned",
    "In Progress", "Resolved", "Reopened", "Rejected",
)


def _audit(action, complaint_id, details):
    complaint_service.log_audit(
        current_user()["id"], action, "complaint", complaint_id, details, request.remote_addr
    )


def _staff_complaint(complaint_id, staff_id):
    complaint = complaint_service.get_complaint(complaint_id)
    if not complaint:
        abort(404)
    assignment = query(
        "SELECT id FROM complaint_assignments WHERE complaint_id = %s AND staff_id = %s AND is_current = 1",
        (complaint_id, staff_id), one=True,
    )
    if not assignment:
        abort(403)
    return complaint


def _task_filters(args, staff_id):
    where = ["ca.staff_id = %s", "ca.is_current = 1"]
    params = [staff_id]
    filters = {
        "q": (args.get("q") or "").strip(),
        "status": args.get("status", ""),
        "priority": args.get("priority", ""),
        "sort": args.get("sort", "newest"),
    }
    if filters["q"]:
        where.append("(c.title LIKE %s OR c.tracking_number LIKE %s OR c.location_address LIKE %s)")
        params.extend([f"%{filters['q']}%"] * 3)
    if filters["status"] in STATUSES:
        where.append("c.status = %s")
        params.append(filters["status"])
    if filters["priority"] in PRIORITIES:
        where.append("c.priority = %s")
        params.append(filters["priority"])
    order = {
        "oldest": "c.created_at ASC",
        "priority": "FIELD(c.priority, 'Urgent', 'High', 'Medium', 'Low'), c.created_at DESC",
        "status": "c.status ASC, c.created_at DESC",
    }.get(filters["sort"], "ca.assigned_at DESC")
    return " WHERE " + " AND ".join(where), tuple(params), order, filters


@staff.route("/dashboard")
@role_required("staff")
def dashboard():
    user = current_user()
    stats = complaint_service.staff_stats(user["id"])
    tasks = query(
        "SELECT c.id, c.tracking_number, c.title, c.status, c.priority, c.location_address, "
        "c.created_at, ca.assigned_at, cat.name AS category_name "
        "FROM complaint_assignments ca JOIN complaints c ON c.id = ca.complaint_id "
        "JOIN complaint_categories cat ON cat.id = c.category_id "
        "WHERE ca.staff_id = %s AND ca.is_current = 1 "
        "ORDER BY FIELD(c.status, 'In Progress', 'Assigned', 'Reopened', 'Verified', 'Submitted'), "
        "ca.assigned_at DESC LIMIT 8", (user["id"],)
    )
    return render_template(
        "staff_dashboard.html",
        stats=stats,
        tasks=tasks,
        unread=unread_count(user["id"]),
    )


@staff.route("/tasks")
@role_required("staff")
def tasks():
    user = current_user()
    clause, params, order, filters = _task_filters(request.args, user["id"])
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 10
    base = (
        "FROM complaint_assignments ca JOIN complaints c ON c.id = ca.complaint_id "
        "JOIN complaint_categories cat ON cat.id = c.category_id"
    )
    total = query("SELECT COUNT(*) AS c " + base + clause, params, one=True)["c"]
    rows = query(
        "SELECT c.id, c.tracking_number, c.title, c.status, c.priority, c.location_address, "
        "c.created_at, ca.assigned_at, cat.name AS category_name, "
        "(SELECT COUNT(*) FROM complaint_updates u WHERE u.complaint_id = c.id) AS update_count " + base +
        clause + " ORDER BY " + order + " LIMIT %s OFFSET %s",
        params + (per_page, (page - 1) * per_page),
    )
    return render_template(
        "staff_tasks.html",
        tasks=rows,
        filters=filters,
        page=page,
        pages=max(1, (total + per_page - 1) // per_page),
        total=total,
        stats=complaint_service.staff_stats(user["id"]),
    )


@staff.route("/tasks/<int:complaint_id>")
@role_required("staff")
def task_detail(complaint_id):
    user = current_user()
    complaint = _staff_complaint(complaint_id, user["id"])
    images = complaint_service.get_images(complaint_id)
    return render_template(
        "staff_task_detail.html",
        complaint=complaint,
        complaint_images=[item for item in images if item["image_type"] == "complaint"],
        progress_images=[item for item in images if item["image_type"] == "progress"],
        resolution_images=[item for item in images if item["image_type"] == "resolution"],
        timeline=complaint_service.get_timeline(complaint_id, public_only=False),
        allowed_statuses=ALLOWED_STAFF_STATUSES,
    )


@staff.route("/tasks/<int:complaint_id>/progress", methods=["POST"])
@role_required("staff")
def task_progress(complaint_id):
    user = current_user()
    complaint = _staff_complaint(complaint_id, user["id"])
    body = (request.form.get("body") or "").strip()
    if len(body) < 5 and not request.files.getlist("images"):
        flash("Add a progress note of at least 5 characters or attach an image.", "warning")
        return redirect(url_for("staff.task_detail", complaint_id=complaint_id))
    try:
        saved = save_images(request.files.getlist("images"), limit=3)
    except UploadError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("staff.task_detail", complaint_id=complaint_id))
    if body:
        complaint_service.add_update(complaint_id, user["id"], "progress", body=body, is_public=True)
    for file_path, original in saved:
        execute(
            "INSERT INTO complaint_images (complaint_id, file_path, original_name, image_type, uploaded_by) "
            "VALUES (%s, %s, %s, 'progress', %s)",
            (complaint_id, file_path, original, user["id"]),
        )
    if saved or body:
        notify(
            complaint["citizen_id"], complaint_id, "Progress update",
            f"Staff posted an update on {complaint['tracking_number']}.", "progress",
        )
        _audit("add_progress", complaint_id, f"Note: {body[:120]}; images: {len(saved)}")
        flash("Progress update posted.", "success")
    return redirect(url_for("staff.task_detail", complaint_id=complaint_id))


@staff.route("/tasks/<int:complaint_id>/status", methods=["POST"])
@role_required("staff")
def task_status(complaint_id):
    user = current_user()
    complaint = _staff_complaint(complaint_id, user["id"])
    status = request.form.get("status", "")
    note = (request.form.get("note") or "").strip()
    if status not in ALLOWED_STAFF_STATUSES:
        flash("Choose a valid staff status.", "danger")
    elif complaint_service.change_status(complaint_id, status, user["id"], note):
        _audit("change_status", complaint_id, f"Staff set status to {status}")
        flash(f"Status updated to {status}.", "success")
    else:
        flash("Status was not changed.", "warning")
    return redirect(url_for("staff.task_detail", complaint_id=complaint_id))


@staff.route("/tasks/<int:complaint_id>/resolve", methods=["POST"])
@role_required("staff")
def task_resolve(complaint_id):
    user = current_user()
    complaint = _staff_complaint(complaint_id, user["id"])
    note = (request.form.get("note") or "").strip()
    if len(note) < 10:
        flash("Describe the resolution in at least 10 characters.", "danger")
        return redirect(url_for("staff.task_detail", complaint_id=complaint_id))
    try:
        saved = save_images(request.files.getlist("images"), limit=4)
    except UploadError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("staff.task_detail", complaint_id=complaint_id))
    for file_path, original in saved:
        execute(
            "INSERT INTO complaint_images (complaint_id, file_path, original_name, image_type, uploaded_by) "
            "VALUES (%s, %s, %s, 'resolution', %s)",
            (complaint_id, file_path, original, user["id"]),
        )
    complaint_service.add_update(
        complaint_id, user["id"], "resolution", body=f"Resolution note: {note}", is_public=True
    )
    if complaint["status"] != "Resolved":
        complaint_service.change_status(complaint_id, "Resolved", user["id"], note)
    else:
        notify_status(complaint_id, "Resolved", user["id"])
    _audit("resolve_complaint", complaint_id, f"Evidence images: {len(saved)}")
    flash("Complaint resolved and citizen notified.", "success")
    return redirect(url_for("staff.task_detail", complaint_id=complaint_id))


@staff.route("/tasks/<int:complaint_id>/escalate", methods=["POST"])
@role_required("staff")
def task_escalate(complaint_id):
    user = current_user()
    complaint = _staff_complaint(complaint_id, user["id"])
    reason = (request.form.get("reason") or "").strip()
    if len(reason) < 10:
        flash("Provide a clear escalation reason.", "danger")
        return redirect(url_for("staff.task_detail", complaint_id=complaint_id))
    complaint_service.add_update(
        complaint_id, user["id"], "escalation", body=f"Escalation requested: {reason}", is_public=False
    )
    for admin in query("SELECT id FROM users WHERE role = 'admin' AND is_active = 1"):
        notify(
            admin["id"], complaint_id, "Staff escalation",
            f"{user['full_name']} needs support on {complaint['tracking_number']}: {reason[:200]}",
            "escalation",
        )
    _audit("escalate_complaint", complaint_id, reason[:200])
    flash("Administrators have been notified.", "success")
    return redirect(url_for("staff.task_detail", complaint_id=complaint_id))
