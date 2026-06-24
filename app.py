import json
import os
import re
import threading
import time
from collections import deque
from copy import deepcopy
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any

import google.auth.transport.requests
import requests
import websocket
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from google.oauth2 import service_account
from jinja2 import Environment
from paho.mqtt import client as mqtt


CONFIG_PATH = Path(os.environ.get("FRIGATE_AUTOMATION_CONFIG", "/data/config.json"))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
LIVE_LOGS: deque[dict[str, Any]] = deque(maxlen=500)

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
THIRD_PARTY_RELAY_URL = "https://ayra.eu.org/project/frigate/fcm"


DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "connection": {
        # Which upstream connection feeds review events into this server's
        # own built-in relay: "mqtt" or "websocket". Mutually exclusive.
        "type": "mqtt",
    },
    "mqtt": {
        "host": "mqtt",
        "port": 1883,
        "username": "",
        "password": "",
        "topic": "frigate/reviews",
        "client_id": "frigate-native-automation",
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
        # "fcm" = this server sends straight to your own Firebase project (the
        #         built-in private relay, default and recommended).
        # "relay" = forward to a third-party relay service instead (optional,
        #           off by default; this is what the original project used).
        "delivery_method": "fcm",
        "tokens": [],
        "fcm_api_url": THIRD_PARTY_RELAY_URL,
        "base_url": "http://frigate:5000",
        "title": "{{ label }} detected - {{ camera_name }}",
        "message": "A {{ label }} was detected on the {{ camera_name }} camera.",
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
        "buttons": [
            {"title": "View Snapshot", "url": "{{ attachment }}"},
            {"title": "View Clip", "url": "{{ clip }}"},
            {"title": "Open Frigate", "url": "{{ base_url }}"},
        ],
    },
    "firebase": {
        # Paste the full service account JSON for your own Firebase project.
        # Used to send pushes directly via the FCM HTTP v1 API.
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


app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET", "change-me")


template_env = Environment(autoescape=False)
template_env.filters["timestamp_custom"] = lambda value, fmt: datetime.fromtimestamp(float(value)).strftime(fmt)
template_env.globals["iif"] = lambda condition, true_value, false_value="": true_value if condition else false_value


def add_log(level: str, message: str, **fields: Any) -> None:
    LIVE_LOGS.appendleft(
        {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "message": message,
            "fields": fields,
        },
    )


def compact_json(value: Any, limit: int = 1200) -> str:
    text = json.dumps(value, default=str, separators=(",", ":"))
    return text if len(text) <= limit else f"{text[:limit]}..."


def unique_text(items: list[Any]) -> list[str]:
    values: list[str] = []
    for item in items:
        if isinstance(item, dict):
            item = item.get("label") or item.get("name") or item.get("id")
        text = str(item or "").strip()
        if text and text != "null" and text not in values:
            values.append(text)
    return values


def display_label(items: list[str]) -> str:
    return ", ".join(item.replace("_", " ") for item in items)


def detected_labels(
    objects: list[str],
    verified_objects: list[str],
    sub_labels: list[str],
    raw_label: str,
) -> list[str]:
    labels = objects or verified_objects or unique_text([raw_label])
    if sub_labels and "person-verified" in labels:
        labels = [item for item in labels if item != "person-verified"]
        for sub_label in sub_labels:
            if sub_label not in labels:
                labels.insert(0, sub_label)
    if not labels and sub_labels:
        labels = sub_labels
    return labels


def deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        add_log("info", "Created default configuration", path=str(CONFIG_PATH))
        return deepcopy(DEFAULT_CONFIG)
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return normalize_config(deep_merge(DEFAULT_CONFIG, json.load(handle)))


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
    config["notifications"] = notifications

    connection = config.get("connection") or {}
    if (connection.get("type") or "mqtt").lower() not in {"mqtt", "websocket"}:
        connection["type"] = "mqtt"
    config["connection"] = connection
    return config


def save_config(config: dict[str, Any]) -> None:
    config = normalize_config(config)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
    add_log("info", "Configuration saved", path=str(CONFIG_PATH))


def csv_list(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,\n]", value or "") if item.strip()]


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}


def number_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_ws_url(base_url: str, path: str) -> str:
    base_url = (base_url or "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("WebSocket base URL is not configured")
    if not re.match(r"^wss?://", base_url, re.IGNORECASE):
        base_url = f"ws://{base_url}"
    path = (path or "/ws").strip()
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base_url}{path}"


def parse_header_lines(raw: str) -> list[str]:
    headers = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key:
            headers.append(f"{key}: {value}")
    return headers


def event_context(payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    after = payload.get("after") or {}
    before = payload.get("before") or {}
    data = after.get("data") or {}
    review_id = after.get("id") or payload.get("id") or payload.get("review_id") or ""
    camera = after.get("camera") or payload.get("camera") or ""
    objects = unique_text(data.get("objects") or data.get("attributes") or [])
    verified_objects = unique_text(data.get("verified_objects") or [])
    sub_labels = unique_text(data.get("sub_labels") or [])
    raw_label = after.get("label") or payload.get("label") or ""
    object_labels = detected_labels(objects, verified_objects, sub_labels, raw_label)
    label = display_label(object_labels) or "event"
    sub_label = display_label(sub_labels)
    detections = data.get("detections") or []
    zones = data.get("zones") or []
    base_url = config["notifications"]["base_url"].rstrip("/")
    first_detection = detections[0] if detections else None
    if isinstance(first_detection, dict):
        first_detection = first_detection.get("id")
    event_id = after.get("event_id") or first_detection or after.get("id") or review_id
    start_time = after.get("start_time") or time.time()
    end_time = after.get("end_time") or time.time()
    context = {
        "event": payload,
        "after": after,
        "before": before,
        "type": payload.get("type", "new"),
        "id": review_id,
        "event_id": event_id,
        "review_id": review_id,
        "camera": camera,
        "camera_name": camera.replace("_", " ").title(),
        "label": label,
        "raw_label": raw_label or label,
        "sub_label": sub_label,
        "objects": objects,
        "verified_objects": verified_objects,
        "sub_labels": sub_labels,
        "object_labels": object_labels,
        "detections": detections,
        "after_zones": zones,
        "before_zones": (before.get("data") or {}).get("zones") or [],
        "severity": after.get("severity") or data.get("max_severity") or "detection",
        "base_url": base_url,
        "clip": f"{base_url}/api/events/{event_id}/clip.mp4",
        "snapshot": f"{base_url}/api/events/{event_id}/snapshot.jpg",
        "thumbnail": f"{base_url}/api/events/{event_id}/thumbnail.jpg",
        "preview": f"{base_url}/api/{camera}/start/{int(float(start_time))}/end/{int(float(end_time))}/preview.gif",
        "stream": f"{base_url}/api/{camera}",
        "now": datetime.now,
    }
    add_log(
        "debug",
        "Event context built",
        review_id=review_id,
        event_id=event_id,
        camera=camera,
        type=context["type"],
        label=label,
        objects=objects,
        zones=zones,
        severity=context["severity"],
    )
    return context


def render_value(value: Any, context: dict[str, Any]) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value)
    return template_env.from_string(str(value)).render(**context).strip()


def zones_satisfied(config: dict[str, Any], current_zones: list[str]) -> bool:
    filters = config["filters"]
    required = filters.get("zones") or []
    if not filters.get("zones_enabled"):
        return True
    if not required:
        return bool(current_zones)
    if filters.get("zone_multi"):
        if not all(zone in current_zones for zone in required):
            return False
        if filters.get("zone_order_enforced"):
            intersection = [zone for zone in current_zones if zone in required]
            return intersection == required
        return True
    return any(zone in current_zones for zone in required)


def custom_filter_satisfied(config: dict[str, Any], context: dict[str, Any]) -> bool:
    raw = (config["filters"].get("custom_filter") or "true").strip()
    if raw.lower() in {"", "true", "1", "yes"}:
        return True
    if raw.lower() in {"false", "0", "no"}:
        return False
    return bool_value(render_value(raw, context))


# ---------------------------------------------------------------------------
# Firebase (built-in private relay) — sends directly to YOUR Firebase project
# using the FCM HTTP v1 API. No third-party server is involved in this path.
# ---------------------------------------------------------------------------

_firebase_lock = threading.Lock()
_firebase_cache: dict[str, Any] = {"raw": None, "credentials": None, "project_id": None}


def get_firebase_credentials(service_account_json: str) -> tuple[service_account.Credentials, str]:
    if not (service_account_json or "").strip():
        raise RuntimeError("Firebase service account JSON is not configured")
    with _firebase_lock:
        if _firebase_cache["raw"] != service_account_json:
            try:
                info = json.loads(service_account_json)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Firebase service account JSON is invalid: {exc}") from exc
            project_id = info.get("project_id")
            if not project_id:
                raise RuntimeError("Firebase service account JSON is missing project_id")
            credentials = service_account.Credentials.from_service_account_info(info, scopes=[FCM_SCOPE])
            _firebase_cache.update(raw=service_account_json, credentials=credentials, project_id=project_id)
        return _firebase_cache["credentials"], _firebase_cache["project_id"]


def send_fcm_v1(service_account_json: str, token: str, payload: dict[str, str]) -> requests.Response:
    credentials, project_id = get_firebase_credentials(service_account_json)
    with _firebase_lock:
        if not credentials.valid:
            credentials.refresh(google.auth.transport.requests.Request())
        access_token = credentials.token
    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; UTF-8",
        },
        json={"message": {"token": token, "data": payload, "android": {"priority": "high"}}},
        timeout=15,
    )
    response.raise_for_status()
    return response


def post_relay_payload(relay_url: str, token: str, payload: dict[str, str]) -> requests.Response:
    response = requests.post(
        relay_url,
        headers={"Content-Type": "application/json"},
        json={
            **payload,
            "token": token,
            "id": payload.get("id", ""),
            "title": payload.get("title", ""),
            "body": payload.get("body") or payload.get("message", ""),
            "camera": payload.get("camera", ""),
            "status": payload.get("status", ""),
            "thumbnail": payload.get("thumbnail") or payload.get("image", ""),
            "preview": payload.get("preview") or payload.get("gif", ""),
        },
        timeout=15,
    )
    response.raise_for_status()
    return response


def send_to_token(config: dict[str, Any], token: str, payload: dict[str, str]) -> requests.Response:
    """Dispatch a single notification to a single token using whichever
    delivery method is configured. "fcm" (default) is this server acting as
    its own private relay straight to Firebase. "relay" forwards to an
    optional third-party relay service instead."""
    delivery_method = (config["notifications"].get("delivery_method") or "fcm").lower()
    if delivery_method == "relay":
        relay_url = config["notifications"].get("fcm_api_url") or THIRD_PARTY_RELAY_URL
        return post_relay_payload(relay_url, token, payload)
    service_account_json = (config.get("firebase") or {}).get("service_account_json", "")
    return send_fcm_v1(service_account_json, token, payload)


class AutomationWorker:
    def __init__(self) -> None:
        self.client: mqtt.Client | websocket.WebSocketApp | None = None
        self.lock = threading.Lock()
        self.running = False
        self.last_triggered = 0.0
        self.events: dict[str, dict[str, Any]] = {}
        self.last_error = ""
        self.sent = 0
        self.connection_type = ""
        self.connected_since: float | None = None

    def start(self) -> None:
        with self.lock:
            if self.running:
                add_log("debug", "Worker start skipped; already running")
                return
            self.running = True
        add_log("info", "Worker starting")
        threading.Thread(target=self._run, daemon=True, name="frigate-automation-listener").start()

    def stop(self) -> None:
        with self.lock:
            self.running = False
        add_log("info", "Worker stopping")
        client = self.client
        if isinstance(client, mqtt.Client):
            client.disconnect()
        elif client is not None:
            client.close()

    def restart(self) -> None:
        add_log("info", "Worker restarting")
        self.stop()
        time.sleep(0.5)
        self.start()

    def status(self) -> dict[str, Any]:
        connected = False
        client = self.client
        if isinstance(client, mqtt.Client):
            connected = client.is_connected()
        elif client is not None:
            sock = getattr(client, "sock", None)
            connected = bool(sock and getattr(sock, "connected", False))
        return {
            "running": self.running,
            "connection_type": self.connection_type or "mqtt",
            "connected": connected,
            "sent": self.sent,
            "last_error": self.last_error,
            "tracked_events": len(self.events),
        }

    def _run(self) -> None:
        backoff = 2.0
        while self.running:
            config = load_config()
            if not config.get("enabled"):
                add_log("debug", "Worker disabled; sleeping")
                time.sleep(5)
                continue

            conn_type = ((config.get("connection") or {}).get("type") or "mqtt").lower()
            self.connection_type = conn_type
            if conn_type == "websocket":
                ws_config = config.get("websocket") or {}
                min_delay = max(number_value(ws_config.get("reconnect_min_seconds"), 2), 1)
                max_delay = max(number_value(ws_config.get("reconnect_max_seconds"), 60), min_delay)
            else:
                min_delay = max_delay = 10
            backoff = max(min(backoff, max_delay), min_delay)
            self.connected_since = None

            try:
                if conn_type == "websocket":
                    self._run_websocket(config)
                else:
                    self._run_mqtt(config)
            except Exception as exc:
                self.last_error = str(exc)
                add_log("error", f"{conn_type} worker error", error=str(exc))

            if not self.running:
                break

            connected_for = (time.time() - self.connected_since) if self.connected_since else 0
            backoff = min_delay if connected_for > 30 else min(backoff * 2, max_delay)
            add_log("info", "Reconnecting", seconds=round(backoff, 1), type=conn_type)
            time.sleep(backoff)

    def _run_mqtt(self, config: dict[str, Any]) -> None:
        mqtt_config = config["mqtt"]
        client_id = f"{mqtt_config.get('client_id')}-{int(time.time())}"
        add_log("info", "MQTT connect attempt", host=mqtt_config["host"], port=mqtt_config["port"], topic=mqtt_config["topic"], client_id=client_id)
        client = mqtt.Client(client_id=client_id, clean_session=True)
        username = mqtt_config.get("username")
        password = mqtt_config.get("password")
        if username:
            client.username_pw_set(username, password or None)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        self.client = client
        client.connect(mqtt_config["host"], int(mqtt_config["port"]), keepalive=30)
        client.loop_forever()

    def _run_websocket(self, config: dict[str, Any]) -> None:
        ws_config = config.get("websocket") or {}
        url = normalize_ws_url(ws_config.get("base_url", ""), ws_config.get("path", "/ws"))
        headers = parse_header_lines(ws_config.get("extra_headers", ""))
        ping_interval = number_value(ws_config.get("ping_interval"), 20) or 20
        ping_timeout = number_value(ws_config.get("ping_timeout"), 10) or 10
        if ping_timeout >= ping_interval:
            ping_timeout = max(ping_interval - 1, 1)
        add_log("info", "WebSocket connect attempt", url=url)

        def on_open(ws: websocket.WebSocketApp) -> None:
            self.connected_since = time.time()
            self.last_error = ""
            add_log("info", "WebSocket connected", url=url)
            ws.send(json.dumps({"topic": "onConnect", "payload": None}))

        def on_message(_ws: websocket.WebSocketApp, message: str) -> None:
            try:
                envelope = json.loads(message)
            except json.JSONDecodeError as exc:
                add_log("error", "WebSocket envelope decode failed", error=str(exc))
                return
            if not isinstance(envelope, dict) or envelope.get("topic") != "reviews":
                return
            raw_payload = envelope.get("payload")
            try:
                payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
            except json.JSONDecodeError as exc:
                add_log("error", "WebSocket payload decode failed", error=str(exc))
                return
            if not isinstance(payload, dict):
                add_log("error", "WebSocket payload was not an object", payload=compact_json(raw_payload))
                return
            add_log("debug", "WebSocket review event received", payload=compact_json(payload))
            self.handle_payload(payload)

        def on_error(_ws: websocket.WebSocketApp, error: Exception) -> None:
            self.last_error = str(error)
            add_log("error", "WebSocket error", error=str(error))

        def on_close(_ws: websocket.WebSocketApp, status_code: int | None, message: str | None) -> None:
            add_log("info", "WebSocket closed", code=status_code, message=message)

        app_ws = websocket.WebSocketApp(
            url,
            header=headers or None,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        self.client = app_ws
        app_ws.run_forever(ping_interval=ping_interval, ping_timeout=ping_timeout)

    def _on_connect(self, client: mqtt.Client, _userdata: Any, _flags: dict[str, Any], rc: int) -> None:
        if rc != 0:
            self.last_error = f"MQTT connect failed with code {rc}"
            add_log("error", "MQTT connect failed", code=rc)
            return
        topic = load_config()["mqtt"]["topic"]
        client.subscribe(topic, qos=1)
        self.connected_since = time.time()
        self.last_error = ""
        add_log("info", "MQTT connected and subscribed", topic=topic)

    def _on_message(self, _client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            add_log("debug", "MQTT message received", topic=message.topic, payload=compact_json(payload))
            self.handle_payload(payload)
        except Exception as exc:
            self.last_error = str(exc)
            add_log("error", "MQTT message handling failed", error=str(exc))

    def handle_payload(self, payload: dict[str, Any]) -> None:
        config = load_config()
        context = event_context(payload, config)
        event_type = context["type"]
        if event_type not in {"new", "update", "end", "genai"}:
            add_log("debug", "Event ignored: unsupported type", type=event_type, review_id=context["review_id"])
            return
        if not self.filters_pass(config, context):
            return

        event_id = context["id"]
        previous = self.events.get(event_id, {})
        changes = self.changed_fields(previous, context)
        first_matching_event = not previous and event_type in {"new", "update", "genai"}
        if not self.cooldown_pass(config, context, first_matching_event):
            return
        should_send = first_matching_event or bool(changes)
        should_send = should_send or (event_type == "end" and config["notifications"].get("final_update"))
        if not should_send:
            add_log("debug", "Event ignored: no relevant changes", review_id=event_id, type=event_type, changes=list(changes))
            return

        initial_delay = number_value(config["timers"].get("initial_delay"))
        if first_matching_event and initial_delay > 0:
            add_log("debug", "Initial notification delay", review_id=event_id, seconds=initial_delay)
            time.sleep(initial_delay)
        if event_type == "end" and config["notifications"].get("final_update"):
            final_delay = number_value(config["notifications"].get("final_delay"), 5)
            add_log("debug", "Final notification delay", review_id=event_id, seconds=final_delay)
            time.sleep(final_delay)

        notification_context = {**context, "type": "new"} if first_matching_event and event_type == "update" else context
        notification = self.build_notification(config, notification_context, silent=not first_matching_event)
        self.send_notification(config, notification)
        self.events[event_id] = {
            "zones": context["after_zones"],
            "objects": context["objects"],
            "label": context["label"],
            "severity": context["severity"],
        }
        if event_type == "end":
            self.events.pop(event_id, None)
        self.last_triggered = time.time()
        add_log("info", "Event processed", review_id=event_id, type=event_type, changes=list(changes), first_matching_event=first_matching_event)

    def filters_pass(self, config: dict[str, Any], context: dict[str, Any]) -> bool:
        filters = config["filters"]
        cameras = filters.get("cameras") or []
        if cameras and context["camera"] not in cameras:
            add_log("debug", "Filter failed: camera", camera=context["camera"], allowed=cameras, review_id=context["review_id"])
            return False
        if context["severity"] not in (filters.get("review_severity") or []):
            add_log("debug", "Filter failed: severity", severity=context["severity"], allowed=filters.get("review_severity") or [], review_id=context["review_id"])
            return False
        labels = filters.get("labels") or []
        candidates = {context["raw_label"], context["label"], *context["objects"], *context["verified_objects"], *context["sub_labels"]}
        if labels and candidates.isdisjoint(labels):
            add_log("debug", "Filter failed: labels", candidates=sorted(candidates), allowed=labels, review_id=context["review_id"])
            return False
        if datetime.now().hour in [int(hour) for hour in filters.get("disable_hours") or []]:
            add_log("debug", "Filter failed: disabled hour", hour=datetime.now().hour, review_id=context["review_id"])
            return False
        if not zones_satisfied(config, context["after_zones"]):
            add_log("debug", "Filter failed: zones", zones=context["after_zones"], required=filters.get("zones") or [], review_id=context["review_id"])
            return False
        if not custom_filter_satisfied(config, context):
            add_log("debug", "Filter failed: custom filter", review_id=context["review_id"])
            return False
        add_log("debug", "All filters passed", review_id=context["review_id"], camera=context["camera"], severity=context["severity"], label=context["label"])
        return True

    def cooldown_pass(
        self,
        config: dict[str, Any],
        context: dict[str, Any],
        first_matching_event: bool,
    ) -> bool:
        if not first_matching_event:
            return True
        cooldown = number_value(config["timers"].get("cooldown"), 30)
        elapsed = time.time() - self.last_triggered
        if cooldown and elapsed < cooldown:
            add_log("debug", "Filter failed: cooldown", cooldown=cooldown, elapsed=round(elapsed, 2), review_id=context["review_id"])
            return False
        return True

    @staticmethod
    def changed_fields(previous: dict[str, Any], context: dict[str, Any]) -> set[str]:
        if not previous:
            return set()
        changes = set()
        if previous.get("zones") != context["after_zones"]:
            changes.add("zones")
        if previous.get("objects") != context["objects"]:
            changes.add("objects")
        if previous.get("label") != context["label"]:
            changes.add("label")
        if previous.get("severity") != context["severity"]:
            changes.add("severity")
        return changes

    def build_notification(self, config: dict[str, Any], context: dict[str, Any], silent: bool) -> dict[str, str]:
        notifications = config["notifications"]
        attachment_template = notifications.get("attachment_2") if silent and notifications.get("attachment_2") else notifications.get("attachment")
        attachment = render_value(attachment_template, context)
        local_context = {**context, "attachment": attachment}
        video = render_value(notifications.get("video"), local_context)
        title = render_value(notifications.get("title"), local_context) or f"{context['label']} detected - {context['camera_name']}"
        message = render_value(notifications.get("message"), local_context)
        group = render_value(notifications.get("group"), local_context)
        actions = []
        for button in notifications.get("buttons") or []:
            button_title = render_value(button.get("title"), local_context)
            url = render_value(button.get("url"), {**local_context, "video": video})
            if button_title and url:
                actions.append({"action": "URI", "title": button_title, "uri": url})

        payload = {
            "sent_at": str(int(time.time() * 1000)),
            "timestamp": str(int(time.time() * 1000)),
            "title": title,
            "message": message,
            "body": message,
            "tag": context["id"],
            "id": context["id"],
            "event_id": context["event_id"],
            "review_id": context["review_id"],
            "camera": context["camera"],
            "status": context["type"],
            "group": group,
            "subject": render_value(notifications.get("subtitle"), local_context),
            "subtitle": render_value(notifications.get("subtitle"), local_context),
            "image": attachment,
            "thumbnail": attachment,
            "photo": context["snapshot"],
            "gif": video if "gif" in video else attachment if "gif" in attachment else context["preview"],
            "preview": video if "gif" in video else attachment if "gif" in attachment else context["preview"],
            "clip": video if (".mp4" in video or ".m3u8" in video) else context["clip"],
            "clip_url": video if (".mp4" in video or ".m3u8" in video) else context["clip"],
            "stream_url": video if ".m3u8" in video else context["stream"],
            "expanded_thumbnail": notifications.get("expanded_thumbnail", "photo"),
            "expanded_thumbnail_type": notifications.get("expanded_thumbnail", "photo"),
            "color": notifications.get("color", "#03a9f4"),
            "channel": "alarm_stream" if notifications.get("critical") else notifications.get("channel", "Default"),
            "alert_once": str(bool_value(notifications.get("alert_once"))).lower(),
            "sticky": str(bool_value(notifications.get("sticky"))).lower(),
            "car_ui": str(bool_value(notifications.get("android_auto"))).lower(),
        }
        if actions:
            payload["actions"] = json.dumps(actions)
            for index, action in enumerate(actions[:3], start=1):
                payload[f"button_{index}"] = action["title"]
                payload[f"url_{index}"] = action["uri"]
        result = {key: str(value) for key, value in payload.items() if value is not None}
        add_log("debug", "Notification payload built", review_id=context["review_id"], title=result.get("title"), label=context["label"], status=context["type"])
        return result

    def send_notification(self, config: dict[str, Any], payload: dict[str, str]) -> None:
        if not config["notifications"].get("enabled", True):
            add_log("info", "Notification skipped: notifications disabled", review_id=payload.get("review_id"))
            self.send_telegram(config, payload)
            return
        tokens = config["notifications"].get("tokens") or []
        delivery_method = (config["notifications"].get("delivery_method") or "fcm").lower()
        add_log("debug", "Sending notification", method=delivery_method, token_count=len(tokens), review_id=payload.get("review_id"))
        for token in tokens:
            try:
                response = send_to_token(config, token, payload)
                self.sent += 1
                add_log("info", "Notification sent", method=delivery_method, status_code=response.status_code, review_id=payload.get("review_id"), camera=payload.get("camera"))
            except Exception as exc:
                self.last_error = str(exc)
                add_log("error", "Notification send failed", method=delivery_method, error=str(exc), review_id=payload.get("review_id"), token=f"{str(token)[:5]}...")
        self.send_telegram(config, payload)

    def send_telegram(self, config: dict[str, Any], payload: dict[str, str]) -> None:
        telegram = config.get("telegram") or {}
        if not telegram.get("enabled") or not telegram.get("bot_token") or not telegram.get("chat_id"):
            add_log("debug", "Telegram skipped", enabled=bool(telegram.get("enabled")), review_id=payload.get("review_id"))
            return
        url = f"https://api.telegram.org/bot{telegram['bot_token']}/sendPhoto"
        requests.post(
            url,
            json={"chat_id": telegram["chat_id"], "caption": payload["message"], "photo": payload.get("image")},
            timeout=10,
        ).raise_for_status()
        add_log("info", "Telegram notification sent", review_id=payload.get("review_id"), chat_id=telegram.get("chat_id"))


worker = AutomationWorker()


def test_notification_payload() -> dict[str, str]:
    now_ms = str(int(time.time() * 1000))
    return {
        "sent_at": now_ms,
        "timestamp": now_ms,
        "title": "Frigate Native test",
        "message": "Test notification from Frigate Automation",
        "body": "Test notification from Frigate Automation",
        "tag": "frigate-native-test",
        "id": "frigate-native-test",
        "event_id": "frigate-native-test",
        "review_id": "frigate-native-test",
        "camera": "test",
        "status": "new",
        "group": "frigate-native-test",
        "subject": "FCM test",
        "subtitle": "FCM test",
        "expanded_thumbnail": "photo",
        "expanded_thumbnail_type": "photo",
    }


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login"))
        return func(*args, **kwargs)

    return wrapper


@app.before_request
def log_request_path() -> None:
    pass


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["authenticated"] = True
            return redirect(url_for("index"))
        return render_template("login.html", error="Invalid password"), 401
    return render_template("login.html", error="")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    config = load_config()
    if request.method == "POST":
        config = form_to_config(config, request.form)
        save_config(config)
        worker.restart()
        add_log("info", "Configuration saved and listener restarted")
        return redirect(url_for("index"))
    return render_template("index.html", config=config, status=worker.status(), logs=list(LIVE_LOGS))


@app.route("/health")
def health():
    return jsonify(worker.status())


@app.route("/api/logs")
@login_required
def logs():
    return jsonify({"logs": list(LIVE_LOGS), "status": worker.status()})


@app.route("/api/test", methods=["POST"])
@login_required
def test_notification():
    payload = request.get_json(force=True)
    worker.handle_payload(payload)
    return jsonify({"ok": True, "status": worker.status()})


@app.route("/api/test-fcm", methods=["POST"])
@login_required
def test_fcm():
    data = request.get_json(silent=True) or {}
    config = load_config()
    configured_tokens = config["notifications"].get("tokens") or []
    if data.get("all"):
        tokens = data.get("tokens") or configured_tokens
    else:
        tokens = [data.get("token")]
    tokens = [str(token).strip() for token in tokens if str(token or "").strip()]
    if not tokens:
        return jsonify({"error": "No FCM token selected"}), 400

    payload = test_notification_payload()
    sent = 0
    errors: list[str] = []
    for token in tokens:
        try:
            response = send_to_token(config, token, payload)
            sent += 1
            add_log(
                "info",
                "Test notification sent",
                status_code=response.status_code,
                token=f"{token[:5]}...",
                method=config["notifications"].get("delivery_method", "fcm"),
            )
        except Exception as exc:
            errors.append(str(exc))
            add_log("error", "Test notification failed", error=str(exc), token=f"{token[:5]}...")
    if not sent and errors:
        return jsonify({"error": errors[0]}), 502
    return jsonify({"ok": True, "sent": sent, "errors": errors})


def form_to_config(config: dict[str, Any], form: dict[str, str]) -> dict[str, Any]:
    updated = deepcopy(config)
    list_fields = {"notifications.tokens", "filters.cameras", "filters.review_severity", "filters.labels", "filters.zones", "filters.disable_hours"}
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
        elif dotted in bool_fields:
            parsed = bool_value(value)
        elif dotted in int_fields:
            parsed = number_value(value)
        else:
            parsed = value
        target[key] = parsed
    return updated


if __name__ == "__main__":
    worker.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5100")))
