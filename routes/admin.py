"""Administrator workspace: complaints, departments, staff, citizens and audit."""

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.security import generate_password_hash

from config import Config
from database.db import DatabaseError, execute, query
from services import complaint_service
from services.notification_service import unread_count
from utils.decorators import current_user, role_required
from utils.validators import PRIORITIES, STATUSES, parse_date, password_errors, valid_email

admin = Blueprint("admin", __name__, url_prefix="/admin")


def _departments(include_inactive=True):
    sql = "SELECT id, name, code, description, is_active FROM departments"
    if not include_inactive:
        sql += " WHERE is_active = 1"
    return query(sql + " ORDER BY name")


def _staff(active_only=False):
    sql = (
        "SELECT u.id, u.full_name, u.email, u.phone, u.is_active, u.department_id, "
        "d.name AS department_name FROM users u LEFT JOIN departments d ON d.id = u.department_id "
        "WHERE u.role = 'staff'"
    )
    if active_only:
        sql += " AND u.is_active = 1"
    return query(sql + " ORDER BY u.full_name")


def _audit(action, entity_type, entity_id, details):
    complaint_service.log_audit(
        current_user()["id"], action, entity_type, entity_id, details, request.remote_addr
    )


@admin.route("/dashboard")
@role_required("admin")
def dashboard():
    stats = complaint_service.admin_stats()
    status_rows = complaint_service.status_distribution()
    categories = complaint_service.category_distribution()
    monthly = complaint_service.monthly_distribution()
    departments = complaint_service.department_performance()
    return render_template(
        "admin_dashboard.html",
        stats=stats,
        recent=complaint_service.recent_complaints(limit=8),
        status_labels=[row["label"] for row in status_rows],
        status_values=[row["value"] for row in status_rows],
        category_labels=[row["label"] for row in categories],
        category_values=[row["value"] for row in categories],
        month_labels=[row["label"] for row in monthly],
        month_values=[row["value"] for row in monthly],
        dept_labels=[row["label"] for row in departments],
        dept_values=[row["resolved"] for row in departments],
        unread=unread_count(current_user()["id"]),
    )


def _complaint_filters(args):
    where = []
    params = []
    filters = {
        "q": (args.get("q") or "").strip(),
        "status": args.get("status", ""),
        "category": args.get("category", "", type=int),
        "priority": args.get("priority", ""),
        "date_from": args.get("date_from", ""),
        "date_to": args.get("date_to", ""),
        "sort": args.get("sort", "newest"),
    }
    if filters["q"]:
        where.append("(c.title LIKE %s OR c.tracking_number LIKE %s OR c.location_address LIKE %s)")
        params.extend([f"%{filters['q']}%"] * 3)
    if filters["status"] in STATUSES:
        where.append("c.status = %s")
        params.append(filters["status"])
    if filters["category"]:
        where.append("c.category_id = %s")
        params.append(filters["category"])
    if filters["priority"] in PRIORITIES:
        where.append("c.priority = %s")
        params.append(filters["priority"])
    errors = []
    date_from = parse_date(filters["date_from"], "start date", errors)
    date_to = parse_date(filters["date_to"], "end date", errors)
    if date_from:
        where.append("DATE(c.created_at) >= %s")
        params.append(date_from)
    if date_to:
        where.append("DATE(c.created_at) <= %s")
        params.append(date_to)
    for error in errors:
        flash(error, "warning")
    order = {
        "oldest": "c.created_at ASC",
        "priority": "FIELD(c.priority, 'Urgent', 'High', 'Medium', 'Low'), c.created_at DESC",
        "status": "c.status ASC, c.created_at DESC",
    }.get(filters["sort"], "c.created_at DESC")
    return (" WHERE " + " AND ".join(where) if where else ""), tuple(params), order, filters


@admin.route("/complaints")
@role_required("admin")
def complaints_list():
    clause, params, order, filters = _complaint_filters(request.args)
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 12
    count_row = query("SELECT COUNT(*) AS c FROM complaints c" + clause, params, one=True)
    total = count_row["c"] if count_row else 0
    rows = query(
        "SELECT c.id, c.tracking_number, c.title, c.location_address, c.status, c.priority, "
        "c.created_at, cat.name AS category_name, "
        "(SELECT COUNT(*) FROM complaint_supports sp WHERE sp.complaint_id = c.id) AS support_count, "
        "d.name AS department_name "
        "FROM complaints c JOIN complaint_categories cat ON cat.id = c.category_id "
        "LEFT JOIN complaint_assignments ca ON ca.complaint_id = c.id AND ca.is_current = 1 "
        "LEFT JOIN departments d ON d.id = ca.department_id " + clause +
        " ORDER BY " + order + " LIMIT %s OFFSET %s",
        params + (per_page, (page - 1) * per_page),
    )
    return render_template(
        "admin_complaints.html",
        complaints=rows,
        categories=query("SELECT id, name FROM complaint_categories ORDER BY name"),
        filters=filters,
        page=page,
        pages=max(1, (total + per_page - 1) // per_page),
        total=total,
    )


@admin.route("/complaints/<int:complaint_id>")
@role_required("admin")
def complaint_review(complaint_id):
    complaint = complaint_service.get_complaint(complaint_id)
    if not complaint:
        abort(404)
    return render_template(
        "admin_complaint_detail.html",
        complaint=complaint,
        images=complaint_service.get_images(complaint_id),
        timeline=complaint_service.get_timeline(complaint_id, public_only=False),
        departments=_departments(),
        staff=_staff(),
        priorities=PRIORITIES,
        statuses=STATUSES,
    )


@admin.route("/complaints/<int:complaint_id>/status", methods=["POST"])
@role_required("admin")
def complaint_status(complaint_id):
    status = request.form.get("status", "")
    note = (request.form.get("note") or "").strip()
    if status not in STATUSES:
        flash("Choose a valid status.", "danger")
    elif complaint_service.change_status(complaint_id, status, current_user()["id"], note):
        _audit("change_status", "complaint", complaint_id, f"Status changed to {status}")
        flash(f"Status updated to {status}.", "success")
    else:
        flash("Status was not changed.", "warning")
    return redirect(url_for("admin.complaint_review", complaint_id=complaint_id))


@admin.route("/complaints/<int:complaint_id>/priority", methods=["POST"])
@role_required("admin")
def complaint_priority(complaint_id):
    priority = request.form.get("priority", "")
    note = (request.form.get("note") or "").strip()
    if priority not in PRIORITIES:
        flash("Choose a valid priority.", "danger")
    elif complaint_service.set_priority(complaint_id, priority, current_user()["id"], note):
        _audit("change_priority", "complaint", complaint_id, f"Priority overridden to {priority}")
        flash(f"Priority updated to {priority}.", "success")
    else:
        flash("Priority was not changed.", "warning")
    return redirect(url_for("admin.complaint_review", complaint_id=complaint_id))


@admin.route("/complaints/<int:complaint_id>/assign", methods=["POST"])
@role_required("admin")
def complaint_assign(complaint_id):
    try:
        department_id = int(request.form.get("department_id") or 0)
    except ValueError:
        department_id = 0
    staff_id = request.form.get("staff_id") or None
    note = (request.form.get("note") or "").strip()
    if not query("SELECT id FROM departments WHERE id = %s AND is_active = 1", (department_id,), one=True):
        flash("Choose a valid department.", "danger")
        return redirect(url_for("admin.complaint_review", complaint_id=complaint_id))
    if staff_id:
        try:
            staff_id = int(staff_id)
        except ValueError:
            staff_id = None
        valid = query(
            "SELECT id FROM users WHERE id = %s AND role = 'staff' AND is_active = 1 AND "
            "(department_id = %s OR department_id IS NULL)",
            (staff_id, department_id), one=True,
        )
        if not valid:
            flash("That staff member cannot be assigned to this department.", "danger")
            return redirect(url_for("admin.complaint_review", complaint_id=complaint_id))
    if complaint_service.assign_complaint(complaint_id, department_id, staff_id, current_user()["id"], note):
        _audit("assign_complaint", "complaint", complaint_id,
               f"Department {department_id}, staff {staff_id or 'unassigned'}")
        flash("Complaint assigned successfully.", "success")
    return redirect(url_for("admin.complaint_review", complaint_id=complaint_id))


@admin.route("/complaints/<int:complaint_id>/reject", methods=["POST"])
@role_required("admin")
def complaint_reject(complaint_id):
    reason = (request.form.get("reason") or "").strip()
    if len(reason) < 10:
        flash("Provide a rejection reason of at least 10 characters.", "danger")
        return redirect(url_for("admin.complaint_review", complaint_id=complaint_id))
    execute(
        "UPDATE complaints SET status = 'Rejected', rejection_reason = %s WHERE id = %s",
        (reason, complaint_id),
    )
    complaint_service.add_update(
        complaint_id, current_user()["id"], "status", None, "Rejected", f"Rejected: {reason}"
    )
    from services.notification_service import notify_status

    notify_status(complaint_id, "Rejected", current_user()["id"])
    _audit("reject_complaint", "complaint", complaint_id, reason[:200])
    flash("Complaint rejected with reason recorded.", "success")
    return redirect(url_for("admin.complaint_review", complaint_id=complaint_id))


@admin.route("/departments")
@role_required("admin")
def departments():
    rows = query(
        "SELECT d.*, (SELECT COUNT(*) FROM users u WHERE u.department_id = d.id AND u.role = 'staff') AS staff_count, "
        "(SELECT COUNT(*) FROM complaint_assignments ca WHERE ca.department_id = d.id AND ca.is_current = 1) AS complaint_count "
        "FROM departments d ORDER BY d.name"
    )
    return render_template("admin_departments.html", departments=rows)


@admin.route("/departments", methods=["POST"])
@role_required("admin")
def department_create():
    name = (request.form.get("name") or "").strip()
    code = (request.form.get("code") or "").strip().upper()
    description = (request.form.get("description") or "").strip()
    if len(name) < 2 or len(code) < 2:
        flash("Department name and code are required.", "danger")
    else:
        try:
            result = execute(
                "INSERT INTO departments (name, code, description) VALUES (%s, %s, %s)",
                (name, code, description or None),
            )
            _audit("create_department", "department", result["lastrowid"], name)
            flash("Department created.", "success")
        except DatabaseError:
            flash("A department with that name or code already exists.", "danger")
    return redirect(url_for("admin.departments"))


@admin.route("/departments/<int:department_id>", methods=["POST"])
@role_required("admin")
def department_update(department_id):
    name = (request.form.get("name") or "").strip()
    code = (request.form.get("code") or "").strip().upper()
    description = (request.form.get("description") or "").strip()
    is_active = 1 if request.form.get("is_active") in {"1", "on"} else 0
    if len(name) < 2 or len(code) < 2:
        flash("Department name and code are required.", "danger")
    else:
        try:
            execute(
                "UPDATE departments SET name = %s, code = %s, description = %s, is_active = %s WHERE id = %s",
                (name, code, description or None, is_active, department_id),
            )
            _audit("update_department", "department", department_id, name)
            flash("Department updated.", "success")
        except DatabaseError:
            flash("Could not update department. Check for duplicate names or codes.", "danger")
    return redirect(url_for("admin.departments"))


@admin.route("/departments/<int:department_id>/view")
@role_required("admin")
def department_view(department_id):
    department = query("SELECT * FROM departments WHERE id = %s", (department_id,), one=True)
    if not department:
        abort(404)
    staff_rows = query("SELECT id, full_name, email, is_active FROM users WHERE department_id = %s AND role = 'staff'", (department_id,))
    complaints = query(
        "SELECT c.id, c.tracking_number, c.title, c.status, c.priority FROM complaint_assignments ca "
        "JOIN complaints c ON c.id = ca.complaint_id WHERE ca.department_id = %s AND ca.is_current = 1 "
        "ORDER BY c.created_at DESC LIMIT 20", (department_id,)
    )
    return render_template("admin_department_view.html", department=department, staff=staff_rows, complaints=complaints)


@admin.route("/staff")
@role_required("admin")
def staff_management():
    return render_template(
        "admin_staff.html", staff=_staff(), departments=_departments(include_inactive=False)
    )


@admin.route("/staff", methods=["POST"])
@role_required("admin")
def staff_create():
    full_name = (request.form.get("full_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    phone = (request.form.get("phone") or "").strip()
    password = request.form.get("password", "")
    try:
        department_id = int(request.form.get("department_id") or 0)
    except ValueError:
        department_id = 0
    errors = []
    if len(full_name) < 2:
        errors.append("Enter a valid full name.")
    if not valid_email(email):
        errors.append("Enter a valid email address.")
    errors.extend(password_errors(password))
    if not query("SELECT id FROM departments WHERE id = %s", (department_id,), one=True):
        errors.append("Choose a valid department.")
    if query("SELECT id FROM users WHERE email = %s", (email,), one=True):
        errors.append("An account with that email already exists.")
    if errors:
        for error in errors:
            flash(error, "danger")
        return redirect(url_for("admin.staff_management"))
    result = execute(
        "INSERT INTO users (full_name, email, phone, password_hash, role, department_id) "
        "VALUES (%s, %s, %s, %s, 'staff', %s)",
        (full_name, email, phone or None, generate_password_hash(password, method="pbkdf2:sha256:260000"), department_id),
    )
    _audit("create_staff", "user", result["lastrowid"], f"Created staff account {email}")
    flash("Staff account created.", "success")
    return redirect(url_for("admin.staff_management"))


@admin.route("/staff/<int:user_id>", methods=["POST"])
@role_required("admin")
def staff_update(user_id):
    user = query("SELECT id FROM users WHERE id = %s AND role = 'staff'", (user_id,), one=True)
    if not user:
        abort(404)
    full_name = (request.form.get("full_name") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    try:
        department_id = int(request.form.get("department_id") or 0)
    except ValueError:
        department_id = 0
    is_active = 1 if request.form.get("is_active") in {"1", "on"} else 0
    if len(full_name) < 2 or not query("SELECT id FROM departments WHERE id = %s", (department_id,), one=True):
        flash("Invalid staff details.", "danger")
    else:
        execute(
            "UPDATE users SET full_name = %s, phone = %s, department_id = %s, is_active = %s WHERE id = %s",
            (full_name, phone or None, department_id, is_active, user_id),
        )
        _audit("update_staff", "user", user_id, f"Active={is_active}")
        flash("Staff account updated.", "success")
    return redirect(url_for("admin.staff_management"))


@admin.route("/staff/<int:user_id>/tasks")
@role_required("admin")
def staff_tasks(user_id):
    user = query("SELECT id, full_name, email FROM users WHERE id = %s AND role = 'staff'", (user_id,), one=True)
    if not user:
        abort(404)
    tasks = query(
        "SELECT c.id, c.tracking_number, c.title, c.status, c.priority, cat.name AS category_name "
        "FROM complaint_assignments ca JOIN complaints c ON c.id = ca.complaint_id "
        "JOIN complaint_categories cat ON cat.id = c.category_id "
        "WHERE ca.staff_id = %s ORDER BY ca.assigned_at DESC LIMIT 30", (user_id,)
    )
    return render_template("admin_staff_tasks.html", staff=user, tasks=tasks)


@admin.route("/citizens")
@role_required("admin")
def citizens():
    search = (request.args.get("q") or "").strip()
    where = "WHERE u.role = 'citizen'"
    params = []
    if search:
        where += " AND (u.full_name LIKE %s OR u.email LIKE %s)"
        params = [f"%{search}%", f"%{search}%"]
    rows = query(
        "SELECT u.id, u.full_name, u.email, u.phone, u.is_active, u.created_at, "
        "(SELECT COUNT(*) FROM complaints c WHERE c.citizen_id = u.id) AS complaint_count "
        "FROM users u " + where + " ORDER BY u.created_at DESC LIMIT 100", tuple(params)
    )
    return render_template("admin_citizens.html", citizens=rows, search=search)


@admin.route("/citizens/<int:user_id>/toggle", methods=["POST"])
@role_required("admin")
def citizen_toggle(user_id):
    user = query("SELECT id, is_active FROM users WHERE id = %s AND role = 'citizen'", (user_id,), one=True)
    if user:
        execute("UPDATE users SET is_active = %s WHERE id = %s", (0 if user["is_active"] else 1, user_id))
        _audit("toggle_citizen", "user", user_id, "Account active state changed")
        flash("Citizen account status updated.", "success")
    return redirect(url_for("admin.citizens"))


@admin.route("/audit")
@role_required("admin")
def audit_logs():
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 20
    total = query("SELECT COUNT(*) AS c FROM audit_logs", one=True)["c"]
    rows = query(
        "SELECT a.*, u.full_name AS actor FROM audit_logs a LEFT JOIN users u ON u.id = a.user_id "
        "ORDER BY a.created_at DESC LIMIT %s OFFSET %s",
        (per_page, (page - 1) * per_page),
    )
    return render_template(
        "admin_audit.html", logs=rows, page=page, pages=max(1, (total + per_page - 1) // per_page)
    )


@admin.route("/settings")
@role_required("admin")
def settings():
    from database.db import health_check

    return render_template(
        "admin_settings.html",
        db_status="Connected" if health_check() else "Unavailable",
        upload_limit_mb=Config.MAX_UPLOAD_BYTES // (1024 * 1024),
        counts={
            "users": query("SELECT COUNT(*) AS c FROM users", one=True)["c"],
            "complaints": query("SELECT COUNT(*) AS c FROM complaints", one=True)["c"],
            "departments": query("SELECT COUNT(*) AS c FROM departments", one=True)["c"],
        },
    )
