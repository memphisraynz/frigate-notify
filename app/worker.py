"""
app/worker.py — AutomationWorker class and module-level singleton.

Import order: ... → app.filters → app.notifications → app.worker
"""

import json
import threading
import time
from datetime import datetime
from typing import Any

import websocket
from paho.mqtt import client as mqtt

from app.config import load_config
from app.filters import custom_filter_satisfied, event_context, zones_satisfied
from app.logging import add_log
from app.notifications import build_notification, send_notification
from app.utils import normalize_ws_url, number_value, parse_header_lines


class AutomationWorker:
    def __init__(self) -> None:
        self.client: mqtt.Client | websocket.WebSocketApp | None = None
        self.lock = threading.Lock()
        self.events_lock = threading.Lock()
        self.running = False
        self.last_triggered: dict[str, float] = {}
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
        threading.Thread(target=self._run, daemon=True, name="frigate-notify-listener").start()

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
        add_log(
            "info",
            "MQTT connect attempt",
            host=mqtt_config["host"],
            port=mqtt_config["port"],
            topic=mqtt_config["topic"],
            client_id=client_id,
        )
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
                add_log("error", "WebSocket payload was not an object", payload=raw_payload)
                return
            add_log("debug", "WebSocket review event received", payload=payload)
            self.handle_payload(payload)

        def on_error(_ws: websocket.WebSocketApp, error: Exception) -> None:
            self.last_error = str(error)
            add_log("error", "WebSocket error", error=str(error))

        def on_close(_ws: websocket.WebSocketApp, status_code: int | None, close_msg: str | None) -> None:
            add_log("info", "WebSocket closed", code=status_code, close_message=close_msg)

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
            add_log("debug", "MQTT message received", topic=message.topic, payload=payload)
            self.handle_payload(payload)
        except Exception as exc:
            self.last_error = str(exc)
            add_log("error", "MQTT message handling failed", error=str(exc))

    def handle_payload(self, payload: dict[str, Any], is_test: bool = False) -> None:
        config = load_config()
        context = event_context(payload, config)
        event_type = context["type"]
        if event_type not in {"new", "update", "end", "genai"}:
            add_log("debug", "Event ignored: unsupported type", type=event_type, review_id=context["review_id"])
            return

        if not is_test and not self.filters_pass(config, context):
            return

        event_id = context["id"]
        with self.events_lock:
            previous = self.events.get(event_id, {})
            if not previous and event_type in {"new", "update", "genai"}:
                self.events[event_id] = {}
        changes = self.changed_fields(previous, context)
        first_matching_event = not previous and event_type in {"new", "update", "genai"}

        if not is_test and not self.cooldown_pass(config, context, first_matching_event):
            return

        should_send = first_matching_event or bool(changes) or is_test
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

        notification_context = (
            {**context, "type": "new"} if first_matching_event and event_type == "update" else context
        )
        # "end" events are always silent updates — they replace the existing
        # notification on the device rather than firing a new alert sound.
        is_silent = not first_matching_event or event_type == "end"
        notification = build_notification(config, notification_context, silent=is_silent)
        sent = send_notification(config, notification)
        self.sent += sent
        self.send_telegram(config, notification)

        with self.events_lock:
            self.events[event_id] = {
                "zones": context["after_zones"],
                "objects": context["objects"],
                "label": context["label"],
                "severity": context["severity"],
            }
            if event_type == "end":
                self.events.pop(event_id, None)
            if first_matching_event:
                self.last_triggered[context["camera"]] = time.time()
        add_log(
            "info",
            "Event processed",
            review_id=event_id,
            type=event_type,
            changes=list(changes),
            first_matching_event=first_matching_event,
        )

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

    def cooldown_pass(self, config: dict[str, Any], context: dict[str, Any], first_matching_event: bool) -> bool:
        if not first_matching_event:
            return True
        cooldown = number_value(config["timers"].get("cooldown"), 30)
        camera = context["camera"]
        elapsed = time.time() - self.last_triggered.get(camera, 0.0)
        if cooldown and elapsed < cooldown:
            add_log("debug", "Filter failed: cooldown", cooldown=cooldown, elapsed=round(elapsed, 2), camera=camera, review_id=context["review_id"])
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

    def send_telegram(self, config: dict[str, Any], payload: dict[str, str]) -> None:
        pass


# ─── Module-level singleton ────────────────────────────────────────────────
# Created here so routes.py can import it without going through app/__init__.py.
worker = AutomationWorker()
