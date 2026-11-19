"""CivicFix Flask application entry point."""

import os

from flask import Flask, jsonify, redirect, render_template, url_for

from config import Config
from database.db import DatabaseError, health_check, initialize_database
from services.notification_service import unread_count
from routes.analytics import analytics
from routes.admin import admin
from routes.auth import auth
from routes.citizen import citizen
from routes.complaints import complaints
from routes.main import main
from routes.notifications import notifications
from routes.staff import staff
from utils.decorators import (
    csrf_validate,
    current_user,
    generate_csrf_token,
)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    for blueprint in (main, auth, citizen, complaints, admin, staff, notifications, analytics):
        app.register_blueprint(blueprint)

    app.jinja_env.globals.update(
        csrf_token=generate_csrf_token,
        current_user=current_user,
        app_name="CivicFix",
        app_tagline="Report. Track. Resolve.",
    )

    @app.before_request
    def _before_request():
        csrf_validate()

    @app.after_request
    def _security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.route("/profile")
    def profile_shortcut():
        return redirect(url_for("citizen.profile"))

    @app.route("/api/notifications/unread-count")
    def unread_notifications_api():
        user = current_user()
        return jsonify({"count": unread_count(user["id"]) if user else 0})

    @app.route("/health")
    def health():
        available = health_check()
        return jsonify({"status": "ok" if available else "database unavailable"}), (
            200 if available else 503
        )

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/error.html", code=403,
                               title="Access denied",
                               message="You do not have permission to view this page."), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/error.html", code=404,
                               title="Page not found",
                               message="The page you requested does not exist."), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("errors/error.html", code=500,
                               title="Something went wrong",
                               message="Please try again in a few moments."), 500

    @app.errorhandler(DatabaseError)
    def database_error(error):
        app.logger.error("Database error: %s", error)
        return render_template(
            "errors/error.html",
            code=503,
            title="Service temporarily unavailable",
            message="We could not reach the database. Please try again shortly.",
        ), 503

    @app.cli.command("init-db")
    def init_db_command():
        initialize_database()
        print("CivicFix database initialized.")

    @app.cli.command("reset-db")
    def reset_db_command():
        initialize_database(force=True)
        print("CivicFix database rebuilt from database/civicfix.sql.")

    @app.context_processor
    def _inject_template_globals():
        return {"session_user": current_user()}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=app.config["DEBUG"])
