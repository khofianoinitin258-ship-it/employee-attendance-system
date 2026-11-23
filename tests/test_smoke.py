"""Basic checks that the app still starts and can reach the database."""
import unittest

from app import create_app


class SmokeTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_home_page_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Essuman", response.data)

    def test_health_check_reaches_database(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["database"]["database_name"], "attendance_db")
        self.assertEqual(data["timezone"], "Africa/Accra")


if __name__ == "__main__":
    unittest.main()
