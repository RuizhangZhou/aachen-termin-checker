#!/usr/bin/env python3
"""Generate a daily summary from the monitor cron log."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import json
from statistics import median
from pathlib import Path
import re
import sys
from typing import Any, Dict, Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from notifications import log, send_error_notification, send_success_notification  # type: ignore


LOG_PATH = ROOT / "cron.log"
STATS_DIR = ROOT / "stats"
STATS_PATH = STATS_DIR / "slot_detection_stats.json"
LINE_PATTERN = re.compile(r"^\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*(?P<msg>.*)$")
MAX_LINES = 8
BUCKET_MINUTES = 30
CLUSTER_GAP_MINUTES = 6
DEFAULT_INTERVAL_SECONDS = 180
MAX_HOTSPOTS = 3
MIN_CHECKS_FOR_HOTSPOT = 10
MAX_RECENT_EVENTS = 4


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize daily monitor activity from cron.log")
    parser.add_argument(
        "--date",
        dest="target_date",
        help="Date to summarize in YYYY-MM-DD (defaults to yesterday)",
    )
    parser.add_argument(
        "--no-matrix",
        action="store_true",
        help="Print the summary but skip sending it to Matrix",
    )
    return parser.parse_args()


def _resolve_target_date(arg: str | None) -> date:
    if arg:
        return datetime.strptime(arg, "%Y-%m-%d").date()
    return date.today() - timedelta(days=1)


def _iter_entries(path: Path) -> Iterable[tuple[datetime, str]]:
    if not path.exists():
        return []

    def generator() -> Iterable[tuple[datetime, str]]:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                match = LINE_PATTERN.match(line.rstrip("\n"))
                if not match:
                    continue
                timestamp = datetime.strptime(match.group("ts"), "%Y-%m-%d %H:%M:%S")
                yield timestamp, match.group("msg")

    return generator()


def _filter_entries(entries: Iterable[tuple[datetime, str]], target: date) -> list[tuple[datetime, str]]:
    return [entry for entry in entries if entry[0].date() == target]


def _split_summary_lines(prefix: str, rows: Sequence[tuple[datetime, str]]) -> List[str]:
    lines: List[str] = []
    if not rows:
        return lines

    if len(rows) > MAX_LINES:
        visible = rows[:MAX_LINES]
        remainder = len(rows) - MAX_LINES
    else:
        visible = rows
        remainder = 0

    lines.append(prefix)
    for ts, message in visible:
        lines.append(f"- {ts:%H:%M:%S} – {message}")
    if remainder:
        lines.append(f"- … and {remainder} more entries")
    return lines


def _bucket_key(timestamp: datetime) -> str:
    bucket_minute = (timestamp.minute // BUCKET_MINUTES) * BUCKET_MINUTES
    return f"{timestamp.strftime('%a')} {timestamp.hour:02d}:{bucket_minute:02d}"


def _ensure_stats_dir() -> None:
    STATS_DIR.mkdir(parents=True, exist_ok=True)


def _default_stats() -> Dict[str, Any]:
    return {
        "version": 1,
        "bucket_minutes": BUCKET_MINUTES,
        "cluster_gap_minutes": CLUSTER_GAP_MINUTES,
        "updated_at": None,
        "buckets": {},
        "events": [],
    }


def _load_stats() -> Dict[str, Any]:
    if not STATS_PATH.exists():
        return _default_stats()

    try:
        with STATS_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:  # pragma: no cover - defensive logging
        log(f"Failed to load stats file: {exc}")
        return _default_stats()

    data.setdefault("buckets", {})
    data.setdefault("events", [])
    return data


def _write_stats(data: Dict[str, Any]) -> None:
    _ensure_stats_dir()
    with STATS_PATH.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)


def _estimate_interval_seconds(run_times: Sequence[datetime]) -> int:
    if len(run_times) < 2:
        return DEFAULT_INTERVAL_SECONDS

    deltas = [
        (current - previous).total_seconds()
        for previous, current in zip(run_times, run_times[1:])
        if current > previous
    ]
    if not deltas:
        return DEFAULT_INTERVAL_SECONDS

    estimated = median(deltas)
    return max(60, int(estimated))


def _cluster_slot_events(
    slot_events: Sequence[tuple[datetime, str]], interval_seconds: int
) -> List[Dict[str, Any]]:
    if not slot_events:
        return []

    clusters: List[Dict[str, Any]] = []
    current_start = slot_events[0][0]
    current_end = current_start
    detections = 1

    for timestamp, _ in slot_events[1:]:
        if timestamp - current_end <= timedelta(minutes=CLUSTER_GAP_MINUTES):
            current_end = timestamp
            detections += 1
            continue

        clusters.append(_build_event(current_start, current_end, detections, interval_seconds))
        current_start = current_end = timestamp
        detections = 1

    clusters.append(_build_event(current_start, current_end, detections, interval_seconds))
    return clusters


def _build_event(
    start: datetime, end: datetime, detections: int, interval_seconds: int
) -> Dict[str, Any]:
    span_seconds = max(0, int((end - start).total_seconds()))
    duration_seconds = span_seconds + max(60, interval_seconds)
    return {
        "start": start,
        "end": end,
        "detections": detections,
        "duration_seconds": duration_seconds,
    }


def _collect_event_buckets(events: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    bucket_summary: Dict[str, Dict[str, int]] = defaultdict(lambda: {"streak_seconds": 0, "streaks": 0})
    for event in events:
        bucket = _bucket_key(event["start"])
        bucket_summary[bucket]["streak_seconds"] += int(event["duration_seconds"])
        bucket_summary[bucket]["streaks"] += 1
    return bucket_summary


def _merge_bucket_counts(
    stats_data: Dict[str, Any],
    bucket_counts: Dict[str, Dict[str, int]],
    bucket_bounds: Dict[str, Dict[str, datetime]],
    event_buckets: Dict[str, Dict[str, int]],
) -> None:
    buckets = stats_data.setdefault("buckets", {})
    for key, counts in bucket_counts.items():
        bounds = bucket_bounds.get(key)
        if not bounds:
            continue

        first_iso = bounds["first"].isoformat()
        last_iso = bounds["last"].isoformat()
        state = buckets.setdefault(
            key,
            {
                "checks": 0,
                "detections": 0,
                "first_seen": first_iso,
                "last_seen": last_iso,
                "streak_seconds": 0,
                "streaks": 0,
            },
        )

        state["checks"] += counts.get("checks", 0)
        state["detections"] += counts.get("detections", 0)
        state["first_seen"] = min(state.get("first_seen", first_iso), first_iso)
        state["last_seen"] = max(state.get("last_seen", last_iso), last_iso)

        event_stats = event_buckets.get(key)
        if event_stats:
            state["streak_seconds"] = state.get("streak_seconds", 0) + event_stats.get("streak_seconds", 0)
            state["streaks"] = state.get("streaks", 0) + event_stats.get("streaks", 0)


def _format_hotspots(buckets: Dict[str, Any]) -> List[str]:
    ranked = []
    for key, stats in buckets.items():
        checks = stats.get("checks", 0)
        detections = stats.get("detections", 0)
        if detections == 0 or checks < MIN_CHECKS_FOR_HOTSPOT:
            continue
        rate = detections / checks if checks else 0.0
        streaks = stats.get("streaks", 0)
        avg_streak = stats.get("streak_seconds", 0) / streaks / 60 if streaks else 0.0
        ranked.append((rate, detections, checks, key, avg_streak))

    ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)

    lines: List[str] = []
    for rate, detections, checks, key, avg_streak in ranked[:MAX_HOTSPOTS]:
        rate_pct = rate * 100
        if avg_streak >= 0.1:
            lines.append(
                f"- {key} — {detections}/{checks} checks ({rate_pct:.1f}%), avg streak {avg_streak:.1f} min"
            )
        else:
            lines.append(f"- {key} — {detections}/{checks} checks ({rate_pct:.1f}%)")
    return lines


def _format_recent_events(events: Sequence[Dict[str, Any]]) -> List[str]:
    lines: List[str] = []
    for event in events[:MAX_RECENT_EVENTS]:
        start = event["start"].strftime("%a %H:%M")
        end = event["end"].strftime("%H:%M")
        duration_minutes = event["duration_seconds"] / 60
        detections = event["detections"]
        lines.append(f"- {start}–{end} (~{duration_minutes:.1f} min, {detections} detections)")
    return lines


def _build_stats_section(
    bucket_counts: Dict[str, Dict[str, int]],
    bucket_bounds: Dict[str, Dict[str, datetime]],
    run_times: Sequence[datetime],
    slot_events: Sequence[tuple[datetime, str]],
) -> List[str]:
    if not bucket_counts and not slot_events:
        return []

    interval_seconds = _estimate_interval_seconds(run_times)
    todays_events = _cluster_slot_events(slot_events, interval_seconds)
    event_buckets = _collect_event_buckets(todays_events) if todays_events else {}

    try:
        stats_data = _load_stats()
        stats_data["bucket_minutes"] = BUCKET_MINUTES
        stats_data["cluster_gap_minutes"] = CLUSTER_GAP_MINUTES
        stats_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        _merge_bucket_counts(stats_data, bucket_counts, bucket_bounds, event_buckets)

        if todays_events:
            serialized_events = [
                {
                    "start": event["start"].isoformat(),
                    "end": event["end"].isoformat(),
                    "detections": event["detections"],
                    "duration_seconds": event["duration_seconds"],
                }
                for event in todays_events
            ]
            stats_data.setdefault("events", []).extend(serialized_events)

        _write_stats(stats_data)
    except Exception as exc:  # pragma: no cover - persistence shouldn't break alerts
        log(f"Failed to update long-term stats: {exc}")
        return []

    lines: List[str] = []
    hotspot_lines = _format_hotspots(stats_data.get("buckets", {}))
    if hotspot_lines:
        lines.append("")
        lines.append(f"Historical detection hotspots ({BUCKET_MINUTES}-min buckets):")
        lines.extend(hotspot_lines)
    else:
        lines.append("")
        lines.append("Historical detection hotspots: insufficient data so far.")

    if todays_events:
        lines.append("Recent availability streaks today:")
        lines.extend(_format_recent_events(todays_events))

    return lines


def build_summary(entries: Sequence[tuple[datetime, str]], target: date) -> Tuple[str, List[str]]:
    run_times: List[datetime] = []
    slot_events: List[tuple[datetime, str]] = []
    error_events: List[tuple[datetime, str]] = []
    bucket_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {"checks": 0, "detections": 0})
    bucket_bounds: Dict[str, Dict[str, datetime]] = {}

    for timestamp, message in entries:
        bucket = _bucket_key(timestamp)
        bounds = bucket_bounds.setdefault(bucket, {"first": timestamp, "last": timestamp})
        if timestamp < bounds["first"]:
            bounds["first"] = timestamp
        if timestamp > bounds["last"]:
            bounds["last"] = timestamp

        if "Checking available slots" in message:
            run_times.append(timestamp)
            bucket_counts[bucket]["checks"] += 1
            continue
        if "available slots" in message and message.startswith("Found"):
            slot_events.append((timestamp, message))
            bucket_counts[bucket]["detections"] += 1
            continue
        if message.startswith("🚨"):
            error_events.append((timestamp, message))

    summary_lines: List[str] = [f"📝 RWTH monitor summary for {target:%Y-%m-%d}"]
    summary_lines.append(f"Checks performed: {len(run_times)}")

    if run_times:
        summary_lines.append(
            f"Monitoring window: {run_times[0]:%H:%M:%S} – {run_times[-1]:%H:%M:%S}"
        )

    if slot_events:
        summary_lines.extend(_split_summary_lines("Slot detections:", slot_events))
    else:
        summary_lines.append("Slot detections: none recorded")

    if error_events:
        summary_lines.extend(_split_summary_lines("Errors:", error_events))

    stats_lines = _build_stats_section(bucket_counts, bucket_bounds, run_times, slot_events)
    summary_lines.extend(stats_lines)

    return "\n".join(summary_lines), summary_lines


def main() -> None:
    args = _parse_args()
    target_date = _resolve_target_date(args.target_date)

    try:
        entries = _filter_entries(_iter_entries(LOG_PATH), target_date)
        summary_text, summary_lines = build_summary(entries, target_date)

        for line in summary_lines:
            log(line)

        if not args.no_matrix:
            send_success_notification(summary_text)

    except Exception as exc:
        log(f"Failed to build daily summary: {exc}")
        try:
            if not args.no_matrix:
                send_error_notification("Daily summary job failed", exc)
        finally:
            raise


if __name__ == "__main__":
    main()
