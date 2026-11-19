# CivicFix

CivicFix is a full-stack civic issue reporting platform where citizens report neighbourhood problems, administrators review and route them, and department staff update progress through resolution. It uses Flask, MySQL, server-rendered HTML, vanilla JavaScript, Chart.js and Leaflet.

## Features

- Citizen registration, login, password reset flow and session-based role access.
- Complaint reporting with category, severity, location picker, map coordinates and validated photo uploads.
- Explainable rule-based priority scoring and rule-based duplicate suggestions.
- Unique tracking numbers, public tracking, complaint timelines, support counts and citizen reopen requests.
- Admin dashboards with charts and full complaint management: search, filters, status, priority, department/staff assignment and rejection reasons.
- Department, staff and citizen administration plus a complete audit trail.
- Staff queues with progress notes, field photos, resolution evidence, status changes and admin escalation.
- Public city issue map with category/status/priority filters and status or priority colour modes.
- Public analytics dashboard and role-aware in-app notifications with unread filtering.
- CSRF protection, permission checks, hashed passwords, parameterized SQL and safe image validation.

## Tech stack

- Frontend: HTML5, CSS, Bootstrap Icons, vanilla JavaScript, Chart.js, Leaflet + OpenStreetMap.
- Backend: Flask blueprints, REST-style JSON endpoints, Jinja templates, Werkzeug security helpers.
- Database: MySQL 8 with `mysql-connector-python`.
- Configuration: `python-dotenv` and local `.env`.

## Prerequisites

- Python 3.10 or newer.
- MySQL 8.0 running locally.
- A MySQL account with permission to create databases and tables.

## Setup

```powershell
cd C:\Users\Admin\OneDrive\Desktop\CivicFix
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set `DB_PASSWORD` to your MySQL password. Other defaults work for a local MySQL instance on port `3306`.

Create the schema and seed demo data:

```powershell
python -m flask --app app init-db
```

Run the application:

```powershell
python -m flask --app app run
```

Open `http://127.0.0.1:5000`.

If port 5000 is busy:

```powershell
python -m flask --app app run --port 5001
```

To rebuild the database from `database/civicfix.sql`:

```powershell
python -m flask --app app reset-db
```

## Demo accounts

All demo accounts use password `Demo@123`.

| Role | Email |
| --- | --- |
| Administrator | `admin@civicfix.demo` |
| Citizen | `priya@example.demo` |
| Citizen | `rohan@example.demo` |
| Staff | `suresh@staff.civicfix.demo` |
| Staff | `meera@staff.civicfix.demo` |

## Tests

```powershell
python -m pytest tests -q
```

The suite covers authentication, RBAC, dashboards, complaint submission, uploads, tracking, duplicate detection, admin management, staff workflow, map/analytics pages, notification filtering and a full citizen-to-resolution lifecycle.

## Project layout

```text
CivicFix/
├── app.py                    Flask app factory, blueprints, security handlers
├── config.py                 Environment-backed configuration
├── requirements.txt
├── .env.example
├── database/
│   ├── civicfix.sql          Schema + demo data
│   └── db.py                 Connection/query helpers and initialization
├── routes/
│   ├── main.py               Landing page + city map
│   ├── auth.py               Login/register/forgot password
│   ├── citizen.py            Citizen dashboard + profile
│   ├── complaints.py         Reporting, details, tracking, support
│   ├── admin.py              Admin management workspace
│   ├── staff.py              Staff task workspace
│   ├── notifications.py      Notification routes
│   └── analytics.py          Public analytics dashboard
├── services/
│   ├── complaint_service.py  Complaint queries and workflow operations
│   ├── notification_service.py
│   ├── priority_service.py   Explainable priority scoring
│   └── duplicate_service.py  Duplicate suggestions
├── utils/
│   ├── decorators.py         CSRF, login and RBAC decorators
│   ├── validators.py         Input validation helpers
│   └── upload_utils.py       Image validation and safe storage
├── templates/                Jinja templates
├── static/
│   ├── css/                  Design system, forms, dashboard, responsive rules
│   ├── js/                   Maps, charts, admin and report helpers
│   └── uploads/complaints/   User-generated images (ignored by Git)
└── tests/                    Pytest suite by phase + end-to-end test
```

## Main routes

- `/` landing page
- `/report`, `/track`, `/map`, `/analytics`
- `/admin/dashboard`, `/admin/complaints`, `/admin/departments`, `/admin/staff`, `/admin/citizens`, `/admin/audit`, `/admin/settings`
- `/staff/dashboard`, `/staff/tasks`
- `/citizen/dashboard`, `/complaints/my`, `/complaints/supported`
- `/notifications`, `/profile`

## Security notes

- All state-changing HTML forms include CSRF tokens; JSON endpoints use the `X-CSRF-Token` header.
- Passwords are hashed with Werkzeug PBKDF2 and never stored in plain text.
- Access is enforced server-side by session role checks on every protected route.
- SQL queries use parameterized statements.
- Uploads are restricted by extension, MIME type, magic bytes and size limit.
- `.env` is ignored by Git. Uploaded complaint images are also ignored.

## Troubleshooting

- If `pip.exe` or `flask.exe` is blocked by Windows Application Control, use `python -m pip` and `python -m flask` instead. You can also start the app with `python app.py`.
- The "development server" warning is normal for local use. Set `FLASK_DEBUG=0` in `.env` to hide the debugger PIN; use a production WSGI server only when deploying publicly.
- If database pages show `503 Service temporarily unavailable`, verify MySQL is running and the credentials in `.env` are correct.
- If `python -m flask --app app init-db` reports a missing table, run `python -m flask --app app reset-db` to rebuild from the SQL file.
- If a map does not display, confirm internet access to the OpenStreetMap tiles and Leaflet CDN.
