"""Tests for admin employee and department management."""
import unittest
from uuid import uuid4

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db


class AdminTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.context = self.app.app_context()
        self.context.push()
        self.db = get_db()
        self.cursor = self.db.cursor()

        suffix = uuid4().hex[:8]
        self.cursor.execute(
            "INSERT INTO departments (name) VALUES (%s)", (f"Admin Dept {suffix}",)
        )
        self.department_id = self.cursor.lastrowid
        self.employee_code = f"EMP{suffix}"
        self.cursor.execute(
            """INSERT INTO employees
               (employee_code, first_name, last_name, email, department_id, is_active)
               VALUES (%s, %s, %s, %s, %s, 1)""",
            (
                self.employee_code,
                "Existing",
                "Employee",
                f"existing{suffix}@example.com",
                self.department_id,
            ),
        )
        self.employee_id = self.cursor.lastrowid
        self.username = f"emp{suffix}"
        self.cursor.execute(
            """INSERT INTO users (username, password_hash, role, employee_id)
               VALUES (%s, %s, 'employee', %s)""",
            (self.username, generate_password_hash("employee123"), self.employee_id),
        )
        self.user_id = self.cursor.lastrowid
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.cursor.execute("DELETE FROM users WHERE id = %s", (self.user_id,))
        self.cursor.execute("DELETE FROM employees WHERE id = %s", (self.employee_id,))
        self.cursor.execute("DELETE FROM departments WHERE id = %s", (self.department_id,))
        self.db.commit()
        self.cursor.close()
        self.context.pop()

    def login(self, username, password):
        with self.client.session_transaction() as session:
            session["csrf_token"] = "csrf"
        return self.client.post(
            "/login",
            data={"csrf_token": "csrf", "username": username, "password": password},
        )

    def post_as_admin(self, url, data):
        with self.client.session_transaction() as session:
            token = session.get("csrf_token") or "csrf"
            session["csrf_token"] = token
        data["csrf_token"] = token
        return self.client.post(url, data=data)

    def test_admin_can_view_employees(self):
        self.login("admin", "admin123")
        response = self.client.get("/admin/employees")
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.employee_code.encode(), response.data)

    def test_employee_cannot_view_employees(self):
        self.login(self.username, "employee123")
        self.assertEqual(self.client.get("/admin/employees").status_code, 403)

    def test_create_employee_with_login_account(self):
        self.login("admin", "admin123")
        suffix = uuid4().hex[:8]
        response = self.post_as_admin(
            "/admin/employees/create",
            {
                "employee_code": f"NEW{suffix}",
                "first_name": "New",
                "last_name": "Person",
                "email": f"new{suffix}@example.com",
                "department_id": str(self.department_id),
                "date_hired": "2026-11-20",
                "create_account": "on",
                "username": f"newuser{suffix}",
                "password": "securepass123",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.cursor.execute(
            "SELECT id FROM employees WHERE employee_code = %s", (f"NEW{suffix}",)
        )
        new_employee = self.cursor.fetchone()
        self.assertIsNotNone(new_employee)
        self.cursor.execute(
            "SELECT role FROM users WHERE employee_id = %s", (new_employee["id"],)
        )
        self.assertEqual(self.cursor.fetchone()["role"], "employee")

        self.cursor.execute("DELETE FROM users WHERE employee_id = %s", (new_employee["id"],))
        self.cursor.execute("DELETE FROM employees WHERE id = %s", (new_employee["id"],))
        self.db.commit()

    def test_duplicate_employee_code_is_rejected(self):
        self.login("admin", "admin123")
        response = self.post_as_admin(
            "/admin/employees/create",
            {
                "employee_code": self.employee_code,
                "first_name": "Duplicate",
                "last_name": "Person",
                "email": f"duplicate-{uuid4().hex[:8]}@example.com",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"already used", response.data)

    def test_edit_employee(self):
        self.login("admin", "admin123")
        response = self.post_as_admin(
            f"/admin/employees/{self.employee_id}/edit",
            {
                "employee_code": self.employee_code,
                "first_name": "Updated",
                "last_name": "Employee",
                "email": f"existing-{uuid4().hex[:8]}@example.com",
                "department_id": str(self.department_id),
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.cursor.execute(
            "SELECT first_name FROM employees WHERE id = %s", (self.employee_id,)
        )
        self.assertEqual(self.cursor.fetchone()["first_name"], "Updated")

    def test_deactivating_employee_disables_login(self):
        self.login("admin", "admin123")
        response = self.post_as_admin(
            f"/admin/employees/{self.employee_id}/toggle", {}
        )
        self.assertEqual(response.status_code, 302)
        self.cursor.execute(
            "SELECT is_active FROM employees WHERE id = %s", (self.employee_id,)
        )
        self.assertEqual(self.cursor.fetchone()["is_active"], 0)
        self.cursor.execute("SELECT is_active FROM users WHERE id = %s", (self.user_id,))
        self.assertEqual(self.cursor.fetchone()["is_active"], 0)

    def test_create_rename_and_delete_department(self):
        self.login("admin", "admin123")
        name = f"Dept {uuid4().hex[:8]}"
        self.post_as_admin("/admin/departments/create", {"name": name})
        self.cursor.execute("SELECT id FROM departments WHERE name = %s", (name,))
        department = self.cursor.fetchone()
        self.assertIsNotNone(department)

        new_name = f"Renamed {uuid4().hex[:8]}"
        self.post_as_admin(
            f"/admin/departments/{department['id']}/rename", {"name": new_name}
        )
        self.cursor.execute("SELECT name FROM departments WHERE id = %s", (department["id"],))
        self.assertEqual(self.cursor.fetchone()["name"], new_name)

        self.post_as_admin(f"/admin/departments/{department['id']}/delete", {})
        self.cursor.execute("SELECT id FROM departments WHERE id = %s", (department["id"],))
        self.assertIsNone(self.cursor.fetchone())

    def test_department_with_employees_cannot_be_deleted(self):
        self.login("admin", "admin123")
        self.post_as_admin(f"/admin/departments/{self.department_id}/delete", {})
        self.cursor.execute(
            "SELECT id FROM departments WHERE id = %s", (self.department_id,)
        )
        self.assertIsNotNone(self.cursor.fetchone())

    def test_csrf_required_on_create(self):
        self.login("admin", "admin123")
        response = self.client.post(
            "/admin/employees/create",
            data={"employee_code": "X", "first_name": "A", "last_name": "B", "email": "a@b.com"},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
