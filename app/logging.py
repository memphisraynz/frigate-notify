"""
app/logging.py — in-memory log deque + rotating file logger.

This module is a leaf: it imports nothing from the rest of the app package.
Every other module that needs add_log imports directly from here.
"""

import json
import logging
import logging.handlers
import os
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

# Re-exported so callers can do: from app.logging import LIVE_LOGS
LIVE_LOGS: deque[dict[str, Any]] = deque(maxlen=500)

# Derived from the same env var used by config so LOG_DIR stays consistent
# without importing config (which would create a circular dependency).
_CONFIG_PATH = Path(os.environ.get("FRIGATE_NOTIFY_CONFIG", "/data/config.json"))
LOG_DIR = _CONFIG_PATH.parent / "logs"


def _setup_file_logger() -> logging.Logger:
    """Set up a daily-rotating file logger that writes to /data/logs/.

    Keeps 7 days of log files (today + 6 backups).  Each file is named
    frigate-notify.log and rotates at midnight, with suffixes like
    frigate-notify.log.2025-06-24.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("frigate_notify")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.handlers.TimedRotatingFileHandler(
            filename=str(LOG_DIR / "frigate-notify.log"),
            when="midnight",
            interval=1,
            backupCount=6,  # keep today + 6 previous days = 7 days total
            encoding="utf-8",
            utc=False,
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-5s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        logger.addHandler(handler)
    return logger


_file_logger = _setup_file_logger()


def add_log(level: str, message: str, **fields: Any) -> None:
    """Append a log entry to the in-memory deque and to the rotating file.

    Field values that are JSON strings are automatically parsed back to
    objects so the UI can display them formatted rather than as a flat string.
    """
    parsed_fields: dict[str, Any] = {}
    for k, v in fields.items():
        if isinstance(v, str) and v.strip().startswith(("{", "[")):
            try:
                parsed_fields[k] = json.loads(v)
                continue
            except (json.JSONDecodeError, ValueError):
                pass
        parsed_fields[k] = v

    entry: dict[str, Any] = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "level": level,
        "message": message,
        "fields": parsed_fields,
    }
    LIVE_LOGS.appendleft(entry)

    log_method = getattr(_file_logger, level.lower(), _file_logger.info)
    if parsed_fields:
        log_method("%s | %s", message, json.dumps(parsed_fields, default=str))
    else:
        log_method("%s", message)
