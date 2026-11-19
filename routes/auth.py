"""Authentication routes: register, login, logout and password help."""

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import DatabaseError, execute, query
from utils.decorators import dashboard_url, generate_csrf_token, login_required
from utils.validators import safe_next_url, validate_login, validate_registration

auth = Blueprint("auth", __name__)


def _audit(user_id, action, entity_type, entity_id, details):
    try:
        execute(
            "INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, action, entity_type, entity_id, details, request.remote_addr),
        )
    except DatabaseError:
        pass


@auth.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(dashboard_url(session.get("role", "citizen")))

    form = {
        "full_name": "",
        "email": "",
        "phone": "",
    }
    if request.method == "POST":
        form = {
            "full_name": (request.form.get("full_name") or "").strip(),
            "email": (request.form.get("email") or "").strip().lower(),
            "phone": (request.form.get("phone") or "").strip(),
        }
        errors = validate_registration(request.form)
        if not errors:
            try:
                existing = query("SELECT id FROM users WHERE email = %s", (form["email"],), one=True)
            except DatabaseError:
                existing = None
                errors.append("Registration is temporarily unavailable. Please try again.")
            if existing:
                errors.append("An account with this email already exists.")

        if not errors:
            password_hash = generate_password_hash(request.form["password"], method="pbkdf2:sha256:260000")
            try:
                result = execute(
                    "INSERT INTO users (full_name, email, phone, password_hash, role) "
                    "VALUES (%s, %s, %s, %s, 'citizen')",
                    (form["full_name"], form["email"], form["phone"] or None, password_hash),
                )
            except DatabaseError:
                errors.append("Registration is temporarily unavailable. Please try again.")
            else:
                user_id = result["lastrowid"]
                _audit(user_id, "register", "user", user_id, "New citizen account created")
                session.clear()
                session["user_id"] = user_id
                session["role"] = "citizen"
                session["name"] = form["full_name"]
                session["email"] = form["email"]
                session.permanent = False
                flash("Welcome to CivicFix! Your account has been created.", "success")
                return redirect(url_for("citizen.dashboard"))

        for error in errors:
            flash(error, "danger")

    return render_template("register.html", form=form)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(dashboard_url(session.get("role", "citizen")))

    email = (request.form.get("email") or "").strip().lower()
    remember = request.form.get("remember") in {"1", "on", "true"}
    if request.method == "POST":
        errors = validate_login(request.form)
        if not errors:
            try:
                user = query(
                    "SELECT id, full_name, email, role, password_hash, is_active "
                    "FROM users WHERE email = %s",
                    (email,),
                    one=True,
                )
            except DatabaseError:
                user = None
                errors.append("Login is temporarily unavailable. Please try again.")
            if user and not check_password_hash(user["password_hash"], request.form.get("password", "")):
                user = None
            if not user:
                errors.append("Invalid email or password.")
            elif not user["is_active"]:
                errors.append("This account is inactive. Please contact an administrator.")

        if not errors and user:
            session.clear()
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["name"] = user["full_name"]
            session["email"] = user["email"]
            session.permanent = remember
            generate_csrf_token()
            try:
                execute("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = %s", (user["id"],))
                _audit(user["id"], "login", "user", user["id"], "Successful sign in")
            except DatabaseError:
                pass
            flash(f"Welcome back, {user['full_name'].split()[0]}!", "success")
            target = safe_next_url(
                request.form.get("next"), dashboard_url(user["role"])
            )
            return redirect(target)

        for error in errors:
            flash(error, "danger")

    return render_template(
        "login.html",
        email=email,
        remember=remember,
        next_url=request.args.get("next", ""),
    )


@auth.route("/logout", methods=["POST"])
@login_required
def logout():
    user_id = session.get("user_id")
    _audit(user_id, "logout", "user", user_id, "Signed out")
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("main.index"))


@auth.route("/forgot-password")
def forgot_password():
    return render_template("forgot_password.html")
