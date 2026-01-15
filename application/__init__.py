from config import Config
from flask import Flask
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy(session_options={'expire_on_commit': False})


def create_app():
    from . import models, routes

    app = Flask(__name__)
    app.config.from_object(Config)
    app.register_blueprint(routes.bp)

    db.init_app(app)

    # TODO: move this to a separate create_db module that is only run for setup.
    #  And/or look into flask-migrate in order to handle schema changes.
    with app.app_context():
        db.create_all()

    return app
