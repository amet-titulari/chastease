from flask import Flask

from .api.routes import api_bp
from .config import Config


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    return app
