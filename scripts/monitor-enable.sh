#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
rm -f .monitor_paused || true
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Monitor enabled (removed .monitor_paused)."

