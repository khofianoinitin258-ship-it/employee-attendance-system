"""First routes: a home page and a health check."""
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, jsonify, render_template, session

from .attendance import get_settings, get_today_record, now_naive
from .db import get_db
from .decorators import admin_required, login_required

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    """Simple landing page to confirm the app renders templates."""
    return render_template("index.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    """Role-aware landing page after login."""
    db = get_db()
    context = {}

    if session.get("role") == "admin":
        today = now_naive().date()
        with db.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM employees WHERE is_active = 1")
            context["total_active"] = cursor.fetchone()["total"]
            cursor.execute(
                """SELECT
                     COALESCE(SUM(status = 'present'), 0) AS present,
                     COALESCE(SUM(status = 'late'), 0) AS late
                   FROM attendance_records ar
                   JOIN employees e ON e.id = ar.employee_id
                   WHERE ar.work_date = %s AND e.is_active = 1""",
                (today,),
            )
            counts = cursor.fetchone()
        context["present"] = counts["present"]
        context["late"] = counts["late"]
        context["absent"] = context["total_active"] - counts["present"] - counts["late"]
    else:
        employee_id = session.get("employee_id")
        if employee_id:
            today = now_naive().date()
            context["record"] = get_today_record(db, employee_id, today)
            context["settings"] = get_settings(db)

    return render_template("dashboard.html", **context)


@main_bp.route("/profile")
@login_required
def profile():
    """Show the logged-in user's personal profile."""
    db = get_db()
    employee = None
    employee_id = session.get("employee_id")
    if employee_id:
        with db.cursor() as cursor:
            cursor.execute(
                """SELECT e.*, d.name AS department_name
                   FROM employees e
                   LEFT JOIN departments d ON d.id = e.department_id
                   WHERE e.id = %s""",
                (employee_id,),
            )
            employee = cursor.fetchone()
    return render_template("profile.html", employee=employee)


@main_bp.route("/admin/ping")
@admin_required
def admin_ping():
    """Tiny admin-only endpoint used to test role protection."""
    return jsonify(ok=True)


@main_bp.route("/health")
def health():
    """Check that Flask and the database are both working."""
    connection = get_db()
    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION() AS version, DATABASE() AS database_name")
        database_info = cursor.fetchone()

    now = datetime.now(ZoneInfo(current_app.config["TIMEZONE"]))
    return jsonify(
        status="ok",
        database=database_info,
        server_time=now.isoformat(),
        timezone=current_app.config["TIMEZONE"],
    )
