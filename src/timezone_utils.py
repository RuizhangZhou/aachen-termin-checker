"""Shared timezone helpers for monitor summaries."""
from __future__ import annotations

from datetime import datetime, timezone, tzinfo
from zoneinfo import ZoneInfo
from typing import Final
import os

DEFAULT_MONITOR_TZ: Final[str] = "Europe/Berlin"


def _load_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        # Fallback to UTC if the requested zone is unavailable
        return ZoneInfo("UTC")


def _detect_server_timezone() -> tzinfo:
    try:
        tz = datetime.now().astimezone().tzinfo
    except Exception:
        tz = None
    return tz or timezone.utc


MONITOR_TZ_NAME: Final[str] = os.environ.get("MONITOR_TIMEZONE", DEFAULT_MONITOR_TZ)
DISPLAY_TZ: Final[ZoneInfo] = _load_timezone(MONITOR_TZ_NAME)
SERVER_TZ = _detect_server_timezone()
DISPLAY_TZ_LABEL: Final[str] = getattr(DISPLAY_TZ, "key", str(DISPLAY_TZ))


def to_display_timezone(timestamp: datetime) -> datetime:
    """Interpret naive timestamps as server-local and convert to the monitor TZ."""
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=SERVER_TZ)
    return timestamp.astimezone(DISPLAY_TZ)
