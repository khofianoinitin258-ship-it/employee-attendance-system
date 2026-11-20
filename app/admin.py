"""Administrator-only pages for managing employees and departments."""
import re

import pymysql
from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.security import generate_password_hash

from .auth import validate_csrf
from .db import get_db
from .decorators import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def department_options(db):
    with db.cursor() as cursor:
        cursor.execute("SELECT id, name FROM departments ORDER BY name")
        return cursor.fetchall()


def validate_employee_form(form, db, employee_id=None):
    """Return (errors, cleaned_values) for an employee form."""
    errors = {}
    values = {
        "employee_code": form.get("employee_code", "").strip(),
        "first_name": form.get("first_name", "").strip(),
        "last_name": form.get("last_name", "").strip(),
        "email": form.get("email", "").strip().lower(),
        "phone": form.get("phone", "").strip(),
        "job_title": form.get("job_title", "").strip(),
        "department_id": form.get("department_id") or None,
        "date_hired": form.get("date_hired") or None,
        "is_active": 1 if form.get("is_active") else 0,
    }

    for field, label in (
        ("employee_code", "Employee code"),
        ("first_name", "First name"),
        ("last_name", "Last name"),
        ("email", "Email"),
    ):
        if not values[field]:
            errors[field] = f"{label} is required."

    if values["email"] and not EMAIL_PATTERN.match(values["email"]):
        errors["email"] = "Enter a valid email address."

    with db.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM employees WHERE employee_code = %s", (values["employee_code"],)
        )
        row = cursor.fetchone()
        if row and row["id"] != employee_id:
            errors["employee_code"] = "That employee code is already used."

        cursor.execute("SELECT id FROM employees WHERE email = %s", (values["email"],))
        row = cursor.fetchone()
        if row and row["id"] != employee_id:
            errors["email"] = "That email is already used."

        if values["department_id"]:
            cursor.execute(
                "SELECT id FROM departments WHERE id = %s", (values["department_id"],)
            )
            if cursor.fetchone() is None:
                errors["department_id"] = "Select a valid department."

    return errors, values


@admin_bp.route("/employees")
@admin_required
def employees():
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            """SELECT e.*, d.name AS department_name
               FROM employees e
               LEFT JOIN departments d ON d.id = e.department_id
               ORDER BY e.id DESC"""
        )
        records = cursor.fetchall()
    return render_template("admin/employees.html", employees=records)


@admin_bp.route("/employees/create", methods=["GET", "POST"])
@admin_required
def create_employee():
    db = get_db()
    departments = department_options(db)

    if request.method == "POST":
        validate_csrf()
        errors, values = validate_employee_form(request.form, db)
        create_account = request.form.get("create_account") == "on"
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if create_account:
            if not username:
                errors["username"] = "Username is required when creating a login."
            if len(password) < 8:
                errors["password"] = "Password must be at least 8 characters."
            with db.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                if cursor.fetchone():
                    errors["username"] = "That username is already taken."

        if errors:
            return (
                render_template(
                    "admin/employee_form.html",
                    employee=None,
                    departments=departments,
                    errors=errors,
                    form=request.form,
                ),
                400,
            )

        try:
            with db.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO employees
                       (employee_code, first_name, last_name, email, phone,
                        job_title, department_id, date_hired, is_active)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        values["employee_code"],
                        values["first_name"],
                        values["last_name"],
                        values["email"],
                        values["phone"] or None,
                        values["job_title"] or None,
                        values["department_id"],
                        values["date_hired"],
                        values["is_active"],
                    ),
                )
                employee_id = cursor.lastrowid
                if create_account:
                    cursor.execute(
                        """INSERT INTO users
                           (username, password_hash, role, employee_id, is_active)
                           VALUES (%s, %s, 'employee', %s, %s)""",
                        (
                            username,
                            generate_password_hash(password),
                            employee_id,
                            values["is_active"],
                        ),
                    )
            db.commit()
        except pymysql.err.IntegrityError:
            db.rollback()
            flash("Employee code or email already exists.", "danger")
            return (
                render_template(
                    "admin/employee_form.html",
                    employee=None,
                    departments=departments,
                    errors={},
                    form=request.form,
                ),
                400,
            )

        flash("Employee created successfully.", "success")
        return redirect(url_for("admin.employees"))

    return render_template(
        "admin/employee_form.html",
        employee=None,
        departments=departments,
        errors={},
        form={},
    )


@admin_bp.route("/employees/<int:employee_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_employee(employee_id):
    db = get_db()
    departments = department_options(db)
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM employees WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
    if employee is None:
        abort(404)

    if request.method == "POST":
        validate_csrf()
        errors, values = validate_employee_form(request.form, db, employee_id)
        if errors:
            return (
                render_template(
                    "admin/employee_form.html",
                    employee=employee,
                    departments=departments,
                    errors=errors,
                    form=request.form,
                ),
                400,
            )

        try:
            with db.cursor() as cursor:
                cursor.execute(
                    """UPDATE employees SET
                         employee_code = %s, first_name = %s, last_name = %s,
                         email = %s, phone = %s, job_title = %s,
                         department_id = %s, date_hired = %s, is_active = %s
                       WHERE id = %s""",
                    (
                        values["employee_code"],
                        values["first_name"],
                        values["last_name"],
                        values["email"],
                        values["phone"] or None,
                        values["job_title"] or None,
                        values["department_id"],
                        values["date_hired"],
                        values["is_active"],
                        employee_id,
                    ),
                )
                cursor.execute(
                    "UPDATE users SET is_active = %s WHERE employee_id = %s",
                    (values["is_active"], employee_id),
                )
            db.commit()
        except pymysql.err.IntegrityError:
            db.rollback()
            flash("Employee code or email already exists.", "danger")
            return redirect(url_for("admin.edit_employee", employee_id=employee_id))

        flash("Employee updated successfully.", "success")
        return redirect(url_for("admin.employees"))

    return render_template(
        "admin/employee_form.html",
        employee=employee,
        departments=departments,
        errors={},
        form=request.form or {},
    )


@admin_bp.route("/employees/<int:employee_id>/toggle", methods=["POST"])
@admin_required
def toggle_employee(employee_id):
    validate_csrf()
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT first_name, is_active FROM employees WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        if employee is None:
            abort(404)
        new_status = 0 if employee["is_active"] else 1
        cursor.execute(
            "UPDATE employees SET is_active = %s WHERE id = %s", (new_status, employee_id)
        )
        cursor.execute(
            "UPDATE users SET is_active = %s WHERE employee_id = %s",
            (new_status, employee_id),
        )
    db.commit()
    action = "deactivated" if new_status == 0 else "reactivated"
    flash(f"{employee['first_name']} was {action}.", "info")
    return redirect(url_for("admin.employees"))


@admin_bp.route("/departments")
@admin_required
def departments():
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            """SELECT d.*, COUNT(e.id) AS employee_count
               FROM departments d
               LEFT JOIN employees e ON e.department_id = d.id
               GROUP BY d.id
               ORDER BY d.name"""
        )
        records = cursor.fetchall()
    return render_template("admin/departments.html", departments=records)


@admin_bp.route("/departments/create", methods=["POST"])
@admin_required
def create_department():
    validate_csrf()
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    if not name:
        flash("Department name is required.", "danger")
        return redirect(url_for("admin.departments"))

    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO departments (name, description) VALUES (%s, %s)",
                (name, description or None),
            )
        db.commit()
        flash("Department created.", "success")
    except pymysql.err.IntegrityError:
        db.rollback()
        flash("A department with that name already exists.", "danger")
    return redirect(url_for("admin.departments"))


@admin_bp.route("/departments/<int:department_id>/rename", methods=["POST"])
@admin_required
def rename_department(department_id):
    validate_csrf()
    name = request.form.get("name", "").strip()
    if not name:
        flash("Department name is required.", "danger")
        return redirect(url_for("admin.departments"))

    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                "UPDATE departments SET name = %s WHERE id = %s", (name, department_id)
            )
        db.commit()
        flash("Department renamed.", "success")
    except pymysql.err.IntegrityError:
        db.rollback()
        flash("A department with that name already exists.", "danger")
    return redirect(url_for("admin.departments"))


@admin_bp.route("/departments/<int:department_id>/delete", methods=["POST"])
@admin_required
def delete_department(department_id):
    validate_csrf()
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS total FROM employees WHERE department_id = %s",
            (department_id,),
        )
        if cursor.fetchone()["total"] > 0:
            flash("Move or deactivate the employees in this department first.", "warning")
            return redirect(url_for("admin.departments"))
        cursor.execute("DELETE FROM departments WHERE id = %s", (department_id,))
    db.commit()
    flash("Department deleted.", "success")
    return redirect(url_for("admin.departments"))
