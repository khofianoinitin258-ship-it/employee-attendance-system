"""Tests for profile and role-aware dashboard."""
import unittest
from uuid import uuid4

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.context = self.app.app_context()
        self.context.push()
        self.db = get_db()
        self.cursor = self.db.cursor()

        suffix = uuid4().hex[:8]
        self.cursor.execute("INSERT INTO departments (name) VALUES (%s)", (f"Profile Dept {suffix}",))
        self.department_id = self.cursor.lastrowid
        self.cursor.execute(
            """INSERT INTO employees
               (employee_code, first_name, last_name, email, department_id, job_title)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                f"PRO{suffix}",
                "Profile",
                "Person",
                f"profile{suffix}@example.com",
                self.department_id,
                "Tester",
            ),
        )
        self.employee_id = self.cursor.lastrowid
        self.username = f"profile{suffix}"
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

    def test_employee_can_view_profile(self):
        self.login(self.username, "employee123")
        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Profile Person", response.data)
        self.assertIn(b"Tester", response.data)

    def test_employee_dashboard_shows_attendance_actions(self):
        self.login(self.username, "employee123")
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Go to attendance", response.data)

    def test_admin_dashboard_shows_quick_actions(self):
        self.login("admin", "admin123")
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Admin quick actions", response.data)


if __name__ == "__main__":
    unittest.main()
