## Aachen Termin Bot — Operations & Alerts

### Realtime Monitoring (systemd timer)
- Runs every 5 minutes via `run_monitor.sh` (configured in `aachen-watch.timer`).
- Each run checks appointment availability and sends Matrix alerts according to throttling rules.

### Pause / Resume
- Pause (either method):
  - Create flag file: `touch .monitor_paused`
  - Or set `MONITOR_ENABLED=false` in `.env`
- Resume:
  - Remove flag: `rm .monitor_paused`
  - Or set `MONITOR_ENABLED=true` in `.env`

`run_monitor.sh` reads these before each run and skips execution when paused.

### One‑Click Start/Stop Scripts
- Enable monitoring: `./scripts/monitor-enable.sh`
- Disable monitoring: `./scripts/monitor-disable.sh`

### Alert Throttling & State Changes
- Sends immediately when availability transitions from none → some.
- If availability persists, sends at most once per X minutes (cooldown).
- Configurable via `.env` (defaults shown):
  - `ALERT_CHANGE_ONLY=true`
  - `ALERT_MIN_INTERVAL_MINUTES=60` (at most one alert per hour)
  - `ALERT_MIN_CONSECUTIVE_DETECTIONS=1`
  - `MONITOR_STATE_FILE=.monitor_state.json`

The state file lives at repo root; each monitor run reads/updates it to enforce change‑only and cooldown behavior.

### Matrix Configuration (example)
Put these in `.env` (replace placeholders):

```
# Realtime monitoring & throttling
MONITOR_ENABLED=true
ALERT_CHANGE_ONLY=true
ALERT_MIN_INTERVAL_MINUTES=60
ALERT_MIN_CONSECUTIVE_DETECTIONS=1
MONITOR_STATE_FILE=.monitor_state.json

# Business configuration
TERMIN_URL="https://termine.staedteregion-aachen.de/auslaenderamt/"
ANLIEGEN_TEXT="RWTH Mitarbeitende & Forschende bzw. PhD"
STANDORT_TEXT="Aachen Arkaden"

# Matrix
export MATRIX_HOMESERVER=https://your-homeserver
export MATRIX_ACCESS_TOKEN=your-access-token
export MATRIX_ROOM_ID=!room:your-homeserver
```

Note:
- `run_monitor.sh` sources `.env`, and Python also uses `python-dotenv`, so both `KEY=VALUE` and `export KEY=VALUE` styles work.

### Daily/Weekly Reports
- Daily summary at 04:30: `summarize_logs.py`
- Weekly hotspots (with heatmap) on Mondays at 05:00: `summarize_history.py`
These are independent from realtime monitoring; pausing monitoring does not affect the reports.

### Manual Run & Logs
- Manual one‑off check: `./run_monitor.sh`
- Tail recent log entries: `tail -n 100 cron.log`
- When throttled during persistent availability you will see: `Slots detected but throttled …`.

### systemd Timers
```
systemctl status aachen-watch.timer
systemctl status aachen-daily-summary.timer
systemctl status aachen-weekly-history.timer
```

### Hotspot Heatmap

Use `plot_hotspots.py` to render a weekday/time heatmap showing the share of detections per bucket:

```bash
# One‑time setup example
python3 -m venv .venv && .venv/bin/pip install matplotlib
source .venv/bin/activate

# Last 14 days
python plot_hotspots.py --recent-days 14 --output stats/hotspots_recent.png
# All data
python plot_hotspots.py --output stats/hotspots_all.png
```

Arguments:
- `--recent-days N`: include buckets whose last detection was within N days.
- `--min-checks`: ignore buckets with fewer checks than this threshold (default 10).
- `--top`: label the top N buckets in the figure (by detection share).
- `--max-share`: clamp color scale upper bound (e.g., 6 for 0–6%).
- `--gamma`: boost contrast for small shares (<1.0 increases boost).
- `--stats-path/--output`: override stats input or output path.
