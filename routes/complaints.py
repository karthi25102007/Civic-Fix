"""Complaint submission, details, tracking and community support routes."""

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from database.db import DatabaseError, execute, query
from services import complaint_service, duplicate_service, priority_service
from utils.decorators import current_user, login_required, role_required
from utils.upload_utils import UploadError, save_images
from utils.validators import TRACKING_RE, PRIORITIES, STATUSES

complaints = Blueprint("complaints", __name__)

SEVERITIES = ("Low", "Medium", "High", "Critical")
LOCATION_IMPORTANCE = ("residential", "commercial", "school", "hospital", "junction")


def _categories():
    return query("SELECT id, name, icon FROM complaint_categories WHERE is_active = 1 ORDER BY id")


def _validate_submission(form):
    errors = []
    title = (form.get("title") or "").strip()
    description = (form.get("description") or "").strip()
    address = (form.get("location_address") or "").strip()
    if len(title) < 5 or len(title) > 200:
        errors.append("Title must be between 5 and 200 characters.")
    if len(description) < 20:
        errors.append("Description must be at least 20 characters.")
    if len(address) < 5 or len(address) > 255:
        errors.append("Enter a valid location or address.")
    try:
        category_id = int(form.get("category_id") or 0)
    except ValueError:
        category_id = 0
    if not query("SELECT id FROM complaint_categories WHERE id = %s AND is_active = 1", (category_id,), one=True):
        errors.append("Choose a valid category.")

    latitude = longitude = None
    if form.get("latitude") or form.get("longitude"):
        try:
            latitude = float(form.get("latitude"))
            longitude = float(form.get("longitude"))
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise ValueError
        except (TypeError, ValueError):
            errors.append("Enter valid latitude and longitude values.")

    severity = form.get("severity", "Medium")
    if severity not in SEVERITIES:
        errors.append("Choose a valid severity level.")
    importance = form.get("location_importance", "residential")
    if importance not in LOCATION_IMPORTANCE:
        errors.append("Choose a valid location type.")
    data = {
        "category_id": category_id,
        "title": title,
        "description": description,
        "additional_details": (form.get("additional_details") or "").strip()[:2000] or None,
        "location_address": address,
        "latitude": latitude,
        "longitude": longitude,
        "severity": severity,
        "location_importance": importance,
        "safety_impact": form.get("safety_impact") in {"1", "on", "true"},
    }
    return data, errors


@complaints.route("/report", methods=["GET", "POST"])
@role_required("citizen")
def report():
    user = current_user()
    form_data = request.form.to_dict() if request.method == "POST" else {}
    preset = request.args.get("category", "")
    if request.method == "POST":
        data, errors = _validate_submission(request.form)
        images = []
        if not errors:
            try:
                images = save_images(request.files.getlist("images"))
            except UploadError as exc:
                errors.append(str(exc))
        if not errors:
            suggestion = priority_service.suggest_priority(data)
            try:
                complaint_id, tracking = complaint_service.create_complaint(user["id"], data, images, suggestion)
            except DatabaseError:
                errors.append("Could not save your complaint. Please try again.")
            else:
                complaint_service.log_audit(user["id"], "create_complaint", "complaint", complaint_id,
                                            f"Submitted {tracking}", request.remote_addr)
                flash("Your complaint was submitted successfully.", "success")
                similar = duplicate_service.find_duplicates(
                    data["title"], data["category_id"], data["latitude"], data["longitude"], limit=3
                )
                similar = [row for row in similar if row["id"] != complaint_id]
                return render_template("report_success.html", tracking=tracking, complaint_id=complaint_id, similar=similar)
        for error in errors:
            flash(error, "danger")
    return render_template(
        "report_issue.html",
        categories=_categories(),
        form=form_data,
        preset_category=preset,
        severities=SEVERITIES,
        location_types=LOCATION_IMPORTANCE,
    )


@complaints.route("/complaints/my")
@role_required("citizen")
def my_complaints():
    user = current_user()
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 10
    status = request.args.get("status", "")
    category_id = request.args.get("category", "", type=int)
    search = (request.args.get("q") or "").strip()
    where = ["c.citizen_id = %s"]
    params = [user["id"]]
    if status in STATUSES:
        where.append("c.status = %s")
        params.append(status)
    if category_id:
        where.append("c.category_id = %s")
        params.append(category_id)
    if search:
        where.append("(c.title LIKE %s OR c.tracking_number LIKE %s OR c.location_address LIKE %s)")
        params.extend([f"%{search}%"] * 3)
    clause = " WHERE " + " AND ".join(where)
    total = query("SELECT COUNT(*) AS c FROM complaints c" + clause, tuple(params), one=True)["c"]
    rows = query(
        "SELECT c.id, c.tracking_number, c.title, c.location_address, c.status, c.priority, "
        "c.created_at, cat.name AS category_name, "
        "(SELECT COUNT(*) FROM complaint_supports sp WHERE sp.complaint_id = c.id) AS support_count "
        "FROM complaints c JOIN complaint_categories cat ON cat.id = c.category_id " + clause +
        " ORDER BY c.created_at DESC LIMIT %s OFFSET %s",
        tuple(params + [per_page, (page - 1) * per_page]),
    )
    return render_template(
        "my_complaints.html",
        complaints=rows,
        categories=_categories(),
        status=status,
        category_id=category_id,
        search=search,
        page=page,
        pages=max(1, (total + per_page - 1) // per_page),
    )


@complaints.route("/complaints/supported")
@role_required("citizen")
def supported_complaints():
    user = current_user()
    rows = query(
        "SELECT c.id, c.tracking_number, c.title, c.status, c.location_address, c.created_at, "
        "cat.name AS category_name FROM complaint_supports sp "
        "JOIN complaints c ON c.id = sp.complaint_id "
        "JOIN complaint_categories cat ON cat.id = c.category_id "
        "WHERE sp.user_id = %s ORDER BY sp.created_at DESC",
        (user["id"],),
    )
    return render_template("supported_complaints.html", complaints=rows)


@complaints.route("/complaints/<int:complaint_id>")
@login_required
def detail(complaint_id):
    complaint = complaint_service.get_complaint(complaint_id)
    if not complaint:
        flash("Complaint not found.", "warning")
        return redirect(url_for("main.index"))
    user = current_user()
    is_owner = user["role"] == "citizen" and complaint["citizen_id"] == user["id"]
    is_admin = user["role"] == "admin"
    is_assigned = user["role"] == "staff" and complaint["staff_id_value"] == user["id"]
    if not complaint["is_public"] and not (is_owner or is_admin or is_assigned):
        from flask import abort

        abort(403)

    can_manage = is_admin or is_assigned
    timeline = complaint_service.get_timeline(complaint_id, public_only=not can_manage)
    admin_notes = (
        query(
            "SELECT u.body, u.created_at, usr.full_name FROM complaint_updates u "
            "LEFT JOIN users usr ON usr.id = u.user_id "
            "WHERE u.complaint_id = %s AND u.is_public = 0 ORDER BY u.created_at DESC",
            (complaint_id,),
        )
        if can_manage else []
    )
    return render_template(
        "complaint_details.html",
        complaint=complaint,
        images=complaint_service.get_images(complaint_id),
        resolution_images=complaint_service.get_images(complaint_id, "resolution"),
        progress_images=complaint_service.get_images(complaint_id, "progress"),
        timeline=timeline,
        admin_notes=admin_notes,
        can_manage=can_manage,
        is_owner=is_owner,
        is_admin=is_admin,
        is_assigned=is_assigned,
        supported=complaint_service.has_support(complaint_id, user["id"]) if user["role"] == "citizen" else False,
    )


@complaints.route("/complaints/<int:complaint_id>/support", methods=["POST"])
@role_required("citizen")
def support(complaint_id):
    if not complaint_service.get_complaint(complaint_id):
        flash("Complaint not found.", "warning")
        return redirect(url_for("complaints.my_complaints"))
    added = complaint_service.toggle_support(complaint_id, current_user()["id"])
    flash("You now support this complaint." if added else "Support removed.", "success")
    return redirect(request.referrer or url_for("complaints.detail", complaint_id=complaint_id))


@complaints.route("/complaints/<int:complaint_id>/reopen", methods=["POST"])
@role_required("citizen")
def reopen(complaint_id):
    complaint = complaint_service.get_complaint(complaint_id)
    if not complaint or complaint["citizen_id"] != current_user()["id"]:
        from flask import abort

        abort(403)
    if complaint["status"] not in {"Resolved", "Rejected"}:
        flash("This complaint cannot be reopened in its current state.", "warning")
    else:
        complaint_service.change_status(complaint_id, "Reopened", current_user()["id"],
                                        "Citizen requested reopening.")
        complaint_service.log_audit(current_user()["id"], "reopen_complaint", "complaint", complaint_id,
                                    "Reopened by citizen", request.remote_addr)
        flash("Complaint reopened for review.", "success")
    return redirect(url_for("complaints.detail", complaint_id=complaint_id))


@complaints.route("/track", methods=["GET", "POST"])
def track():
    complaint = None
    message = None
    if request.method == "POST":
        tracking = (request.form.get("tracking_number") or "").strip().upper()
        if not TRACKING_RE.fullmatch(tracking):
            message = "Enter a tracking number in the format CFX-2026-00001."
        else:
            complaint = complaint_service.get_by_tracking(tracking)
            if not complaint:
                message = "No complaint found with that tracking number."
            elif not complaint["is_public"]:
                user = current_user()
                allowed = user and (
                    user["role"] == "admin"
                    or (user["role"] == "citizen" and complaint["citizen_id"] == user["id"])
                    or (user["role"] == "staff" and complaint["staff_id_value"] == user["id"])
                )
                if not allowed:
                    complaint = None
                    message = "This complaint is private. Sign in with the associated account to view details."
    public_updates = (
        complaint_service.get_timeline(complaint["id"], public_only=True) if complaint else []
    )
    return render_template("track_complaint.html", complaint=complaint, message=message, updates=public_updates)


@complaints.route("/api/complaints/duplicate-check", methods=["POST"])
@role_required("citizen")
def duplicate_check_api():
    payload = request.get_json(silent=True) or {}
    try:
        category_id = int(payload.get("category_id") or 0)
    except (TypeError, ValueError):
        category_id = 0
    if not category_id:
        return jsonify({"matches": []})
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    matches = duplicate_service.find_duplicates(
        payload.get("title", ""), category_id, latitude, longitude, limit=3
    )
    return jsonify({
        "matches": [
            {
                "id": row["id"],
                "tracking_number": row["tracking_number"],
                "title": row["title"],
                "status": row["status"],
                "location": row["location_address"],
                "similarity": row["similarity"],
            }
            for row in matches
        ]
    })
