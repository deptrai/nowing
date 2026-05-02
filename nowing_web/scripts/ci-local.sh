#!/bin/bash
# Mirror CI environment locally for debugging.
# Requires: local backend on :8000 and frontend on :4998.
# Usage: ./scripts/ci-local.sh
set -euo pipefail

export BASE_URL="${BASE_URL:-http://localhost:4998}"
export API_URL="${API_URL:-http://localhost:8000}"
export CI="true"

echo "Running E2E tests in CI mode"
echo "  BASE_URL=${BASE_URL}"
echo "  API_URL=${API_URL}"
echo ""

pnpm exec playwright test --reporter=html,junit
