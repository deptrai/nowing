#!/usr/bin/env bash
# Run backend tests matching files changed against a base branch (default main).
set -euo pipefail

BASE_BRANCH="${1:-main}"
ITERATIONS="${2:-1}"

cd "$(dirname "$0")/../nowing_backend"

CHANGED=$(git diff --name-only "origin/${BASE_BRANCH}...HEAD" -- tests/ app/ | sed 's|^nowing_backend/||' | sort -u)
if [ -z "$CHANGED" ]; then
  echo "No changed backend test/source files."
  exit 0
fi

echo "Changed files:"
echo "$CHANGED" | sed 's/^/  - /'

for i in $(seq 1 "$ITERATIONS"); do
  echo "==> Run $i/$ITERATIONS"
  uv run pytest -m unit --tb=short -q $CHANGED
  echo "==> Run $i passed"
done
