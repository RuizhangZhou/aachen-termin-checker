#!/usr/bin/env python3
"""Clean up logs produced by the monitor job, keeping the last 14 days."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

LOG_PATH = Path(__file__).parent / "cron.log"
RETENTION_DAYS = 14
_DATE_PATTERN = re.compile(r"\[(\d{4}-\d{2}-\d{2})")


def _parse_line_date(line: str) -> datetime | None:
    match = _DATE_PATTERN.search(line)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d")
    except ValueError:
        return None


def prune_log_file(path: Path, cutoff: datetime) -> int:
    if not path.exists():
        return 0

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return 0

    kept_lines = []
    removed = 0
    for line in lines:
        line_date = _parse_line_date(line)
        if line_date is None or line_date >= cutoff:
            kept_lines.append(line)
        else:
            removed += 1

    if removed:
        path.write_text("\n".join(kept_lines) + ("\n" if kept_lines else ""), encoding="utf-8")
    return removed


def prune_rotated_logs(path: Path, cutoff: datetime) -> list[str]:
    removed = []
    for rotated in sorted(path.parent.glob("cron.log.*")):
        try:
            if datetime.fromtimestamp(rotated.stat().st_mtime) < cutoff:
                rotated.unlink(missing_ok=True)
                removed.append(rotated.name)
        except FileNotFoundError:
            continue
    return removed


def main() -> None:
    now = datetime.now()
    cutoff = now - timedelta(days=RETENTION_DAYS)

    removed_lines = prune_log_file(LOG_PATH, cutoff)
    removed_files = prune_rotated_logs(LOG_PATH, cutoff)

    if removed_lines or removed_files:
        summary = [f"[{now:%Y-%m-%d %H:%M:%S}] Log cleanup:"]
        if removed_lines:
            summary.append(f"Removed {removed_lines} old log lines")
        if removed_files:
            summary.append(f"Removed old log files {', '.join(removed_files)}")
        print(" ".join(summary))


if __name__ == "__main__":
    main()
