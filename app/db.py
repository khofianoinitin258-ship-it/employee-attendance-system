"""Database connection helpers.

PyMySQL lets Flask talk to MySQL/MariaDB using plain SQL.
We open one connection per request and close it automatically at the end.
"""
import pymysql
from flask import current_app, g


def get_db():
    """Return the database connection for the current request."""
    if "db" not in g:
        g.db = pymysql.connect(
            host=current_app.config["DB_HOST"],
            port=current_app.config["DB_PORT"],
            user=current_app.config["DB_USER"],
            password=current_app.config["DB_PASSWORD"],
            database=current_app.config["DB_NAME"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
    return g.db


def close_db(error=None):
    """Close the connection when the request finishes."""
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_app(app):
    """Attach database cleanup to the Flask application."""
    app.teardown_appcontext(close_db)
