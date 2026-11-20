"""Application configuration.

Values come from the .env file so we never hard-code passwords in Python code.
"""
import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Settings shared by the whole application."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 3306))
    DB_USER = os.getenv("DB_USER", "attendance_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "attendance_pass")
    DB_NAME = os.getenv("DB_NAME", "attendance_db")

    # All time calculations in this project use Ghana time.
    TIMEZONE = os.getenv("TIMEZONE", "Africa/Accra")
