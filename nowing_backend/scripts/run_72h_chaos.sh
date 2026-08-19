#!/usr/bin/env bash
# 72h Continuous Scraper Stress and Zombie/Leak Monitor (AC-2 / AD-108)
set -euo pipefail

DURATION_HOURS="${1:-72}"
INTERVAL_SEC="${2:-30}"
DURATION_SECONDS=$((DURATION_HOURS * 3600))

echo "Starting ${DURATION_HOURS}h Chaos Scraper Anti-Zombie monitor..."

python3 scripts/chaos_scraper_stress.py \
    --duration-seconds "$DURATION_SECONDS" \
    --interval-seconds "$INTERVAL_SEC" \
    --workers 8 \
    --zombie-log zombie_log.jsonl

echo "Completed ${DURATION_HOURS}h Chaos Scraper Monitor successfully."
