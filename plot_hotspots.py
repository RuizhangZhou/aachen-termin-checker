#!/usr/bin/env python3
"""Render a day/time heatmap of detection rates."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")  # Use a headless backend by default
import matplotlib.pyplot as plt
from matplotlib import colors
import numpy as np

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DEFAULT_STATS_PATH = Path("stats/slot_detection_stats.json")
DEFAULT_OUTPUT_PATH = Path("stats/hotspot_heatmap.png")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot detection-rate hotspots from aggregated stats")
    parser.add_argument(
        "--stats-path",
        type=Path,
        default=DEFAULT_STATS_PATH,
        help="Path to slot_detection_stats.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Where to write the heatmap PNG",
    )
    parser.add_argument(
        "--recent-days",
        type=int,
        default=None,
        help="Only include buckets whose last_seen is within the last N days",
    )
    parser.add_argument(
        "--min-checks",
        type=int,
        default=10,
        help="Skip buckets with fewer than this many checks",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=8,
        help="Highlight this many best-performing buckets",
    )
    parser.add_argument(
        "--max-share",
        type=float,
        default=10.0,
        help="Clamp color scale to this percentage (set <=0 to auto fit data)",
    )
    parser.add_argument(
        "--gamma",
        type=float,
        default=0.45,
        help="Gamma for color scaling (<1 boosts contrast on low percentages)",
    )
    return parser.parse_args()


def _load_stats(path: Path) -> Dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"Stats file {path} does not exist")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    buckets = data.get("buckets")
    if not isinstance(buckets, dict):
        raise ValueError("Unexpected stats file format: missing 'buckets'")
    return data


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _strip_timezone(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _build_time_axis(bucket_minutes: int) -> Tuple[List[str], Dict[str, int]]:
    labels: List[str] = []
    positions: Dict[str, int] = {}
    steps = int(60 / bucket_minutes)
    if steps * bucket_minutes != 60:
        raise ValueError("Bucket minutes must divide 60 evenly")
    total_slots = int(24 * 60 / bucket_minutes)
    for idx in range(total_slots):
        minutes = idx * bucket_minutes
        hour = minutes // 60
        minute = minutes % 60
        label = f"{hour:02d}:{minute:02d}"
        positions[label] = idx
        labels.append(label)
    return labels, positions


def _should_include(stats: Dict[str, object], min_checks: int, cutoff: datetime | None) -> bool:
    checks = int(stats.get("checks", 0))
    if checks < min_checks:
        return False
    if cutoff is None:
        return True
    last_seen = _strip_timezone(_parse_iso(stats.get("last_seen")))
    return last_seen is not None and last_seen >= cutoff


def _prepare_matrix(
    buckets: Dict[str, Dict[str, object]],
    min_checks: int,
    cutoff: datetime | None,
    bucket_minutes: int,
) -> Tuple[np.ndarray, Dict[Tuple[int, int], Dict[str, object]], List[str], Dict[str, int]]:
    time_labels, time_index = _build_time_axis(bucket_minutes)
    matrix = np.full((len(WEEKDAYS), len(time_labels)), np.nan)
    cell_info: Dict[Tuple[int, int], Dict[str, object]] = {}
    total_detections = 0
    for key, stats in buckets.items():
        if not isinstance(stats, dict):
            continue
        try:
            weekday, time_label = key.split()
        except ValueError:
            continue
        if weekday not in WEEKDAYS or time_label not in time_index:
            continue
        if not _should_include(stats, min_checks, cutoff):
            continue
        checks = int(stats.get("checks", 0))
        detections = int(stats.get("detections", 0))
        if detections <= 0:
            continue
        row = WEEKDAYS.index(weekday)
        col = time_index[time_label]
        info = {
            "weekday": weekday,
            "time": time_label,
            "checks": checks,
            "detections": detections,
            "first_seen": stats.get("first_seen"),
            "last_seen": stats.get("last_seen"),
            "row": row,
            "col": col,
        }
        cell_info[(row, col)] = info
        total_detections += detections

    if total_detections == 0:
        return matrix, cell_info, time_labels, time_index

    for (row, col), info in cell_info.items():
        share = info["detections"] / total_detections * 100
        info["share"] = share
        matrix[row, col] = share

    return matrix, cell_info, time_labels, time_index


def _pick_top_cells(cell_info: Dict[Tuple[int, int], Dict[str, object]], limit: int) -> List[Dict[str, object]]:
    ranked = sorted(
        cell_info.values(),
        key=lambda item: (item.get("share", 0.0), item["detections"], item["checks"]),
        reverse=True,
    )
    return ranked[:limit]


def _plot_heatmap(
    matrix: np.ndarray,
    time_labels: List[str],
    top_cells: List[Dict[str, object]],
    output_path: Path,
    recent_days: int | None,
    min_checks: int,
    bucket_minutes: int,
    max_share: float | None,
    gamma: float,
) -> None:
    masked = np.ma.masked_invalid(matrix)
    cmap = plt.get_cmap("YlOrRd").copy()
    cmap.set_bad(color="#f0f0f0")

    data_max = np.nanmax(matrix)
    if not np.isfinite(data_max):
        raise SystemExit("No data values to plot")
    vmax = max_share if (max_share and max_share > 0) else data_max
    vmax = min(max(1e-3, vmax), 100.0)
    norm = colors.PowerNorm(gamma=max(gamma, 0.1), vmin=0, vmax=vmax)

    width = max(10, len(time_labels) * 0.25)
    fig, ax = plt.subplots(figsize=(width, 4.5))
    image = ax.imshow(masked, aspect="auto", cmap=cmap, norm=norm)

    tick_step = max(1, int(60 / bucket_minutes))
    ticks = list(range(0, len(time_labels), tick_step))
    tick_labels = [time_labels[i] for i in ticks]
    ax.set_xticks(ticks, tick_labels, rotation=90)
    ax.set_yticks(range(len(WEEKDAYS)), WEEKDAYS)
    ax.set_xlabel("Time of day")
    ax.set_ylabel("Weekday")

    title_parts = ["RWTH detection-share heatmap"]
    if recent_days:
        title_parts.append(f"(last {recent_days} days, min {min_checks} checks)")
    else:
        title_parts.append(f"(all data, min {min_checks} checks)")
    ax.set_title(" ".join(title_parts))

    for cell in top_cells:
        col = int(cell["col"])
        row = int(cell["row"])
        value = cell.get("share", 0.0)
        text_color = "black" if value < vmax * 0.6 else "white"
        ax.text(
            col,
            row,
            f"{value:.0f}%",
            ha="center",
            va="center",
            color=text_color,
            fontsize=7,
            fontweight="bold",
            clip_on=True,
        )

    cbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("Share of detections (%)")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def main() -> None:
    args = _parse_args()
    data = _load_stats(args.stats_path)
    buckets = data.get("buckets", {})
    bucket_minutes = int(data.get("bucket_minutes", 30))
    cutoff = None
    if args.recent_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=args.recent_days)
        cutoff = cutoff.replace(tzinfo=None)

    matrix, cell_info, time_labels, _ = _prepare_matrix(
        buckets,
        min_checks=args.min_checks,
        cutoff=cutoff,
        bucket_minutes=bucket_minutes,
    )

    if np.isnan(matrix).all():
        raise SystemExit("No data available with the provided filters")

    top_cells = _pick_top_cells(cell_info, args.top)
    _plot_heatmap(
        matrix,
        time_labels,
        top_cells,
        args.output,
        args.recent_days,
        args.min_checks,
        bucket_minutes,
        args.max_share,
        args.gamma,
    )

    print(f"Saved heatmap to {args.output}")
    if top_cells:
        print("Top hotspots:")
        for cell in top_cells:
            share = cell.get("share", 0.0)
            print(
                f"- {cell['weekday']} {cell['time']} — {cell['detections']}/{cell['checks']} checks, "
                f"{share:.2f}% of detections, last seen {cell['last_seen']}"
            )


if __name__ == "__main__":
    main()
