"""Login, logout and the small security helpers around them."""
import secrets
from urllib.parse import urlparse

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from .db import get_db

auth_bp = Blueprint("auth", __name__)


def get_csrf_token():
    """Create a one-per-session token used to protect forms from CSRF attacks."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


def validate_csrf():
    """Reject a form unless it sends the token stored in this session."""
    expected = session.get("csrf_token")
    submitted = request.form.get("csrf_token", "")
    if not expected or not submitted or not secrets.compare_digest(submitted, expected):
        abort(400, description="Invalid CSRF token")


@auth_bp.app_context_processor
def inject_template_globals():
    """Make the CSRF token and current user available in every template."""
    user = None
    if session.get("user_id"):
        user = {
            "id": session["user_id"],
            "username": session.get("username"),
            "role": session.get("role"),
        }
    return {"csrf_token": get_csrf_token, "current_user": user}


def safe_next(target):
    """Only allow redirects to a path on our own site."""
    if not target:
        return url_for("main.dashboard")
    parsed = urlparse(target)
    if parsed.netloc or not parsed.path.startswith("/"):
        return url_for("main.dashboard")
    return target


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        validate_csrf()

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        connection = get_db()
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT u.id, u.username, u.password_hash, u.role,
                          u.employee_id, u.is_active
                   FROM users u
                   WHERE u.username = %s""",
                (username,),
            )
            user = cursor.fetchone()

        valid = (
            user is not None
            and user["is_active"]
            and check_password_hash(user["password_hash"], password)
        )
        if not valid:
            flash("Invalid username or password.", "danger")
            return render_template("login.html"), 401

        # Regenerate the session so a session ID cannot be reused.
        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        session["employee_id"] = user["employee_id"]
        session["csrf_token"] = secrets.token_hex(16)

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET last_login_at = NOW() WHERE id = %s", (user["id"],)
            )
            connection.commit()

        flash(f"Welcome, {user['username']}!", "success")
        return redirect(safe_next(request.form.get("next")))

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    validate_csrf()

    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
