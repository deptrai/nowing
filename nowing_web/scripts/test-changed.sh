#!/bin/bash
# Run E2E tests only for spec files changed vs a base branch.
# Usage: ./scripts/test-changed.sh [base-branch]
set -euo pipefail

BASE="${1:-main}"
CHANGED=$(git diff --name-only "origin/${BASE}...HEAD" | grep -E 'playwright/e2e/.*\.spec\.(ts|js)$' || true)

if [ -z "$CHANGED" ]; then
  echo "No E2E spec files changed vs ${BASE} — running full suite"
  pnpm exec playwright test
else
  echo "Changed specs:"
  echo "$CHANGED"
  # Security: CHANGED is derived from git diff output, not user input
  # shellcheck disable=SC2086
  pnpm exec playwright test $CHANGED
fi
