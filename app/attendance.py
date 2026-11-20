"""Clock in/out logic and the employee attendance page."""
from datetime import datetime, time
from zoneinfo import ZoneInfo

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    session,
    url_for,
)

from .auth import validate_csrf
from .db import get_db
from .decorators import login_required

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")


def now_naive():
    """Current time in Africa/Accra, stored without timezone suffix.

    MySQL DATETIME columns have no timezone, so we keep everything consistent
    by using organisation-local time everywhere in the database.
    """
    timezone = ZoneInfo(current_app.config["TIMEZONE"])
    return datetime.now(timezone).replace(tzinfo=None)


def as_time(value):
    """Normalise a TIME value from MySQL into a datetime.time object.

    PyMySQL may return TIME columns as '8:00:00' strings instead of
    datetime.time objects, so we handle both forms.
    """
    if isinstance(value, time):
        return value
    text = str(value).strip()
    parts = text.split(":")
    if len(parts) >= 2:
        second = int(parts[2]) if len(parts) > 2 and parts[2] else 0
        return time(int(parts[0]), int(parts[1]), second)
    return time.fromisoformat(text)


def get_settings(db):
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM system_settings WHERE id = 1")
        return cursor.fetchone()


def get_today_record(db, employee_id, work_date):
    with db.cursor() as cursor:
        cursor.execute(
            """SELECT * FROM attendance_records
               WHERE employee_id = %s AND work_date = %s""",
            (employee_id, work_date),
        )
        return cursor.fetchone()


def clock_in(db, employee_id, settings, now):
    """Create today's record. Returns (success, message)."""
    record = get_today_record(db, employee_id, now.date())
    if record is not None:
        return False, "You have already clocked in today."

    start_time = as_time(settings["work_start_time"])
    status = "late" if now.time() > start_time else "present"

    with db.cursor() as cursor:
        cursor.execute(
            """INSERT INTO attendance_records
               (employee_id, work_date, clock_in, status)
               VALUES (%s, %s, %s, %s)""",
            (employee_id, now.date(), now, status),
        )
    db.commit()

    if status == "late":
        return True, f"You are clocked in, but marked late (work starts at {start_time})."
    return True, "Clocked in successfully."


def clock_out(db, employee_id, now):
    """Close today's record. Returns (success, message)."""
    record = get_today_record(db, employee_id, now.date())
    if record is None:
        return False, "You must clock in before clocking out."
    if record["clock_out"] is not None:
        return False, "You have already clocked out today."

    hours_worked = round((now - record["clock_in"]).total_seconds() / 3600, 2)
    with db.cursor() as cursor:
        cursor.execute(
            """UPDATE attendance_records
               SET clock_out = %s, hours_worked = %s
               WHERE id = %s AND clock_out IS NULL""",
            (now, hours_worked, record["id"]),
        )
    db.commit()
    return True, f"Clocked out. You worked {hours_worked} hours today."


def current_employee(db):
    """Return the employee linked to the logged-in user, if any."""
    employee_id = session.get("employee_id")
    if not employee_id:
        return None
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT id, first_name, last_name FROM employees WHERE id = %s",
            (employee_id,),
        )
        return cursor.fetchone()


@attendance_bp.route("/")
@login_required
def attendance_page():
    db = get_db()
    employee = current_employee(db)
    if employee is None:
        flash("Your account is not linked to an employee record.", "warning")
        return redirect(url_for("main.dashboard"))

    now = now_naive()
    record = get_today_record(db, employee["id"], now.date())
    settings = get_settings(db)

    with db.cursor() as cursor:
        cursor.execute(
            """SELECT work_date, clock_in, clock_out, status, hours_worked
               FROM attendance_records
               WHERE employee_id = %s
               ORDER BY work_date DESC
               LIMIT 10""",
            (employee["id"],),
        )
        history = cursor.fetchall()

    return render_template(
        "attendance.html",
        employee=employee,
        record=record,
        history=history,
        settings=settings,
        now=now,
    )


@attendance_bp.route("/clock-in", methods=["POST"])
@login_required
def clock_in_route():
    validate_csrf()
    db = get_db()
    employee = current_employee(db)
    if employee is None:
        flash("Your account is not linked to an employee record.", "warning")
        return redirect(url_for("main.dashboard"))

    success, message = clock_in(db, employee["id"], get_settings(db), now_naive())
    flash(message, "success" if success else "warning")
    return redirect(url_for("attendance.attendance_page"))


@attendance_bp.route("/clock-out", methods=["POST"])
@login_required
def clock_out_route():
    validate_csrf()
    db = get_db()
    employee = current_employee(db)
    if employee is None:
        flash("Your account is not linked to an employee record.", "warning")
        return redirect(url_for("main.dashboard"))

    success, message = clock_out(db, employee["id"], now_naive())
    flash(message, "success" if success else "warning")
    return redirect(url_for("attendance.attendance_page"))
