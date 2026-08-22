"""Flask app factory for AI Session Hub web UI."""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def create_app():
    from flask import Flask
    from flask_cors import CORS
    from config import BASE_DIR

    app = Flask(
        __name__,
        static_folder=os.path.join(BASE_DIR, "web", "static"),
        static_url_path="/static",
    )
    CORS(app)

    from web.api import register_routes
    register_routes(app)

    @app.route("/")
    def serve_index():
        from flask import send_from_directory
        return send_from_directory(os.path.join(BASE_DIR, "web", "static"), "index.html")

    @app.route("/<path:path>")
    def serve_spa(path):
        from flask import send_from_directory
        static_dir = os.path.join(BASE_DIR, "web", "static")
        if os.path.isfile(os.path.join(static_dir, path)):
            return send_from_directory(static_dir, path)
        return send_from_directory(static_dir, "index.html")

    return app
