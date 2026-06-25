"""
app/config.py — configuration constants, DEFAULT_CONFIG, and load/save helpers.

Import order: app.logging → app.utils → app.config
"""

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.logging import add_log
from app.utils import bool_value, csv_list, deep_merge, number_value

# ─── Paths & env ──────────────────────────────────────────────────────────

CONFIG_PATH = Path(os.environ.get("FRIGATE_NOTIFY_CONFIG", "/data/config.json"))
SAVED_PAYLOADS_PATH = CONFIG_PATH.parent / "saved_payloads.json"
LOG_DIR = CONFIG_PATH.parent / "logs"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
THIRD_PARTY_RELAY_URL = ""

# ─── Sample event ─────────────────────────────────────────────────────────

SAMPLE_REVIEW_EVENT: dict[str, Any] = {
    "type": "new",
    "before": {
        "id": "1782340990.237592-gu88rp",
        "camera": "front_door",
        "start_time": 1782340990.237592,
        "end_time": None,
        "severity": "alert",
        "thumb_path": "/media/frigate/clips/review/thumb-front_door-1782340990.237592-gu88rp.webp",
        "data": {
            "detections": ["1782340990.039527-44hvr0"],
            "objects": ["person"],
            "verified_objects": [],
            "sub_labels": [],
            "zones": [],
            "audio": [],
            "thumb_time": 1782340990.525862,
            "metadata": None,
        },
    },
    "after": {
        "id": "1782340990.237592-gu88rp",
        "camera": "front_door",
        "start_time": 1782340990.237592,
        "end_time": None,
        "severity": "alert",
        "thumb_path": "/media/frigate/clips/review/thumb-front_door-1782340990.237592-gu88rp.webp",
        "data": {
            "detections": ["1782340990.039527-44hvr0"],
            "objects": ["person"],
            "verified_objects": [],
            "sub_labels": [],
            "zones": [],
            "audio": [],
            "thumb_time": 1782340990.525862,
            "metadata": None,
        },
    },
}

# ─── Default config ───────────────────────────────────────────────────────

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "connection": {
        "type": "mqtt",
    },
    "mqtt": {
        "host": "mqtt",
        "port": 1883,
        "username": "",
        "password": "",
        "topic": "frigate/reviews",
        "client_id": "frigate-notify",
    },
    "websocket": {
        "base_url": "ws://frigate:5000",
        "path": "/ws",
        "extra_headers": "",
        "ping_interval": 20,
        "ping_timeout": 10,
        "reconnect_min_seconds": 2,
        "reconnect_max_seconds": 60,
    },
    "notifications": {
        "enabled": True,
        "delivery_method": "fcm",
        "tokens": [],
        "fcm_api_url": THIRD_PARTY_RELAY_URL,
        "base_url": "http://frigate:5000",
        "title": "{{ label }} detected - {{ camera_name }}",
        "message": "A {{ label }} was detected on the {{ camera_name }} camera.",
        "sub_label_message": "",
        "subtitle": "",
        "expanded_thumbnail": "photo",
        "attachment": "{{ base_url }}/api/events/{{ event_id }}/thumbnail.jpg",
        "attachment_2": "{{ base_url }}/api/events/{{ event_id }}/thumbnail.jpg",
        "video": "",
        "final_update": False,
        "final_delay": 5,
        "alert_once": False,
        "color": "#03a9f4",
        "group": "{{ camera }}-frigate-notification",
        "channel": "Default",
        "sticky": False,
        "critical": False,
        "android_auto": False,
        "click_action": "frigate://review/{{ review_id }}",
        "buttons": [
            {"title": "View Snapshot", "url": "{{ attachment }}"},
            {"title": "View Clip", "url": "{{ clip }}"},
            {"title": "Open Frigate", "url": "{{ base_url }}"},
        ],
    },
    "firebase": {
        "service_account_json": "",
    },
    "filters": {
        "cameras": [],
        "review_severity": ["alert", "detection"],
        "zones_enabled": False,
        "zones": [],
        "zone_multi": False,
        "zone_order_enforced": False,
        "labels": [],
        "disable_hours": [],
        "custom_filter": "true",
    },
    "timers": {"cooldown": 30, "timeout": 2, "silence_timer": 0, "loiter_timer": 0, "initial_delay": 0},
    "telegram": {"enabled": False, "bot_token": "", "chat_id": "", "base_url": ""},
    "debug": {"enabled": False, "redacted": True},
}


# ─── Config I/O ───────────────────────────────────────────────────────────

def normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    notifications = config.get("notifications") or {}
    notifications.pop("icon", None)
    notifications.pop("client_id", None)
    for key in ("attachment", "attachment_2"):
        value = notifications.get(key)
        if isinstance(value, str) and "/api/frigate" in value and "/notifications/" in value:
            notifications[key] = DEFAULT_CONFIG["notifications"][key]
    if (notifications.get("delivery_method") or "fcm").lower() not in {"fcm", "relay"}:
        notifications["delivery_method"] = "fcm"
    # Migrate plain-string tokens to {name, token} pairs
    raw_tokens = notifications.get("tokens") or []
    migrated: list[dict[str, str]] = []
    for entry in raw_tokens:
        if isinstance(entry, str):
            migrated.append({"name": "", "token": entry})
        elif isinstance(entry, dict) and "token" in entry:
            migrated.append({"name": str(entry.get("name") or ""), "token": str(entry["token"])})
    notifications["tokens"] = migrated
    # Migrate camelCase clickAction to snake_case click_action
    if "clickAction" in notifications and "click_action" not in notifications:
        notifications["click_action"] = notifications.pop("clickAction")
    elif "clickAction" in notifications:
        notifications.pop("clickAction")
    config["notifications"] = notifications

    connection = config.get("connection") or {}
    if (connection.get("type") or "mqtt").lower() not in {"mqtt", "websocket"}:
        connection["type"] = "mqtt"
    config["connection"] = connection
    return config


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        add_log("info", "Created default configuration", path=str(CONFIG_PATH))
        return deepcopy(DEFAULT_CONFIG)
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return normalize_config(deep_merge(DEFAULT_CONFIG, json.load(handle)))


def save_config(config: dict[str, Any]) -> None:
    config = normalize_config(config)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
    add_log("info", "Configuration saved", path=str(CONFIG_PATH))


def load_saved_payload() -> dict[str, Any]:
    if not SAVED_PAYLOADS_PATH.exists():
        return {}
    with SAVED_PAYLOADS_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def form_to_config(config: dict[str, Any], form: dict[str, str]) -> dict[str, Any]:
    updated = deepcopy(config)
    list_fields = {"filters.cameras", "filters.review_severity", "filters.labels", "filters.zones", "filters.disable_hours"}
    json_fields = {"notifications.buttons", "notifications.tokens"}
    bool_fields = {
        "enabled",
        "notifications.enabled",
        "notifications.final_update",
        "notifications.alert_once",
        "notifications.critical",
        "notifications.sticky",
        "notifications.android_auto",
        "filters.zones_enabled",
        "filters.zone_multi",
        "filters.zone_order_enforced",
        "telegram.enabled",
    }
    int_fields = {
        "mqtt.port",
        "notifications.final_delay",
        "timers.cooldown",
        "timers.timeout",
        "timers.silence_timer",
        "timers.loiter_timer",
        "timers.initial_delay",
        "websocket.ping_interval",
        "websocket.ping_timeout",
        "websocket.reconnect_min_seconds",
        "websocket.reconnect_max_seconds",
    }
    for dotted, value in form.items():
        target = updated
        parts = dotted.split(".")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        key = parts[-1]
        if dotted in list_fields:
            parsed: Any = csv_list(value)
            if dotted == "filters.disable_hours":
                parsed = [number_value(item) for item in parsed]
        elif dotted in json_fields:
            try:
                candidate = json.loads(value) if (value or "").strip() else []
                parsed = candidate if isinstance(candidate, list) else target.get(key, [])
            except json.JSONDecodeError as exc:
                add_log("error", "Failed to parse JSON from form; keeping previous value", field=dotted, error=str(exc))
                parsed = target.get(key, [])
        elif dotted in bool_fields:
            parsed = bool_value(value)
        elif dotted in int_fields:
            parsed = number_value(value)
        else:
            parsed = value
        target[key] = parsed
    return updated
