"""Basic rule-based duplicate detection. Suggestions only, never auto-rejections."""

from difflib import SequenceMatcher

from database.db import DatabaseError, query

STOP_WORDS = {"the", "a", "an", "on", "at", "in", "near", "road", "street", "and", "of", "for"}


def _tokens(text: str) -> set:
    words = "".join(ch.lower() if ch.isalnum() else " " for ch in text).split()
    return {word for word in words if len(word) > 2 and word not in STOP_WORDS}


def find_duplicates(title, category_id, latitude=None, longitude=None, radius=0.012, days=365, limit=5):
    sql = (
        "SELECT id, tracking_number, title, status, location_address, created_at, "
        "latitude, longitude FROM complaints "
        "WHERE category_id = %s AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) "
        "AND status NOT IN ('Rejected', 'Resolved')"
    )
    params = [category_id, days]
    if latitude is not None and longitude is not None:
        sql += " AND latitude BETWEEN %s AND %s AND longitude BETWEEN %s AND %s"
        params.extend([float(latitude) - radius, float(latitude) + radius,
                       float(longitude) - radius, float(longitude) + radius])
    sql += " ORDER BY created_at DESC LIMIT 50"
    try:
        candidates = query(sql, tuple(params))
    except DatabaseError:
        return []

    title_tokens = _tokens(title or "")
    matches = []
    for row in candidates:
        ratio = SequenceMatcher(None, (title or "").lower(), (row["title"] or "").lower()).ratio()
        other_tokens = _tokens(row["title"] or "")
        overlap = len(title_tokens & other_tokens)
        if ratio >= 0.45 or overlap >= 2:
            row["similarity"] = round(max(ratio, overlap / max(len(title_tokens), 1)), 2)
            matches.append(row)
    return sorted(matches, key=lambda row: row["similarity"], reverse=True)[:limit]
