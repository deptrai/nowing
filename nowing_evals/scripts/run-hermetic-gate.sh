#!/usr/bin/env bash
# Runs the hermetic replay benchmark gate ($0 external cost, offline).
set -euo pipefail

export NOWING_JWT=dummy

echo "==> Ingesting lead extraction regression cases..."
uv run python -m nowing_evals ingest lead_extraction regression

echo "==> Running lead extraction replay regression benchmark..."
uv run python -m nowing_evals run lead_extraction regression --mode replay

echo "==> Generating benchmark summary report..."
uv run python -m nowing_evals report --suite lead_extraction

echo "==> Hermetic quality gate passed successfully!"
