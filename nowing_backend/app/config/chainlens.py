"""Config domain: chainlens."""

from __future__ import annotations

import os

from app.config._helpers import (
    _env_float,
)

# ChainLens Research / Ingest integration (https://research-api.chainlens.net or local).
# CHAINLENS_SERVICE_TOKEN is the preferred service-to-service token for ingest.
# CHAINLENS_API_KEY is kept as a legacy alias for deep-research calls.
CHAINLENS_API_URL = os.getenv("CHAINLENS_API_URL", "http://localhost:3001").rstrip(
    "/"
)
CHAINLENS_SERVICE_TOKEN = os.getenv("CHAINLENS_SERVICE_TOKEN", "")
CHAINLENS_API_KEY = os.getenv("CHAINLENS_API_KEY", "")
# Local/self-host HMAC fast-path: when CHAINLENS_AUTH_CONTEXT_SECRET is set,
# Nowing signs an x-user-ctx header for the ChainLens HmacAuthGuard.  This
# lets local dev bypass Supabase/JWT auth and the QuotaGuard when the target
# ChainLens instance is configured with the same MCP_SERVICE_USER_ID.
CHAINLENS_AUTH_CONTEXT_SECRET = os.getenv("CHAINLENS_AUTH_CONTEXT_SECRET", "")
CHAINLENS_HMAC_USER_ID = os.getenv(
    "CHAINLENS_HMAC_USER_ID", "00000000-0000-0000-0000-000000000001"
)
CHAINLENS_REQUEST_TIMEOUT_SECONDS = float(
    os.getenv("CHAINLENS_REQUEST_TIMEOUT_SECONDS", "300")
)
# Fallback flat rate for deep-research calls that do not emit costDollars.
# Default is ~the average real cost observed in ChainLens benchmark 2026-08-02
# (report-per-mode.md: avg $0.0519; research balanced $0.0482, quality $0.0671).
# Override via env for a specific deployment/pricing model.
CHAINLENS_QUERY_MICROS_PER_CALL = int(
    os.getenv("CHAINLENS_QUERY_MICROS_PER_CALL", "60000")
)
# Margin applied to the engine-reported cost for self-host calls to cover
# full-pipeline overhead until ChainLens emits aggregated cost (Story 42-1b).
# Default 1.5x; billed_micros = floor(cost_micros * multiplier).
_self_host_multiplier = _env_float("SELF_HOST_RESEARCH_COST_MULTIPLIER", 1.5)
if _self_host_multiplier <= 0:
    _self_host_multiplier = 1.5
SELF_HOST_RESEARCH_COST_MULTIPLIER = _self_host_multiplier
# Scraper feed ingest settings.
CHAINLENS_INGEST_MAX_BATCH_SIZE = int(
    os.getenv("CHAINLENS_INGEST_MAX_BATCH_SIZE", "1000")
)
CHAINLENS_INGEST_TIMEOUT_SECONDS = float(
    os.getenv("CHAINLENS_INGEST_TIMEOUT_SECONDS", "5")
)
CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS = int(
    os.getenv("CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS", "3")
)
CHAINLENS_INGEST_RETRY_BACKOFF_SECONDS = float(
    os.getenv("CHAINLENS_INGEST_RETRY_BACKOFF_SECONDS", "1.0")
)



__all__ = ['CHAINLENS_API_KEY', 'CHAINLENS_API_URL', 'CHAINLENS_AUTH_CONTEXT_SECRET', 'CHAINLENS_HMAC_USER_ID', 'CHAINLENS_INGEST_MAX_BATCH_SIZE', 'CHAINLENS_INGEST_RETRY_BACKOFF_SECONDS', 'CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS', 'CHAINLENS_INGEST_TIMEOUT_SECONDS', 'CHAINLENS_QUERY_MICROS_PER_CALL', 'CHAINLENS_REQUEST_TIMEOUT_SECONDS', 'CHAINLENS_SERVICE_TOKEN', 'SELF_HOST_RESEARCH_COST_MULTIPLIER', '_self_host_multiplier']
