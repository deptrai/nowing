#!/bin/bash
# Run E2E burn-in (N iterations) on changed or specified specs.
# Usage: ./scripts/burn-in.sh [iterations] [base-branch]
set -euo pipefail

ITERATIONS="${1:-5}"
BASE="${2:-main}"
CHANGED=$(git diff --name-only "origin/${BASE}...HEAD" | grep -E 'playwright/e2e/.*\.spec\.(ts|js)$' || true)

if [ -z "$CHANGED" ]; then
  echo "No changed E2E specs vs ${BASE} — nothing to burn in"
  exit 0
fi

echo "Running ${ITERATIONS}-iteration burn-in on:"
echo "$CHANGED"

for i in $(seq 1 "$ITERATIONS"); do
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Iteration $i/$ITERATIONS"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  # Security: CHANGED is derived from git diff output, not user input
  # shellcheck disable=SC2086
  pnpm exec playwright test $CHANGED --reporter=line || {
    echo "FAILED on iteration $i"
    exit 1
  }
done

echo "Burn-in complete — no flakiness detected"
