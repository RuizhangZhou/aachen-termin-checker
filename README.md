### Hotspot heatmap

Use `plot_hotspots.py` to render a weekday/time heatmap that shows what percentage of all detections happened in each bucket:

```bash
# Activate the virtual environment (create it once via `python3 -m venv .venv && .venv/bin/pip install matplotlib`)
source .venv/bin/activate
python plot_hotspots.py --recent-days 14 --output stats/hotspots_recent.png
python plot_hotspots.py --output stats/hotspots_all.png
```

Arguments:
- `--recent-days N`: restrict the heatmap to buckets whose last detection happened within the last N days (default: use the entire stats file).
- `--min-checks`: ignore buckets with fewer checks than this threshold (default 10).
- `--top`: label the top N buckets in the figure (ranking is based on share of detections).
- `--max-share`: clamp the color scale to the given percentage; lowering the value highlights small differences (for example, 0–6%).
- `--gamma`: adjust how aggressively low percentages are brightened; values below 1.0 boost contrast for smaller buckets.
- `--stats-path/--output`: override the stats input path or the PNG output path.

The resulting PNG can be shared directly with end users so they immediately see the busiest windows.
