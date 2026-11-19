"""Public pages (landing page and static information pages)."""

from flask import Blueprint, render_template

from database.db import DatabaseError, query

main = Blueprint("main", __name__)


def _one(sql, params=None):
    try:
        return query(sql, params, one=True) or {}
    except DatabaseError:
        return {}


def _all(sql, params=None):
    try:
        return query(sql, params)
    except DatabaseError:
        return []


@main.route("/")
def index():
    totals = _one(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END), 0) AS resolved, "
        "COALESCE(SUM(CASE WHEN status NOT IN ('Resolved', 'Rejected') THEN 1 ELSE 0 END), 0) AS active "
        "FROM complaints"
    )
    stats = {
        "total": totals.get("total") or 0,
        "resolved": totals.get("resolved") or 0,
        "active": totals.get("active") or 0,
        "departments": _one("SELECT COUNT(*) AS count FROM departments WHERE is_active = 1").get("count") or 0,
    }
    categories = _all(
        "SELECT name, icon, description FROM complaint_categories WHERE is_active = 1 ORDER BY id"
    )
    if not categories:
        categories = [
            {"name": name, "icon": icon, "description": description}
            for name, icon, description in [
                ("Roads & Potholes", "bi-sign-stop", "Potholes, cracked roads and footpaths."),
                ("Garbage & Sanitation", "bi-trash", "Waste collection and public cleanliness."),
                ("Water Supply", "bi-droplet", "Leaks, taps and water supply issues."),
                ("Streetlights", "bi-lightbulb", "Broken or flickering street lights."),
                ("Drainage", "bi-cloud-rain", "Blocked drains and waterlogging."),
                ("Public Infrastructure", "bi-building", "Damaged public property and amenities."),
                ("Other", "bi-three-dots", "Any other civic issue."),
            ]
        ]
    recent_complaints = _all(
        "SELECT c.tracking_number, c.title, c.location_address, c.status, c.created_at, "
        "cat.name AS category, cat.icon AS category_icon "
        "FROM complaints c JOIN complaint_categories cat ON cat.id = c.category_id "
        "WHERE c.is_public = 1 AND c.status <> 'Rejected' "
        "ORDER BY c.created_at DESC LIMIT 6"
    )
    return render_template(
        "index.html",
        stats=stats,
        categories=categories,
        recent_complaints=recent_complaints,
    )


@main.route("/map")
def city_map():
    complaints = _all(
        "SELECT c.id, c.tracking_number, c.title, c.location_address, c.latitude, c.longitude, "
        "c.status, c.priority, c.category_id, cat.name AS category_name "
        "FROM complaints c JOIN complaint_categories cat ON cat.id = c.category_id "
        "WHERE c.is_public = 1 AND c.status <> 'Rejected' AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL "
        "ORDER BY c.created_at DESC LIMIT 500"
    )
    categories = _all("SELECT id, name FROM complaint_categories WHERE is_active = 1 ORDER BY name")
    return render_template("city_map.html", complaints=complaints, categories=categories)


@main.route("/about")
def about():
    return render_template("pages/about.html")


@main.route("/contact")
def contact():
    return render_template("pages/contact.html")


@main.route("/privacy")
def privacy():
    return render_template("pages/privacy.html")


@main.route("/terms")
def terms():
    return render_template("pages/terms.html")
