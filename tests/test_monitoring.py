"""Tests for the admin overview and working-hours settings."""
import unittest
from datetime import datetime
from uuid import uuid4

from werkzeug.security import generate_password_hash

from app import create_app
from app.attendance import clock_in, now_naive
from app.db import get_db


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.context = self.app.app_context()
        self.context.push()
        self.db = get_db()
        self.cursor = self.db.cursor()

        suffix = uuid4().hex[:8]
        self.cursor.execute("INSERT INTO departments (name) VALUES (%s)", (f"Mon Dept {suffix}",))
        self.department_id = self.cursor.lastrowid
        self.cursor.execute(
            """INSERT INTO employees
               (employee_code, first_name, last_name, email, department_id)
               VALUES (%s, %s, %s, %s, %s)""",
            (f"MON{suffix}", "Monitor", "Tester", f"mon{suffix}@example.com", self.department_id),
        )
        self.employee_id = self.cursor.lastrowid
        self.username = f"mon{suffix}"
        self.cursor.execute(
            """INSERT INTO users (username, password_hash, role, employee_id)
               VALUES (%s, %s, 'employee', %s)""",
            (self.username, generate_password_hash("employee123"), self.employee_id),
        )
        self.user_id = self.cursor.lastrowid
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.cursor.execute("DELETE FROM attendance_records WHERE employee_id = %s", (self.employee_id,))
        self.cursor.execute("DELETE FROM users WHERE id = %s", (self.user_id,))
        self.cursor.execute("DELETE FROM employees WHERE id = %s", (self.employee_id,))
        self.cursor.execute("DELETE FROM departments WHERE id = %s", (self.department_id,))
        self.db.commit()

        self.cursor.execute(
            "UPDATE system_settings SET work_start_time='08:00:00', work_end_time='17:00:00', timezone='Africa/Accra' WHERE id=1"
        )
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

    def test_admin_can_view_overview(self):
        self.login("admin", "admin123")
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Today's attendance", response.data)

    def test_employee_cannot_view_overview(self):
        self.login(self.username, "employee123")
        self.assertEqual(self.client.get("/admin/").status_code, 403)

    def test_overview_counts_todays_records(self):
        today = now_naive().date()
        self.cursor.execute(
            """INSERT INTO attendance_records
               (employee_id, work_date, clock_in, status)
               VALUES (%s, %s, %s, 'late')""",
            (self.employee_id, today, datetime(2026, 11, 20, 8, 30)),
        )
        self.db.commit()

        self.login("admin", "admin123")
        page = self.client.get("/admin/")
        self.assertIn(b"Late", page.data)
        self.assertIn(b"Monitor Tester", page.data)

    def test_admin_can_change_working_hours(self):
        self.login("admin", "admin123")
        response = self.post_as_admin(
            "/admin/settings",
            {
                "work_start_time": "09:00",
                "work_end_time": "17:30",
                "timezone": "Africa/Accra",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.cursor.execute("SELECT * FROM system_settings WHERE id = 1")
        row = self.cursor.fetchone()
        self.assertEqual(str(row["work_start_time"]), "9:00:00")
        self.assertEqual(str(row["work_end_time"]), "17:30:00")

        # An 08:30 clock-in is now on time because work starts at 09:00.
        success, _ = clock_in(
            self.db, self.employee_id, row, datetime(2026, 11, 20, 8, 30)
        )
        self.assertTrue(success)
        self.cursor.execute(
            "SELECT status FROM attendance_records WHERE employee_id = %s", (self.employee_id,)
        )
        self.assertEqual(self.cursor.fetchone()["status"], "present")

    def test_invalid_time_order_is_rejected(self):
        self.login("admin", "admin123")
        response = self.post_as_admin(
            "/admin/settings",
            {
                "work_start_time": "17:00",
                "work_end_time": "09:00",
                "timezone": "Africa/Accra",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"before end time", response.data)

    def test_unknown_timezone_is_rejected(self):
        self.login("admin", "admin123")
        response = self.post_as_admin(
            "/admin/settings",
            {
                "work_start_time": "08:00",
                "work_end_time": "17:00",
                "timezone": "Mars/Olympus",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"not recognised", response.data)

    def test_settings_require_csrf_token(self):
        self.login("admin", "admin123")
        response = self.client.post(
            "/admin/settings",
            data={"work_start_time": "08:00", "work_end_time": "17:00", "timezone": "UTC"},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
