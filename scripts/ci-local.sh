#!/usr/bin/env bash
# Run the same core checks as the CI pipeline locally.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Backend lint"
cd nowing_backend
uv run ruff check .
uv run ruff format --check .

echo "==> Backend unit tests"
uv run pytest -m unit --tb=short

echo "==> Frontend lint"
cd ../nowing_web
pnpm install --frozen-lockfile
pnpm exec biome check . --diagnostic-level=error

echo "==> Frontend build"
pnpm build

echo "==> CI local checks passed"
