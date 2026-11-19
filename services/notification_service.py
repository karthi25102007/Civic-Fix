"""In-app notification helpers (and optional SMTP email)."""

import smtplib
from email.message import EmailMessage

from config import Config
from database.db import DatabaseError, execute, query

STATUS_MESSAGES = {
    "Submitted": ("Complaint submitted", "Your complaint {tracking} was submitted successfully."),
    "Under Review": ("Complaint under review", "Complaint {tracking} is now being reviewed by an administrator."),
    "Verified": ("Complaint verified", "Complaint {tracking} has been verified."),
    "Assigned": ("Complaint assigned", "Complaint {tracking} has been assigned to a department."),
    "In Progress": ("Work in progress", "Work on complaint {tracking} has started."),
    "Resolved": ("Complaint resolved", "Complaint {tracking} has been resolved. Thank you for your report."),
    "Reopened": ("Complaint reopened", "Complaint {tracking} was reopened for further action."),
    "Rejected": ("Complaint rejected", "Complaint {tracking} was rejected. Please check the admin note."),
}


def send_email(to_address: str, subject: str, body: str) -> bool:
    """Send email only when SMTP settings are provided; never raise to callers."""
    if not Config.SMTP_HOST or not to_address:
        return False
    try:
        message = EmailMessage()
        message["From"] = Config.SMTP_FROM
        message["To"] = to_address
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=10) as smtp:
            smtp.starttls()
            if Config.SMTP_USER:
                smtp.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
            smtp.send_message(message)
        return True
    except Exception:
        return False


def notify(user_id, complaint_id, title, message, kind="info", email=False):
    if not user_id:
        return None
    try:
        result = execute(
            "INSERT INTO notifications (user_id, complaint_id, title, message, type) "
            "VALUES (%s, %s, %s, %s, %s)",
            (user_id, complaint_id, title[:180], message[:500], kind),
        )
    except DatabaseError:
        return None
    if email:
        user = query("SELECT email FROM users WHERE id = %s", (user_id,), one=True)
        if user:
            send_email(user["email"], title, message)
    return result["lastrowid"]


def notify_status(complaint_id, new_status, actor_id=None):
    complaint = query(
        "SELECT c.id, c.tracking_number, c.title, c.citizen_id, ca.staff_id, "
        "a.staff_id AS assigned_staff FROM complaints c "
        "LEFT JOIN complaint_assignments ca ON ca.complaint_id = c.id AND ca.is_current = 1 "
        "LEFT JOIN complaint_assignments a ON a.complaint_id = c.id AND a.is_current = 1 "
        "WHERE c.id = %s",
        (complaint_id,),
        one=True,
    )
    if not complaint:
        return
    title, template = STATUS_MESSAGES.get(new_status, ("Complaint updated", "Complaint {tracking} was updated."))
    message = template.format(tracking=complaint["tracking_number"])
    notify(complaint["citizen_id"], complaint_id, title, message, new_status.lower().replace(" ", "_"), email=True)
    staff_id = complaint["assigned_staff"]
    if staff_id and staff_id != actor_id and new_status in {"Assigned", "In Progress", "Reopened"}:
        notify(staff_id, complaint_id, title, message, "assignment")


def notify_staff(complaint_id, staff_id, title, message, kind="assignment"):
    notify(staff_id, complaint_id, title, message, kind)


def unread_count(user_id) -> int:
    row = query(
        "SELECT COUNT(*) AS count FROM notifications WHERE user_id = %s AND is_read = 0",
        (user_id,),
        one=True,
    )
    return (row or {}).get("count") or 0


def mark_read(notification_id, user_id) -> bool:
    result = execute(
        "UPDATE notifications SET is_read = 1, read_at = CURRENT_TIMESTAMP "
        "WHERE id = %s AND user_id = %s",
        (notification_id, user_id),
    )
    return result["rowcount"] > 0


def mark_all_read(user_id) -> int:
    result = execute(
        "UPDATE notifications SET is_read = 1, read_at = CURRENT_TIMESTAMP "
        "WHERE user_id = %s AND is_read = 0",
        (user_id,),
    )
    return result["rowcount"]
