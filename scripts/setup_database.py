"""Create the tables and insert the first administrator account.

Run once with:  .venv\\Scripts\\python.exe scripts\\setup_database.py
It is safe to run again - existing rows are left alone.
"""
import os
import sys
from pathlib import Path

import pymysql
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))  # allow importing config.py from the project root

from config import Config

SCHEMA_FILE = BASE_DIR / "sql" / "schema.sql"


def connect(use_database=True):
    options = dict(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )
    if use_database:
        options["database"] = Config.DB_NAME
    return pymysql.connect(**options)


def create_database():
    connection = connect(use_database=False)
    with connection.cursor() as cursor:
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    connection.close()
    print(f"Database '{Config.DB_NAME}' is ready.")


def create_tables():
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    connection = connect()
    with connection.cursor() as cursor:
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)
    connection.close()
    print("Tables created/verified.")


def seed_defaults():
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

    connection = connect()
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT IGNORE INTO departments (name, description) VALUES (%s, %s)",
            ("General", "Default department"),
        )
        cursor.execute(
            "INSERT IGNORE INTO system_settings "
            "(id, work_start_time, work_end_time, timezone) VALUES (1, %s, %s, %s)",
            ("08:00:00", "17:00:00", "Africa/Accra"),
        )

        cursor.execute("SELECT id FROM users WHERE username = %s", (admin_username,))
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, is_active) "
                "VALUES (%s, %s, 'admin', 1)",
                (admin_username, generate_password_hash(admin_password)),
            )
            print(f"Admin user '{admin_username}' created.")
        else:
            print(f"Admin user '{admin_username}' already exists.")
    connection.close()


if __name__ == "__main__":
    create_database()
    create_tables()
    seed_defaults()
    print("Database setup finished.")
