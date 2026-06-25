"""
app/filters.py — event context builder and filter evaluation helpers.

Import order: app.logging → app.utils → app.config → app.filters
"""

import time
from datetime import datetime
from typing import Any

from app.logging import add_log
from app.utils import (
    bool_value,
    detected_labels,
    display_label,
    render_value,
    unique_text,
)


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
