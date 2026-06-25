"""
app/__init__.py — creates the Flask application and registers blueprints.

Does NOT start the worker; that responsibility belongs to run.py.
"""

import os

from flask import Flask

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.secret_key = os.environ.get("APP_SECRET", "change-me")

# Attach routes directly to the app so url_for() names stay unqualified
# (matching the existing templates which use e.g. url_for('logout'))
from app.routes import init_routes  # noqa: E402
init_routes(app)

# Expose the worker singleton for callers that do `from app import worker`
from app.worker import worker  # noqa: E402, F401
