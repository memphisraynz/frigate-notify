"""
app/notifications.py — outbound notification delivery.

Owns the Firebase credential cache and all send functions.
build_notification and send_notification are standalone functions
(previously methods on AutomationWorker) that accept config + context.

Import order: app.logging → app.utils → app.config → app.notifications
"""

import json
import threading
import time
from typing import Any

import google.auth.transport.requests
import requests
from google.oauth2 import service_account

from app.config import THIRD_PARTY_RELAY_URL
from app.logging import add_log
from app.utils import bool_value, render_value

# ─── Firebase credential cache ─────────────────────────────────────────────

_firebase_lock = threading.Lock()
_firebase_cache: dict[str, Any] = {"raw": None, "credentials": None, "project_id": None}

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


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


# ─── Low-level send helpers ────────────────────────────────────────────────

def send_fcm_v1(service_account_json: str, token: str, payload: dict[str, str]) -> requests.Response:
    credentials, project_id = get_firebase_credentials(service_account_json)
    with _firebase_lock:
        if not credentials.valid:
            credentials.refresh(google.auth.transport.requests.Request())
        access_token = credentials.token

    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

    fcm_message = {
        "message": {
            "token": token,
            "data": {
                # Primary content
                "title":                    payload.get("title"),
                "message":                  payload.get("message"),
                "image":                    payload.get("image") or payload.get("thumbnail"),

                # Notification click action
                "url":                      payload.get("url") or payload.get("click_action"),

                # Action buttons
                "button_1":                 payload.get("button_1"),
                "url_1":                    payload.get("url_1"),
                "button_2":                 payload.get("button_2"),
                "url_2":                    payload.get("url_2"),
                "button_3":                 payload.get("button_3"),
                "url_3":                    payload.get("url_3"),

                # Media
                "photo":                    payload.get("photo"),
                "gif":                      payload.get("gif"),
                "preview":                  payload.get("preview"),
                "clip":                     payload.get("clip"),
                "clip_url":                 payload.get("clip_url"),
                "stream_url":               payload.get("stream_url"),
                "expanded_thumbnail":       payload.get("expanded_thumbnail"),
                "expanded_thumbnail_type":  payload.get("expanded_thumbnail_type"),

                # Presentation
                "subtitle":                 payload.get("subtitle"),
                "subject":                  payload.get("subject"),
                "color":                    payload.get("color"),
                "channel":                  payload.get("channel"),
                "sticky":                   payload.get("sticky"),
                "car_ui":                   payload.get("car_ui"),

                # Metadata / behaviour
                "group":                    payload.get("group"),
                "tag":                      payload.get("tag"),
                "id":                       payload.get("id"),
                "event_id":                 payload.get("event_id"),
                "camera":                   payload.get("camera"),
                "review_id":                payload.get("review_id"),
                "status":                   payload.get("status"),
                "alert_once":               payload.get("alert_once"),
                "sent_at":                  payload.get("sent_at"),
                "timestamp":                payload.get("timestamp"),
            },
            "android": {
                "priority": "high",
                "ttl": "0s",
            },
            "apns": {
                "payload": {
                    "aps": {
                        "alert": {
                            "title": payload.get("title"),
                            "body": payload.get("message"),
                        },
                        "mutable-content": 1,
                        "category": "frigate_alert",
                    }
                }
            },
        }
    }

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; UTF-8",
        },
        json=fcm_message,
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
    delivery_method = (config["notifications"].get("delivery_method") or "fcm").lower()
    if delivery_method == "relay":
        relay_url = config["notifications"].get("fcm_api_url") or THIRD_PARTY_RELAY_URL
        return post_relay_payload(relay_url, token, payload)
    service_account_json = (config.get("firebase") or {}).get("service_account_json", "")
    return send_fcm_v1(service_account_json, token, payload)


# ─── High-level notification builders ─────────────────────────────────────

def build_notification(config: dict[str, Any], context: dict[str, Any], silent: bool) -> dict[str, str]:
    notifications = config["notifications"]
    attachment_template = (
        notifications.get("attachment_2")
        if silent and notifications.get("attachment_2")
        else notifications.get("attachment")
    )
    attachment = render_value(attachment_template, context)
    local_context = {**context, "attachment": attachment}
    video = render_value(notifications.get("video"), local_context)
    title = (
        render_value(notifications.get("title"), local_context)
        or f"{context['label']} detected - {context['camera_name']}"
    )
    message_template = notifications.get("message", "")
    sub_label_message_template = notifications.get("sub_label_message", "")
    if sub_label_message_template and context["sub_labels"]:
        message_template = sub_label_message_template
    message = render_value(message_template, local_context)
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
        "click_action": render_value(notifications.get("click_action"), local_context),
    }
    if actions:
        payload["actions"] = json.dumps(actions)
        for index, action in enumerate(actions[:3], start=1):
            payload[f"button_{index}"] = action["title"]
            payload[f"url_{index}"] = action["uri"]
    result = {key: str(value) for key, value in payload.items() if value is not None}
    add_log(
        "debug",
        "Notification payload built",
        review_id=context["review_id"],
        title=result.get("title"),
        label=context["label"],
        status=context["type"],
    )
    return result


def send_notification(config: dict[str, Any], payload: dict[str, str]) -> int:
    """Send notification to all configured tokens.  Returns count sent."""
    if not config["notifications"].get("enabled", True):
        add_log("info", "Notification skipped: notifications disabled", review_id=payload.get("review_id"))
        return 0

    tokens = config["notifications"].get("tokens") or []
    delivery_method = (config["notifications"].get("delivery_method") or "fcm").lower()

    add_log(
        "info",
        f"Compiled Notification Payload ({delivery_method})",
        payload_details=payload,
    )
    add_log(
        "debug",
        "Sending notification",
        method=delivery_method,
        token_count=len(tokens),
        review_id=payload.get("review_id"),
    )

    sent = 0
    last_error = ""
    for entry in tokens:
        name = entry.get("name") or ""
        token = entry.get("token") or ""
        if not token:
            continue
        try:
            response = send_to_token(config, token, payload)
            sent += 1
            add_log(
                "info",
                "Notification sent",
                method=delivery_method,
                device=name or token[:8] + "...",
                status_code=response.status_code,
                review_id=payload.get("review_id"),
                camera=payload.get("camera"),
            )
        except Exception as exc:
            last_error = str(exc)
            add_log(
                "error",
                "Notification send failed",
                method=delivery_method,
                error=str(exc),
                review_id=payload.get("review_id"),
                device=name or token[:8] + "...",
            )
    return sent
