#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
touch .monitor_paused
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Monitor disabled (created .monitor_paused)."

