"""Application factory.

create_app() builds and returns a Flask app. Keeping this in a function makes
testing and future growth much easier.
"""
from flask import Flask, render_template

from config import Config

from .admin import admin_bp
from .attendance import attendance_bp
from .auth import auth_bp
from .db import init_app as init_db
from .routes import main_bp


def create_app():
    # Our templates/ and static/ folders live next to the app/ package,
    # so point Flask at them explicitly.
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(Config)

    init_db(app)
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(attendance_bp)

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("403.html"), 403

    return app
