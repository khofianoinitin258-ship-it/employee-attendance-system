"""Tests for clock in/out rules and the employee attendance page."""
import unittest
from datetime import date, datetime
from uuid import uuid4

from werkzeug.security import generate_password_hash

from app import create_app
from app.attendance import clock_in, clock_out, get_settings, get_today_record
from app.db import get_db


class AttendanceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.context = self.app.app_context()
        self.context.push()
        self.db = get_db()
        self.cursor = self.db.cursor()
        self.work_date = date(2026, 11, 20)

        suffix = uuid4().hex[:8]
        self.cursor.execute("INSERT INTO departments (name) VALUES (%s)", (f"Att Dept {suffix}",))
        self.department_id = self.cursor.lastrowid
        self.cursor.execute(
            """INSERT INTO employees
               (employee_code, first_name, last_name, email, department_id)
               VALUES (%s, %s, %s, %s, %s)""",
            (
                f"ATT{suffix}",
                "Clock",
                "Tester",
                f"clock{suffix}@example.com",
                self.department_id,
            ),
        )
        self.employee_id = self.cursor.lastrowid
        self.username = f"clock{suffix}"
        self.cursor.execute(
            """INSERT INTO users (username, password_hash, role, employee_id)
               VALUES (%s, %s, 'employee', %s)""",
            (self.username, generate_password_hash("employee123"), self.employee_id),
        )
        self.user_id = self.cursor.lastrowid
        self.db.commit()
        self.settings = get_settings(self.db)

    def tearDown(self):
        self.db.rollback()
        self.cursor.execute(
            "DELETE FROM attendance_records WHERE employee_id = %s", (self.employee_id,)
        )
        self.cursor.execute("DELETE FROM users WHERE id = %s", (self.user_id,))
        self.cursor.execute("DELETE FROM employees WHERE id = %s", (self.employee_id,))
        self.cursor.execute("DELETE FROM departments WHERE id = %s", (self.department_id,))
        self.db.commit()
        self.cursor.close()
        self.context.pop()

    def login_as_employee(self):
        with self.client.session_transaction() as session:
            session["csrf_token"] = "csrf"
        return self.client.post(
            "/login",
            data={
                "csrf_token": "csrf",
                "username": self.username,
                "password": "employee123",
            },
        )

    def post_with_csrf(self, url):
        with self.client.session_transaction() as session:
            token = session.get("csrf_token") or "csrf"
            session["csrf_token"] = token
        return self.client.post(url, data={"csrf_token": token})

    def test_clock_in_on_time_is_present(self):
        success, message = clock_in(
            self.db, self.employee_id, self.settings, datetime(2026, 11, 20, 8, 0)
        )
        self.assertTrue(success)
        record = get_today_record(self.db, self.employee_id, self.work_date)
        self.assertEqual(record["status"], "present")

    def test_clock_in_after_start_is_late(self):
        success, message = clock_in(
            self.db, self.employee_id, self.settings, datetime(2026, 11, 20, 8, 30)
        )
        self.assertTrue(success)
        self.assertIn("late", message)
        record = get_today_record(self.db, self.employee_id, self.work_date)
        self.assertEqual(record["status"], "late")

    def test_duplicate_clock_in_is_blocked(self):
        clock_in(self.db, self.employee_id, self.settings, datetime(2026, 11, 20, 8, 0))
        success, message = clock_in(
            self.db, self.employee_id, self.settings, datetime(2026, 11, 20, 8, 5)
        )
        self.assertFalse(success)
        self.assertIn("already clocked in", message)

    def test_clock_out_requires_clock_in(self):
        success, message = clock_out(
            self.db, self.employee_id, datetime(2026, 11, 20, 17, 0)
        )
        self.assertFalse(success)
        self.assertIn("must clock in", message)

    def test_working_hours_are_calculated(self):
        clock_in(self.db, self.employee_id, self.settings, datetime(2026, 11, 20, 8, 0))
        success, message = clock_out(
            self.db, self.employee_id, datetime(2026, 11, 20, 17, 0)
        )
        self.assertTrue(success)
        record = get_today_record(self.db, self.employee_id, self.work_date)
        self.assertEqual(float(record["hours_worked"]), 9.0)

    def test_employee_can_open_attendance_page_and_clock_in(self):
        self.login_as_employee()
        page = self.client.get("/attendance/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"My attendance", page.data)

        response = self.post_with_csrf("/attendance/clock-in")
        self.assertEqual(response.status_code, 302)
        page = self.client.get("/attendance/")
        self.assertIn(b"Clock out", page.data)

        response = self.post_with_csrf("/attendance/clock-out")
        self.assertEqual(response.status_code, 302)
        page = self.client.get("/attendance/")
        self.assertIn(b"Finished for today", page.data)

    def test_admin_without_employee_is_redirected(self):
        with self.client.session_transaction() as session:
            session["csrf_token"] = "csrf"
        self.client.post(
            "/login",
            data={"csrf_token": "csrf", "username": "admin", "password": "admin123"},
        )
        response = self.client.get("/attendance/")
        self.assertEqual(response.status_code, 302)


if __name__ == "__main__":
    unittest.main()
