"""
app/__init__.py — creates the Flask application and registers blueprints.

Does NOT start the worker; that responsibility belongs to run.py.
"""

import os

from flask import Flask

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.secret_key = os.environ.get("APP_SECRET", "change-me")

# Register routes blueprint — imported after app is created to avoid circularity
from app.routes import main  # noqa: E402
app.register_blueprint(main)

# Expose the worker singleton for callers that do `from app import worker`
from app.worker import worker  # noqa: E402, F401
