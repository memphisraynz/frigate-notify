"""
app/utils.py — pure stateless helpers and the shared Jinja2 environment.

Imports from app.logging only (for add_log in error paths).
"""

import json
import re
from copy import deepcopy
from datetime import datetime
from typing import Any

from jinja2 import Environment

from app.logging import add_log  # noqa: F401 — re-exported for convenience

# ─── Jinja2 environment ────────────────────────────────────────────────────

template_env = Environment(autoescape=False)
template_env.filters["timestamp_custom"] = lambda value, fmt: datetime.fromtimestamp(float(value)).strftime(fmt)
template_env.globals["iif"] = lambda condition, true_value, false_value="": true_value if condition else false_value


# ─── Type coercions ────────────────────────────────────────────────────────

def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}


def number_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def csv_list(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,\n]", value or "") if item.strip()]


# ─── Dict helpers ──────────────────────────────────────────────────────────

def deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# ─── Label helpers ─────────────────────────────────────────────────────────

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


# ─── JSON helpers ──────────────────────────────────────────────────────────

def parse_json_if_string(value: Any) -> Any:
    """If value is a JSON-encoded string, parse and return it; otherwise return as-is."""
    if isinstance(value, str) and value.strip().startswith(("{", "[")):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass
    return value


def compact_json(value: Any, limit: int = 1200) -> str:
    text = json.dumps(value, default=str, separators=(",", ":"))
    return text if len(text) <= limit else f"{text[:limit]}..."


# ─── Template rendering ────────────────────────────────────────────────────

def render_value(value: Any, context: dict[str, Any]) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value)
    return template_env.from_string(str(value)).render(**context).strip()


# ─── Network helpers ───────────────────────────────────────────────────────

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
