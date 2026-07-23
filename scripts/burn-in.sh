#!/usr/bin/env bash
# Run backend unit tests N times to detect flakiness.
set -euo pipefail

ITERATIONS="${1:-10}"

cd "$(dirname "$0")/../nowing_backend"

echo "🔥 Burn-in: $ITERATIONS iterations"
for i in $(seq 1 "$ITERATIONS"); do
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "🔥 Iteration $i/$ITERATIONS"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  uv run pytest -m unit --tb=short
  echo "✅ Iteration $i passed"
done
echo "🎉 Burn-in complete"
