"""Attendance report queries and CSV exports."""
import csv
import io
from datetime import date, timedelta

from flask import Blueprint, Response, render_template, request

from .attendance import now_naive
from .db import get_db
from .decorators import admin_required

reports_bp = Blueprint("reports", __name__, url_prefix="/admin/reports")

REPORT_TYPES = {
    "daily": "Daily attendance",
    "weekly": "Weekly attendance",
    "monthly": "Monthly attendance",
    "late": "Late arrivals",
    "absence": "Absences / not clocked in",
    "individual": "Individual employee",
}


def parse_date(value, default=None):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return default


def report_period(report_type, selected_date):
    """Return (start, end, title) for the chosen report."""
    if report_type == "weekly":
        start = selected_date - timedelta(days=selected_date.weekday())
        end = start + timedelta(days=6)
        title = f"Weekly report ({start} to {end})"
    elif report_type == "monthly":
        start = selected_date.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = next_month - timedelta(days=1)
        title = f"Monthly report ({start.strftime('%B %Y')})"
    else:
        start = end = selected_date
        title = f"Daily report ({selected_date})"
    return start, end, title


def build_rows(db, report_type, start, end, employee_id=None):
    """Return rows for a report. None means absent / no clock-in on that date."""
    if report_type == "individual":
        if employee_id is None:
            return []
        with db.cursor() as cursor:
            cursor.execute(
                """SELECT ar.work_date,
                          e.employee_code,
                          CONCAT(e.first_name, ' ', e.last_name) AS full_name,
                          d.name AS department_name,
                          ar.status, ar.clock_in, ar.clock_out, ar.hours_worked
                   FROM attendance_records ar
                   JOIN employees e ON e.id = ar.employee_id
                   LEFT JOIN departments d ON d.id = e.department_id
                   WHERE ar.employee_id = %s
                     AND ar.work_date BETWEEN %s AND %s
                   ORDER BY ar.work_date DESC""",
                (employee_id, start, end),
            )
            return cursor.fetchall()

    with db.cursor() as cursor:
        cursor.execute(
            """SELECT e.id AS employee_id,
                      ar.work_date,
                      e.employee_code,
                      CONCAT(e.first_name, ' ', e.last_name) AS full_name,
                      d.name AS department_name,
                      ar.status, ar.clock_in, ar.clock_out, ar.hours_worked
               FROM employees e
               LEFT JOIN departments d ON d.id = e.department_id
               LEFT JOIN attendance_records ar
                    ON ar.employee_id = e.id
                   AND ar.work_date BETWEEN %s AND %s
               WHERE e.is_active = 1
               ORDER BY ar.work_date DESC, e.last_name, e.first_name""",
            (start, end),
        )
        rows = cursor.fetchall()

    if report_type == "absence":
        rows = [row for row in rows if row["status"] is None]
    elif report_type == "late":
        rows = [row for row in rows if row["status"] == "late"]
    elif report_type == "daily":
        # For a single day, fill rows that have no date with the selected day.
        for row in rows:
            if row["work_date"] is None:
                row["work_date"] = start
    return rows


def rows_to_csv(rows, report_type):
    """Create a UTF-8 CSV download with a BOM so Excel opens it cleanly."""
    output = io.StringIO()
    output.write("\ufeff")  # BOM helps Excel detect UTF-8
    writer = csv.writer(output)
    writer.writerow([
        "Date",
        "Employee Code",
        "Employee Name",
        "Department",
        "Status",
        "Clock In",
        "Clock Out",
        "Hours Worked",
    ])
    for row in rows:
        status = row["status"] or "absent"
        writer.writerow([
            row["work_date"] or "",
            row["employee_code"],
            row["full_name"],
            row["department_name"] or "",
            status,
            row["clock_in"].strftime("%H:%M") if row["clock_in"] else "",
            row["clock_out"].strftime("%H:%M") if row["clock_out"] else "",
            row["hours_worked"] if row["hours_worked"] is not None else "",
        ])

    filename = f"{report_type}-attendance-report.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@reports_bp.route("/")
@admin_required
def index():
    db = get_db()
    today = now_naive().date()

    report_type = request.args.get("type", "daily")
    if report_type not in REPORT_TYPES:
        report_type = "daily"

    selected_date = parse_date(request.args.get("date"), today)
    employee_id = request.args.get("employee_id", type=int)
    start, end, title = report_period(report_type, selected_date)

    with db.cursor() as cursor:
        cursor.execute(
            """SELECT id, employee_code,
                      CONCAT(first_name, ' ', last_name) AS full_name
               FROM employees
               WHERE is_active = 1
               ORDER BY last_name, first_name"""
        )
        employees = cursor.fetchall()

    rows = build_rows(db, report_type, start, end, employee_id)

    if request.args.get("export") == "csv":
        return rows_to_csv(rows, report_type)

    return render_template(
        "admin/reports.html",
        rows=rows,
        report_types=REPORT_TYPES,
        report_type=report_type,
        selected_date=selected_date,
        start=start,
        end=end,
        title=title,
        employees=employees,
        employee_id=employee_id,
    )
