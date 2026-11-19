"""Public civic analytics and reporting dashboard."""

from flask import Blueprint, render_template

from database.db import query
from services import complaint_service

analytics = Blueprint("analytics", __name__, url_prefix="/analytics")


@analytics.route("")
@analytics.route("/")
def overview():
    categories = complaint_service.category_distribution()
    statuses = complaint_service.status_distribution()
    priorities = query(
        "SELECT priority AS label, COUNT(*) AS value FROM complaints "
        "GROUP BY priority ORDER BY FIELD(priority, 'Urgent', 'High', 'Medium', 'Low')"
    )
    monthly = complaint_service.monthly_distribution(12)
    departments = complaint_service.department_performance()
    stats = complaint_service.admin_stats()
    resolution = query(
        "SELECT ROUND(AVG(TIMESTAMPDIFF(HOUR, created_at, resolved_at)), 1) AS avg_hours "
        "FROM complaints WHERE resolved_at IS NOT NULL",
        one=True,
    ) or {}
    totals = query(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(is_public = 1), 0) AS public_count, "
        "COALESCE((SELECT COUNT(*) FROM complaint_supports), 0) AS support_count, "
        "COALESCE(SUM(priority = 'Urgent' AND status NOT IN ('Resolved', 'Rejected')), 0) AS urgent_open "
        "FROM complaints",
        one=True,
    ) or {}
    locations = query(
        "SELECT location_address AS label, COUNT(*) AS value FROM complaints "
        "GROUP BY location_address ORDER BY value DESC LIMIT 6"
    )
    return render_template(
        "analytics.html",
        stats=stats,
        totals=totals,
        avg_hours=resolution.get("avg_hours"),
        category_labels=[row["label"] for row in categories],
        category_values=[row["value"] for row in categories],
        status_labels=[row["label"] for row in statuses],
        status_values=[row["value"] for row in statuses],
        priority_labels=[row["label"] for row in priorities],
        priority_values=[row["value"] for row in priorities],
        month_labels=[row["label"] for row in monthly],
        month_values=[row["value"] for row in monthly],
        dept_labels=[row["label"] for row in departments],
        dept_values=[row["total"] for row in departments],
        location_labels=[row["label"] for row in locations],
        location_values=[row["value"] for row in locations],
    )
