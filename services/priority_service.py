"""Explainable, rule-based priority suggestions (no machine learning)."""

from datetime import datetime

from database.db import DatabaseError, query

CATEGORY_WEIGHTS = {
    "Roads & Potholes": 2,
    "Garbage & Sanitation": 1,
    "Water Leakage": 2,
    "Streetlights": 2,
    "Drainage": 3,
    "Public Infrastructure": 1,
    "Other": 1,
}
SEVERITY_WEIGHTS = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}
LOCATION_WEIGHTS = {"residential": 0, "commercial": 0.5, "school": 1.5, "hospital": 2, "junction": 1.5}
RISK_WORDS = (
    "urgent", "danger", "accident", "fire", "flood", "manhole", "safety", "child",
    "school", "hospital", "electrocution", "collapse", "blocked", "leak", "broken glass",
)


def suggest_priority(data: dict) -> dict:
    """Return suggested priority, numeric score and a human-readable explanation."""
    score = 0.0
    reasons = []

    severity = data.get("severity", "Medium")
    severity_points = SEVERITY_WEIGHTS.get(severity, 1)
    score += severity_points
    reasons.append(f"reported severity: {severity} (+{severity_points})")

    try:
        category = query(
            "SELECT name FROM complaint_categories WHERE id = %s", (data.get("category_id"),), one=True
        )
    except DatabaseError:
        category = None
    category_name = (category or {}).get("name")
    category_points = CATEGORY_WEIGHTS.get(category_name, 1)
    score += category_points
    reasons.append(f"category: {category_name or 'general'} (+{category_points})")

    safety = data.get("safety_impact") in (True, "1", "on", "true", 1)
    if safety:
        score += 2
        reasons.append("safety impact reported (+2)")

    location = str(data.get("location_importance") or "residential").lower()
    location_points = LOCATION_WEIGHTS.get(location, 0)
    if location_points:
        score += location_points
        reasons.append(f"sensitive location: {location} (+{location_points})")

    text = f"{data.get('title', '')} {data.get('description', '')}".lower()
    matched = [word for word in RISK_WORDS if word in text][:3]
    if matched:
        word_points = min(len(matched), 2)
        score += word_points
        reasons.append(f"risk keywords: {', '.join(matched)} (+{word_points})")

    created_at = data.get("created_at")
    if isinstance(created_at, datetime):
        days = (datetime.now() - created_at).days
        if days >= 30:
            score += 1
            reasons.append(f"pending for {days} days (+1)")
        elif days >= 7:
            score += 0.5
            reasons.append(f"pending for {days} days (+0.5)")

    if score >= 7:
        priority = "Urgent"
    elif score >= 5:
        priority = "High"
    elif score >= 3:
        priority = "Medium"
    else:
        priority = "Low"

    return {"priority": priority, "score": round(score, 1), "reason": "; ".join(reasons)}
