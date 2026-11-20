"""Checks that the database rules we designed are actually enforced."""
import unittest
from datetime import date
from uuid import uuid4

import pymysql

from app import create_app
from app.db import get_db


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.context = self.app.app_context()
        self.context.push()
        self.db = get_db()
        self.cursor = self.db.cursor()

        suffix = uuid4().hex[:8]
        self.cursor.execute(
            "INSERT INTO departments (name) VALUES (%s)", (f"Test Dept {suffix}",)
        )
        self.department_id = self.cursor.lastrowid
        self.cursor.execute(
            """INSERT INTO employees
               (employee_code, first_name, last_name, email, department_id)
               VALUES (%s, %s, %s, %s, %s)""",
            (
                f"TEST{suffix}",
                "Test",
                "Employee",
                f"test{suffix}@example.com",
                self.department_id,
            ),
        )
        self.employee_id = self.cursor.lastrowid
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.cursor.execute("DELETE FROM employees WHERE id = %s", (self.employee_id,))
        self.cursor.execute("DELETE FROM departments WHERE id = %s", (self.department_id,))
        self.db.commit()
        self.cursor.close()
        self.context.pop()

    def test_duplicate_clock_in_is_blocked(self):
        values = (self.employee_id, date.today(), "2026-11-20 08:05:00")
        self.cursor.execute(
            """INSERT INTO attendance_records
               (employee_id, work_date, clock_in, status)
               VALUES (%s, %s, %s, 'present')""",
            values,
        )
        self.db.commit()

        with self.assertRaises(pymysql.err.IntegrityError):
            self.cursor.execute(
                """INSERT INTO attendance_records
                   (employee_id, work_date, clock_in, status)
                   VALUES (%s, %s, %s, 'present')""",
                values,
            )
            self.db.commit()
        self.db.rollback()

    def test_default_settings_exist(self):
        self.cursor.execute(
            """SELECT TIME_FORMAT(work_start_time, '%H:%i:%s') AS work_start_time,
                      TIME_FORMAT(work_end_time, '%H:%i:%s') AS work_end_time
               FROM system_settings WHERE id = 1"""
        )
        settings = self.cursor.fetchone()
        self.assertEqual(settings["work_start_time"], "08:00:00")
        self.assertEqual(settings["work_end_time"], "17:00:00")


if __name__ == "__main__":
    unittest.main()
