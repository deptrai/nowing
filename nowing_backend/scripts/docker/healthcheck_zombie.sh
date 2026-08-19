#!/bin/sh
# Docker container healthcheck for zombie / defunct processes (AC-2 / AD-107)
set -eu

ZOMBIE_COUNT=$(ps -eo stat | grep -E '^[[:space:]]*Z' | wc -l | tr -d ' ' || true)

if [ "$ZOMBIE_COUNT" -gt 0 ]; then
  echo "HEALTHCHECK FAILED: Detected $ZOMBIE_COUNT zombie processes in container" >&2
  exit 1
fi

echo "HEALTHCHECK OK: 0 zombie processes"
exit 0
