"""Application factory.

create_app() builds and returns a Flask app. Keeping this in a function makes
testing and future growth much easier.
"""
from flask import Flask

from config import Config

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

    return app
