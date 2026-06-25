"""
app/routes.py — Flask routes and login_required decorator.

Registered as a Blueprint named 'main' in app/__init__.py.

Import order: ... → app.worker → app.routes → app/__init__.py
"""

import json
from functools import wraps
from typing import Any

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from app.config import (
    ADMIN_PASSWORD,
    SAMPLE_REVIEW_EVENT,
    SAVED_PAYLOADS_PATH,
    form_to_config,
    load_config,
    load_saved_payload,
    save_config,
)
from app.logging import LIVE_LOGS, add_log
from app.worker import worker

main = Blueprint("main", __name__)


# ─── Auth ──────────────────────────────────────────────────────────────────

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("main.login"))
        return func(*args, **kwargs)

    return wrapper


# ─── Auth routes ───────────────────────────────────────────────────────────

@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["authenticated"] = True
            return redirect(url_for("main.index"))
        return render_template("login.html", error="Invalid password"), 401
    return render_template("login.html", error="")


@main.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


# ─── Main UI ───────────────────────────────────────────────────────────────

@main.route("/", methods=["GET", "POST"])
@login_required
def index():
    config = load_config()
    if request.method == "POST":
        config = form_to_config(config, request.form)
        save_config(config)
        worker.restart()
        add_log("info", "Configuration saved and listener restarted")
        return redirect(url_for("main.index"))
    return render_template(
        "index.html",
        config=config,
        status=worker.status(),
        logs=list(LIVE_LOGS),
        sample_payload=json.dumps(load_saved_payload() or SAMPLE_REVIEW_EVENT, indent=2),
    )


# ─── Health & status ───────────────────────────────────────────────────────

@main.route("/health")
def health():
    return jsonify(worker.status())


# ─── API routes ────────────────────────────────────────────────────────────

@main.route("/api/logs")
@login_required
def logs():
    return jsonify({"logs": list(LIVE_LOGS), "status": worker.status()})


@main.route("/api/test", methods=["POST"])
@login_required
def test_notification():
    envelope = request.get_json(force=True)

    if isinstance(envelope, dict) and "topic" in envelope and "payload" in envelope:
        if envelope.get("topic") != "reviews":
            return jsonify({"ok": True, "message": "Ignored non-review topic", "status": worker.status()})
        raw_payload = envelope.get("payload")
        try:
            payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
        except json.JSONDecodeError as exc:
            return jsonify({"error": f"WebSocket payload decode failed: {exc}"}), 400
    else:
        payload = envelope

    if not isinstance(payload, dict):
        return jsonify({"error": "Payload must resolve to a valid JSON object"}), 400

    add_log("debug", "WebSocket review event received (via Test API)", payload=payload)
    worker.handle_payload(payload, is_test=True)
    return jsonify({"ok": True, "status": worker.status()})


@main.route("/api/test-fcm", methods=["POST"])
@login_required
def test_fcm():
    raw_websocket_message = {
        "topic": "reviews",
        "payload": (
            '{"type": "new", "before": {"id": "1782340990.237592-gu88rp", "camera": "front_door",'
            ' "start_time": 1782340990.237592, "end_time": null, "severity": "alert",'
            ' "thumb_path": "/media/frigate/clips/review/thumb-front_door-1782340990.237592-gu88rp.webp",'
            ' "data": {"detections": ["1782340990.039527-44hvr0"], "objects": ["person"],'
            ' "verified_objects": [], "sub_labels": [], "zones": [], "audio": [],'
            ' "thumb_time": 1782340990.525862, "metadata": null}},'
            ' "after": {"id": "1782340990.237592-gu88rp", "camera": "front_door",'
            ' "start_time": 1782340990.237592, "end_time": null, "severity": "alert",'
            ' "thumb_path": "/media/frigate/clips/review/thumb-front_door-1782340990.237592-gu88rp.webp",'
            ' "data": {"detections": ["1782340990.039527-44hvr0"], "objects": ["person"],'
            ' "verified_objects": [], "sub_labels": [], "zones": [], "audio": [],'
            ' "thumb_time": 1782340990.525862, "metadata": null}}}'
        ),
    }

    inner_payload_string = raw_websocket_message.get("payload")
    try:
        payload = json.loads(inner_payload_string) if isinstance(inner_payload_string, str) else inner_payload_string
    except json.JSONDecodeError as exc:
        add_log("error", "Emulated WebSocket payload decode failed", error=str(exc))
        return jsonify({"error": f"JSON Decode Error: {exc}"}), 400

    add_log("info", "Emulating live WebSocket event pipeline from Web UI button", payload=payload)

    try:
        worker.handle_payload(payload, is_test=True)
    except Exception as exc:
        add_log("error", "Pipeline execution failed during emulation", error=str(exc))
        return jsonify({"error": str(exc)}), 500

    return jsonify({"ok": True, "sent": 1, "errors": [], "status": worker.status()})


@main.route("/api/saved-payload", methods=["GET"])
@login_required
def get_saved_payload():
    return jsonify(load_saved_payload())


@main.route("/api/saved-payload", methods=["POST"])
@login_required
def save_payload():
    payload = request.get_json(force=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "payload must be a JSON object"}), 400
    SAVED_PAYLOADS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SAVED_PAYLOADS_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return jsonify({"ok": True})
