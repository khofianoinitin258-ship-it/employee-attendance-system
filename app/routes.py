"""First routes: a home page and a health check."""
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, jsonify, render_template

from .db import get_db

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    """Simple landing page to confirm the app renders templates."""
    return render_template("index.html")


@main_bp.route("/health")
def health():
    """Check that Flask and the database are both working."""
    connection = get_db()
    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION() AS version, DATABASE() AS database_name")
        database_info = cursor.fetchone()

    now = datetime.now(ZoneInfo(current_app.config["TIMEZONE"]))
    return jsonify(
        status="ok",
        database=database_info,
        server_time=now.isoformat(),
        timezone=current_app.config["TIMEZONE"],
    )
