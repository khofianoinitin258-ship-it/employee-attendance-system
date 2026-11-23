"""Tests for attendance reports and CSV export."""
import unittest
from datetime import datetime
from uuid import uuid4

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.context = self.app.app_context()
        self.context.push()
        self.db = get_db()
        self.cursor = self.db.cursor()

        suffix = uuid4().hex[:8]
        self.cursor.execute("INSERT INTO departments (name) VALUES (%s)", (f"Rep Dept {suffix}",))
        self.department_id = self.cursor.lastrowid
        self.cursor.execute(
            """INSERT INTO employees
               (employee_code, first_name, last_name, email, department_id)
               VALUES (%s, %s, %s, %s, %s)""",
            (f"REP{suffix}", "Report", "Worker", f"rep{suffix}@example.com", self.department_id),
        )
        self.employee_id = self.cursor.lastrowid
        self.username = f"rep{suffix}"
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
        self.cursor.close()
        self.context.pop()

    def login(self, username, password):
        with self.client.session_transaction() as session:
            session["csrf_token"] = "csrf"
        return self.client.post(
            "/login",
            data={"csrf_token": "csrf", "username": username, "password": password},
        )

    def seed_attendance(self):
        rows = [
            ("2026-11-16", "2026-11-16 08:10:00", "2026-11-16 17:00:00", "late", 8.83),
            ("2026-11-17", "2026-11-17 08:00:00", "2026-11-17 17:00:00", "present", 9.0),
        ]
        for work_date, clock_in, clock_out, status, hours in rows:
            self.cursor.execute(
                """INSERT INTO attendance_records
                   (employee_id, work_date, clock_in, clock_out, status, hours_worked)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (self.employee_id, work_date, clock_in, clock_out, status, hours),
            )
        self.db.commit()

    def test_employee_cannot_view_reports(self):
        self.login(self.username, "employee123")
        self.assertEqual(self.client.get("/admin/reports/").status_code, 403)

    def test_daily_report_shows_record(self):
        self.seed_attendance()
        self.login("admin", "admin123")
        response = self.client.get("/admin/reports/?type=daily&date=2026-11-17")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Report Worker", response.data)
        self.assertIn(b"Present", response.data)

    def test_weekly_report_includes_week(self):
        self.seed_attendance()
        self.login("admin", "admin123")
        response = self.client.get("/admin/reports/?type=weekly&date=2026-11-17")
        self.assertIn(b"2026-11-16", response.data)
        self.assertIn(b"2026-11-17", response.data)

    def test_late_report_filters(self):
        self.seed_attendance()
        self.login("admin", "admin123")
        response = self.client.get("/admin/reports/?type=late&date=2026-11-16")
        self.assertIn(b"Late", response.data)
        self.assertNotIn(b"2026-11-17", response.data)

    def test_absence_report_shows_unclocked_employee(self):
        self.login("admin", "admin123")
        response = self.client.get("/admin/reports/?type=absence&date=2026-11-23")
        self.assertIn(b"Report Worker", response.data)
        self.assertIn(b"Absent", response.data)

    def test_individual_report(self):
        self.seed_attendance()
        self.login("admin", "admin123")
        response = self.client.get(
            f"/admin/reports/?type=individual&date=2026-11-17&employee_id={self.employee_id}"
        )
        self.assertIn(b"Report Worker", response.data)
        self.assertNotIn(b"No records for this report", response.data)

    def test_csv_export(self):
        self.seed_attendance()
        self.login("admin", "admin123")
        response = self.client.get("/admin/reports/?type=weekly&date=2026-11-17&export=csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)
        self.assertIn(b"Employee Name", response.data)
        self.assertIn(b"Report Worker", response.data)


if __name__ == "__main__":
    unittest.main()
