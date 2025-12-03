#!/usr/bin/env python3
"""Generate a historical summary of availability hotspots."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import gzip
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT
LOG_PATTERN = re.compile(r"cron\.log(\..+)?$")
LINE_PATTERN = re.compile(r"^\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*(?P<msg>.*)$")
BUCKET_MINUTES = 30
CLUSTER_GAP_MINUTES = 6
MIN_CHECKS_FOR_BUCKET = 10
TOP_BUCKETS = 8
TOP_STREAKS = 5
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DEFAULT_INTERVAL_SECONDS = 180

SRC_DIR = ROOT / "src"
import sys
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from notifications import log, send_error_notification, send_success_notification  # type: ignore


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize historical availability hotspots")
    parser.add_argument("--no-matrix", action="store_true", help="Only print to stdout")
    parser.add_argument("--min-checks", type=int, default=MIN_CHECKS_FOR_BUCKET, help="Minimum checks for a bucket to be ranked")
    parser.add_argument("--top", type=int, default=TOP_BUCKETS, help="How many top buckets to include")
    parser.add_argument("--top-streaks", type=int, default=TOP_STREAKS, help="How many longest streaks to include")
    return parser.parse_args()


def _iter_log_paths() -> List[Path]:
    paths = [path for path in LOG_DIR.glob("cron.log*") if LOG_PATTERN.match(path.name)]
    return sorted(paths, key=lambda p: p.stat().st_mtime)


def _iter_entries(paths: Sequence[Path]) -> List[Tuple[datetime, str]]:
    entries: List[Tuple[datetime, str]] = []
    for path in paths:
        opener = gzip.open if path.suffix == ".gz" else open
        try:
            with opener(path, "rt", encoding="utf-8", errors="ignore") as handle:  # type: ignore[arg-type]
                for line in handle:
                    match = LINE_PATTERN.match(line.rstrip("\n"))
                    if not match:
                        continue
                    timestamp = datetime.strptime(match.group("ts"), "%Y-%m-%d %H:%M:%S")
                    entries.append((timestamp, match.group("msg")))
        except FileNotFoundError:
            continue
    entries.sort(key=lambda item: item[0])
    return entries


def _bucket_key(timestamp: datetime) -> str:
    bucket_minute = (timestamp.minute // BUCKET_MINUTES) * BUCKET_MINUTES
    return f"{timestamp.strftime('%a')} {timestamp.hour:02d}:{bucket_minute:02d}"


def _estimate_interval_seconds(run_times: Sequence[datetime]) -> int:
    if len(run_times) < 2:
        return DEFAULT_INTERVAL_SECONDS
    deltas = [
        int((current - previous).total_seconds())
        for previous, current in zip(run_times, run_times[1:])
        if current > previous
    ]
    if not deltas:
        return DEFAULT_INTERVAL_SECONDS
    return max(60, sorted(deltas)[len(deltas) // 2])


def _cluster_slot_events(
    slot_events: Sequence[Tuple[datetime, str]], interval_seconds: int
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


def _aggregate_weekdays(buckets: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    totals: Dict[str, Dict[str, int]] = {day: {"checks": 0, "detections": 0} for day in WEEKDAYS}
    for key, stats in buckets.items():
        weekday = key.split()[0][:3]
        if weekday not in totals:
            continue
        totals[weekday]["checks"] += stats.get("checks", 0)
        totals[weekday]["detections"] += stats.get("detections", 0)
    return totals


def _format_weekday_lines(totals: Dict[str, Dict[str, int]]) -> List[str]:
    lines: List[str] = []
    for day in WEEKDAYS:
        stats = totals.get(day)
        if not stats or stats["checks"] == 0:
            lines.append(f"- {day}: no data")
            continue
        rate = stats["detections"] / stats["checks"] * 100
        lines.append(
            f"- {day}: {stats['detections']}/{stats['checks']} checks ({rate:.2f}%)"
        )
    return lines


def _gather_history(entries: Sequence[Tuple[datetime, str]]):
    bucket_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "checks": 0,
        "detections": 0,
        "first_seen": None,
        "last_seen": None,
    })
    run_times: List[datetime] = []
    slot_events: List[Tuple[datetime, str]] = []
    errors: List[Tuple[datetime, str]] = []
    for timestamp, message in entries:
        bucket = _bucket_key(timestamp)
        state = bucket_stats[bucket]
        state["first_seen"] = timestamp if state["first_seen"] is None else min(state["first_seen"], timestamp)
        state["last_seen"] = timestamp if state["last_seen"] is None else max(state["last_seen"], timestamp)

        if "Checking available slots" in message:
            state["checks"] += 1
            run_times.append(timestamp)
            continue
        if message.startswith("Found") and "available slots" in message:
            state["detections"] += 1
            slot_events.append((timestamp, message))
            continue
        if message.startswith("🚨") or "error" in message.lower():
            errors.append((timestamp, message))
    return bucket_stats, run_times, slot_events, errors


def _format_bucket_line(
    bucket: str,
    stats: Dict[str, Any],
    event_stats: Dict[str, int] | None,
) -> str:
    detections = stats.get("detections", 0)
    checks = stats.get("checks", 0)
    rate = detections / checks * 100 if checks else 0.0
    avg_streak = 0.0
    if event_stats and event_stats.get("streaks", 0):
        avg_streak = event_stats["streak_seconds"] / event_stats["streaks"] / 60
    first_seen = stats.get("first_seen")
    last_seen = stats.get("last_seen")
    first_txt = first_seen.strftime("%Y-%m-%d") if first_seen else "?"
    last_txt = last_seen.strftime("%Y-%m-%d") if last_seen else "?"
    if avg_streak > 0:
        streak_part = f", avg streak {avg_streak:.1f} min"
    else:
        streak_part = ""
    return (
        f"- {bucket} — {detections}/{checks} checks ({rate:.2f}%){streak_part}"
        f" [span {first_txt} → {last_txt}]"
    )


def build_summary(
    entries: Sequence[Tuple[datetime, str]],
    limit_buckets: int,
    min_checks: int,
    limit_streaks: int,
) -> Tuple[str, List[str]]:
    if not entries:
        lines = ["ℹ️ No log entries found; cannot build historical summary."]
        return "\n".join(lines), lines

    bucket_stats, run_times, slot_events, _ = _gather_history(entries)
    total_checks = sum(stats["checks"] for stats in bucket_stats.values())
    total_detections = sum(stats["detections"] for stats in bucket_stats.values())
    first_seen = entries[0][0]
    last_seen = entries[-1][0]

    lines: List[str] = []
    header = (
        f"🗂️ RWTH historical hotspots (data window {first_seen:%Y-%m-%d} → {last_seen:%Y-%m-%d})"
    )
    lines.append(header)
    rate = total_detections / total_checks * 100 if total_checks else 0.0
    lines.append(
        f"Observed {total_checks} checks and {total_detections} detections ({rate:.2f}%)."
    )

    interval_seconds = _estimate_interval_seconds(run_times)
    events = _cluster_slot_events(slot_events, interval_seconds)
    event_buckets = _collect_event_buckets(events)

    ranked = [
        (stats["detections"] / stats["checks"], stats["detections"], stats["checks"], bucket)
        for bucket, stats in bucket_stats.items()
        if stats["detections"] > 0 and stats["checks"] >= min_checks
    ]
    ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)

    lines.append("")
    if ranked:
        lines.append(f"Top {min(limit_buckets, len(ranked))} time buckets (>= {min_checks} checks):")
        for _, _, _, bucket in ranked[:limit_buckets]:
            stats = bucket_stats[bucket]
            event_stats = event_buckets.get(bucket)
            lines.append(_format_bucket_line(bucket, stats, event_stats))
    else:
        fallback = [
            (stats["detections"], stats["checks"], bucket)
            for bucket, stats in bucket_stats.items()
            if stats["detections"] > 0
        ]
        fallback.sort(key=lambda item: (item[0], item[1]), reverse=True)
        if fallback:
            lines.append(
                f"No buckets met the >= {min_checks} checks threshold; showing top detections instead:"
            )
            for detections, checks, bucket in fallback[:limit_buckets]:
                stats = bucket_stats[bucket]
                event_stats = event_buckets.get(bucket)
                lines.append(_format_bucket_line(bucket, stats, event_stats))
        else:
            lines.append("No availability detections recorded yet.")

    weekday_totals = _aggregate_weekdays(bucket_stats)
    lines.append("")
    lines.append("Weekday detection rates:")
    lines.extend(_format_weekday_lines(weekday_totals))

    if events:
        lines.append("")
        lines.append("Longest observed availability streaks:")
        sorted_events = sorted(events, key=lambda e: e["duration_seconds"], reverse=True)
        for event in sorted_events[:limit_streaks]:
            start = event["start"].strftime("%a %Y-%m-%d %H:%M")
            end = event["end"].strftime("%H:%M")
            duration = event["duration_seconds"] / 60
            detections = event["detections"]
            lines.append(
                f"- {start}–{end} (~{duration:.1f} min, {detections} detections)"
            )

    summary_text = "\n".join(lines)
    return summary_text, lines


def main() -> None:
    args = _parse_args()
    try:
        paths = _iter_log_paths()
        entries = _iter_entries(paths)
        summary_text, summary_lines = build_summary(entries, args.top, args.min_checks, args.top_streaks)
        for line in summary_lines:
            log(line)
        if not args.no_matrix:
            send_success_notification(summary_text)
    except Exception as exc:
        log(f"Failed to build historical summary: {exc}")
        if not args.no_matrix:
            send_error_notification("Historical summary job failed", exc)
        raise


if __name__ == "__main__":
    main()
