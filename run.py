"""
run.py — application entry point.

Starts the background worker then runs the Flask dev server.
For production, use a WSGI server:
    gunicorn "app:app"
"""

import os

from app import app
from app.worker import worker

if __name__ == "__main__":
    worker.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5100")))
