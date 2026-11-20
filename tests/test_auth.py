"""Tests for login, logout and role-based access."""
import unittest
from uuid import uuid4

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.context = self.app.app_context()
        self.context.push()
        self.db = get_db()
        self.cursor = self.db.cursor()

        suffix = uuid4().hex[:8]
        self.cursor.execute(
            "INSERT INTO departments (name) VALUES (%s)", (f"Auth Dept {suffix}",)
        )
        self.department_id = self.cursor.lastrowid
        self.cursor.execute(
            """INSERT INTO employees
               (employee_code, first_name, last_name, email, department_id)
               VALUES (%s, %s, %s, %s, %s)""",
            (
                f"AUTH{suffix}",
                "Login",
                "Tester",
                f"auth{suffix}@example.com",
                self.department_id,
            ),
        )
        self.employee_id = self.cursor.lastrowid
        self.username = f"tester{suffix}"
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

    def login_as(self, username, password, **extra):
        with self.client.session_transaction() as session:
            session["csrf_token"] = "test-csrf-token"
        data = {"csrf_token": "test-csrf-token", "username": username, "password": password}
        data.update(extra)
        return self.client.post("/login", data=data)

    def test_login_page_loads(self):
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Log in", response.data)

    def test_admin_can_log_in(self):
        response = self.login_as("admin", "admin123")
        self.assertEqual(response.status_code, 302)
        dashboard = self.client.get("/dashboard")
        self.assertIn(b"Dashboard", dashboard.data)
        with self.client.session_transaction() as session:
            self.assertEqual(session["role"], "admin")

    def test_wrong_password_is_rejected(self):
        response = self.login_as("admin", "wrong-password")
        self.assertEqual(response.status_code, 401)
        self.assertIn(b"Invalid username or password", response.data)

    def test_dashboard_requires_login(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_employee_cannot_access_admin_route(self):
        self.login_as(self.username, "employee123")
        response = self.client.get("/admin/ping")
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Access denied", response.data)

    def test_admin_can_access_admin_route(self):
        self.login_as("admin", "admin123")
        response = self.client.get("/admin/ping")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True})

    def test_logout_clears_session(self):
        self.login_as("admin", "admin123")
        with self.client.session_transaction() as session:
            token = session["csrf_token"]
        response = self.client.post("/logout", data={"csrf_token": token})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/dashboard").status_code, 302)

    def test_login_rejects_missing_csrf_token(self):
        response = self.client.post(
            "/login", data={"username": "admin", "password": "admin123"}
        )
        self.assertEqual(response.status_code, 400)

    def test_external_next_redirect_is_ignored(self):
        response = self.login_as(
            "admin", "admin123", next="https://example.com/steal"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/dashboard", response.headers["Location"])


if __name__ == "__main__":
    unittest.main()
