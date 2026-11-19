"""Core complaint queries and workflow operations."""

from datetime import datetime

from database.db import DatabaseError, execute, query, transaction
from services.notification_service import notify_status

COMPLAINT_SELECT = """
    SELECT c.*, cat.name AS category_name, cat.icon AS category_icon,
           u.full_name AS citizen_name,
           d.id AS department_id_value, d.name AS department_name,
           s.full_name AS staff_name, s.id AS staff_id_value,
           (SELECT COUNT(*) FROM complaint_supports sp WHERE sp.complaint_id = c.id) AS support_count
    FROM complaints c
    JOIN complaint_categories cat ON cat.id = c.category_id
    JOIN users u ON u.id = c.citizen_id
    LEFT JOIN complaint_assignments ca ON ca.complaint_id = c.id AND ca.is_current = 1
    LEFT JOIN departments d ON d.id = ca.department_id
    LEFT JOIN users s ON s.id = ca.staff_id
"""

OPEN_STATUSES = ("Submitted", "Under Review", "Verified", "Assigned", "Reopened")


def get_complaint(complaint_id):
    return query(COMPLAINT_SELECT + " WHERE c.id = %s", (complaint_id,), one=True)


def get_by_tracking(tracking_number):
    return query(
        COMPLAINT_SELECT + " WHERE c.tracking_number = %s",
        ((tracking_number or "").strip().upper(),),
        one=True,
    )


def get_images(complaint_id, image_type=None):
    sql = (
        "SELECT id, file_path, original_name, image_type, created_at FROM complaint_images "
        "WHERE complaint_id = %s"
    )
    params = [complaint_id]
    if image_type:
        sql += " AND image_type = %s"
        params.append(image_type)
    return query(sql + " ORDER BY created_at ASC", tuple(params))


def get_timeline(complaint_id, public_only=True):
    sql = (
        "SELECT u.id, u.update_type, u.from_status, u.to_status, u.body, u.created_at, "
        "usr.full_name AS author "
        "FROM complaint_updates u LEFT JOIN users usr ON usr.id = u.user_id "
        "WHERE u.complaint_id = %s"
    )
    if public_only:
        sql += " AND u.is_public = 1"
    return query(sql + " ORDER BY u.created_at ASC, u.id ASC", (complaint_id,))


def add_update(complaint_id, user_id, update_type, from_status=None, to_status=None,
               body=None, is_public=True):
    return execute(
        "INSERT INTO complaint_updates "
        "(complaint_id, user_id, update_type, from_status, to_status, body, is_public) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (complaint_id, user_id, update_type, from_status, to_status, body, int(bool(is_public))),
    )["lastrowid"]


def generate_tracking_number():
    year = datetime.now().year
    row = query(
        "SELECT tracking_number FROM complaints WHERE tracking_number LIKE %s "
        "ORDER BY tracking_number DESC LIMIT 1",
        (f"CFX-{year}-%",),
        one=True,
    )
    sequence = 1
    if row:
        try:
            sequence = int(row["tracking_number"].split("-")[-1]) + 1
        except (ValueError, IndexError):
            sequence = 1
    return f"CFX-{year}-{sequence:05d}"


def create_complaint(citizen_id, data, image_paths, priority_suggestion):
    tracking = generate_tracking_number()
    with transaction() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "INSERT INTO complaints "
                "(tracking_number, citizen_id, category_id, title, description, additional_details, location_address, "
                " latitude, longitude, status, priority, suggested_priority, priority_reason) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Submitted', %s, %s, %s)",
                (
                    tracking, citizen_id, data["category_id"], data["title"], data["description"],
                    data.get("additional_details") or None, data["location_address"], data.get("latitude"), data.get("longitude"),
                    priority_suggestion["priority"], priority_suggestion["priority"],
                    priority_suggestion["reason"],
                ),
            )
            complaint_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO complaint_updates "
                "(complaint_id, user_id, update_type, to_status, body, is_public) "
                "VALUES (%s, %s, 'status', 'Submitted', %s, 1)",
                (complaint_id, citizen_id, "Complaint submitted by citizen."),
            )
            for path, original in image_paths:
                cursor.execute(
                    "INSERT INTO complaint_images (complaint_id, file_path, original_name, image_type, uploaded_by) "
                    "VALUES (%s, %s, %s, 'complaint', %s)",
                    (complaint_id, path, original, citizen_id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
    notify_status(complaint_id, "Submitted", citizen_id)
    return complaint_id, tracking


def change_status(complaint_id, new_status, actor_id, note=None, is_public=True):
    complaint = get_complaint(complaint_id)
    if not complaint:
        return False
    old_status = complaint["status"]
    if old_status == new_status:
        return False
    resolved_at = "CURRENT_TIMESTAMP" if new_status == "Resolved" else "NULL"
    with transaction() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                f"UPDATE complaints SET status = %s, resolved_at = {resolved_at} WHERE id = %s",
                (new_status, complaint_id),
            )
            cursor.execute(
                "INSERT INTO complaint_updates "
                "(complaint_id, user_id, update_type, from_status, to_status, body, is_public) "
                "VALUES (%s, %s, 'status', %s, %s, %s, %s)",
                (complaint_id, actor_id, old_status, new_status, note, int(bool(is_public))),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
    notify_status(complaint_id, new_status, actor_id)
    return True


def set_priority(complaint_id, priority, actor_id, note=None):
    complaint = get_complaint(complaint_id)
    if not complaint or complaint["priority"] == priority:
        return False
    execute("UPDATE complaints SET priority = %s WHERE id = %s", (priority, complaint_id))
    add_update(
        complaint_id, actor_id, "priority", body=note or f"Priority changed from {complaint['priority']} to {priority}.",
        is_public=False,
    )
    staff_id = complaint["staff_id_value"]
    if staff_id:
        from services.notification_service import notify_staff

        notify_staff(
            complaint_id, staff_id,
            "Priority changed",
            f"Complaint {complaint['tracking_number']} priority changed to {priority}.",
            "priority",
        )
    return True


def assign_complaint(complaint_id, department_id, staff_id, admin_id, note=None):
    complaint = get_complaint(complaint_id)
    if not complaint:
        return False
    with transaction() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "UPDATE complaint_assignments SET is_current = 0 WHERE complaint_id = %s AND is_current = 1",
                (complaint_id,),
            )
            cursor.execute(
                "INSERT INTO complaint_assignments "
                "(complaint_id, department_id, staff_id, assigned_by, note, is_current) "
                "VALUES (%s, %s, %s, %s, %s, 1)",
                (complaint_id, department_id, staff_id or None, admin_id, note),
            )
            if complaint["status"] in OPEN_STATUSES:
                cursor.execute(
                    "UPDATE complaints SET status = 'Assigned' WHERE id = %s", (complaint_id,)
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
    add_update(
        complaint_id, admin_id, "assignment", complaint["status"], "Assigned",
        note or "Complaint assigned to a department.",
    )
    notify_status(complaint_id, "Assigned", admin_id)
    if staff_id:
        from services.notification_service import notify_staff

        notify_staff(
            complaint_id, staff_id,
            "New assignment",
            f"Complaint {complaint['tracking_number']} was assigned to you.",
            "assignment",
        )
    return True


def has_support(complaint_id, user_id) -> bool:
    row = query(
        "SELECT id FROM complaint_supports WHERE complaint_id = %s AND user_id = %s",
        (complaint_id, user_id),
        one=True,
    )
    return bool(row)


def toggle_support(complaint_id, user_id) -> bool:
    """Returns True when a support was added, False when removed."""
    if has_support(complaint_id, user_id):
        execute("DELETE FROM complaint_supports WHERE complaint_id = %s AND user_id = %s",
                (complaint_id, user_id))
        return False
    execute("INSERT INTO complaint_supports (complaint_id, user_id) VALUES (%s, %s)",
            (complaint_id, user_id))
    return True


def citizen_stats(user_id):
    return query(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(status IN ('Submitted','Under Review','Verified','Assigned','Reopened')),0) AS pending, "
        "COALESCE(SUM(status = 'In Progress'),0) AS in_progress, "
        "COALESCE(SUM(status = 'Resolved'),0) AS resolved "
        "FROM complaints WHERE citizen_id = %s",
        (user_id,),
        one=True,
    ) or {}


def admin_stats():
    row = query(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(status IN ('Submitted','Under Review')),0) AS pending_review, "
        "COALESCE(SUM(status = 'In Progress'),0) AS in_progress, "
        "COALESCE(SUM(status = 'Resolved'),0) AS resolved, "
        "COALESCE(SUM(priority = 'Urgent' AND status NOT IN ('Resolved','Rejected')),0) AS urgent, "
        "COALESCE(ROUND(100 * SUM(status = 'Resolved') / NULLIF(COUNT(*), 0), 1),0) AS resolution_rate "
        "FROM complaints",
        one=True,
    ) or {}
    return row


def staff_stats(staff_id):
    return query(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(c.status IN ('Submitted','Under Review','Verified','Assigned','Reopened')),0) AS pending, "
        "COALESCE(SUM(c.status = 'In Progress'),0) AS in_progress, "
        "COALESCE(SUM(c.status = 'Resolved'),0) AS completed "
        "FROM complaint_assignments ca JOIN complaints c ON c.id = ca.complaint_id "
        "WHERE ca.staff_id = %s AND ca.is_current = 1",
        (staff_id,),
        one=True,
    ) or {}


def status_distribution(user_id=None):
    if user_id:
        return query(
            "SELECT status AS label, COUNT(*) AS value FROM complaints WHERE citizen_id = %s "
            "GROUP BY status ORDER BY value DESC",
            (user_id,),
        )
    return query("SELECT status AS label, COUNT(*) AS value FROM complaints GROUP BY status ORDER BY value DESC")


def category_distribution(user_id=None):
    if user_id:
        return query(
            "SELECT cat.name AS label, COUNT(*) AS value FROM complaints c "
            "JOIN complaint_categories cat ON cat.id = c.category_id WHERE c.citizen_id = %s "
            "GROUP BY cat.name ORDER BY value DESC",
            (user_id,),
        )
    return query(
        "SELECT cat.name AS label, COUNT(*) AS value FROM complaints c "
        "JOIN complaint_categories cat ON cat.id = c.category_id "
        "GROUP BY cat.name ORDER BY value DESC"
    )


def monthly_distribution(months=6):
    return query(
        "SELECT DATE_FORMAT(created_at, '%%b') AS label, COUNT(*) AS value "
        "FROM complaints WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL %s MONTH) "
        "GROUP BY YEAR(created_at), MONTH(created_at), DATE_FORMAT(created_at, '%%b') "
        "ORDER BY MIN(created_at)",
        (months,),
    )


def recent_complaints(user_id=None, limit=6, status=None):
    sql = COMPLAINT_SELECT
    params = []
    where = []
    if user_id:
        where.append("c.citizen_id = %s")
        params.append(user_id)
    if status:
        where.append("c.status = %s")
        params.append(status)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY c.created_at DESC LIMIT %s"
    params.append(limit)
    return query(sql, tuple(params))


def citizen_activity(user_id, limit=6):
    return query(
        "SELECT u.body, u.to_status, u.update_type, u.created_at, c.tracking_number, c.title "
        "FROM complaint_updates u JOIN complaints c ON c.id = u.complaint_id "
        "WHERE c.citizen_id = %s AND u.is_public = 1 "
        "ORDER BY u.created_at DESC LIMIT %s",
        (user_id, limit),
    )


def department_performance():
    return query(
        "SELECT d.name AS label, COUNT(*) AS total, "
        "COALESCE(SUM(c.status = 'Resolved'),0) AS resolved "
        "FROM complaint_assignments ca "
        "JOIN departments d ON d.id = ca.department_id "
        "JOIN complaints c ON c.id = ca.complaint_id "
        "WHERE ca.is_current = 1 GROUP BY d.name ORDER BY total DESC"
    )


def log_audit(user_id, action, entity_type, entity_id, details, ip_address=None):
    try:
        execute(
            "INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, action, entity_type, entity_id, details, ip_address),
        )
    except DatabaseError:
        pass
