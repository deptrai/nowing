"""Config domain: entities."""

from __future__ import annotations

import os

from app.config._helpers import (
    _env_int,
)

# Canonical entity settings
CANONICAL_EMBEDDING_OUTBOX_FAILURE_THRESHOLD = _env_int(
    "CANONICAL_EMBEDDING_OUTBOX_FAILURE_THRESHOLD", 5
)

# Signal detection (Story 21.1)
SIGNAL_SCAN_MICROS_PER_SIGNAL = max(0, _env_int("SIGNAL_SCAN_MICROS_PER_SIGNAL", 0))
LEAD_SCORING_MICROS_PER_CALL = max(0, _env_int("LEAD_SCORING_MICROS_PER_CALL", 0))
CRUNCHBASE_API_KEY = os.getenv("CRUNCHBASE_API_KEY", "")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
SIGNAL_EXECUTIVE_MOVE_ENABLED = (
    os.getenv("SIGNAL_EXECUTIVE_MOVE_ENABLED", "FALSE").upper() == "TRUE"
)
SIGNAL_EVENT_RETENTION_DAYS = max(1, _env_int("SIGNAL_EVENT_RETENTION_DAYS", 90))

# Contact enrichment (Story 21.3)
CLEANLIST_API_KEY = os.getenv("CLEANLIST_API_KEY", "")
BETTERCONTACT_API_KEY = os.getenv("BETTERCONTACT_API_KEY", "")
CONTACT_ENRICHMENT_MICROS_PER_CONTACT = max(
    0, _env_int("CONTACT_ENRICHMENT_MICROS_PER_CONTACT", 0)
)
CONTACT_ENRICHMENT_CACHE_TTL_SECONDS = max(
    1, _env_int("CONTACT_ENRICHMENT_CACHE_TTL_SECONDS", 30 * 24 * 60 * 60)
)
CONTACT_ENRICHMENT_PRIMARY_PROVIDER = (
    os.getenv("CONTACT_ENRICHMENT_PRIMARY_PROVIDER", "cleanlist").strip().lower()
)
CONTACT_ENRICHMENT_MAX_CONTACTS_PER_LEAD = max(
    1, _env_int("CONTACT_ENRICHMENT_MAX_CONTACTS_PER_LEAD", 5)
)
CONTACT_ENRICHMENT_REQUEST_TIMEOUT_SECONDS = max(
    1, _env_int("CONTACT_ENRICHMENT_REQUEST_TIMEOUT_SECONDS", 30)
)
CONTACT_ENRICHMENT_RETRY_ATTEMPTS = max(
    1, _env_int("CONTACT_ENRICHMENT_RETRY_ATTEMPTS", 3)
)

# CRM (Story 21.5)
SALESFORCE_CLIENT_ID = os.getenv("SALESFORCE_CLIENT_ID", "")
SALESFORCE_CLIENT_SECRET = os.getenv("SALESFORCE_CLIENT_SECRET", "")
SALESFORCE_REDIRECT_URI = os.getenv("SALESFORCE_REDIRECT_URI", "")
SALESFORCE_WEBHOOK_SECRET = os.getenv("SALESFORCE_WEBHOOK_SECRET", "")
HUBSPOT_WEBHOOK_SECRET = os.getenv("HUBSPOT_WEBHOOK_SECRET", "")
HUBSPOT_CLIENT_ID = os.getenv("HUBSPOT_CLIENT_ID", "")
HUBSPOT_CLIENT_SECRET = os.getenv("HUBSPOT_CLIENT_SECRET", "")
HUBSPOT_REDIRECT_URI = os.getenv("HUBSPOT_REDIRECT_URI", "")
PIPEDRIVE_CLIENT_ID = os.getenv("PIPEDRIVE_CLIENT_ID", "")
PIPEDRIVE_CLIENT_SECRET = os.getenv("PIPEDRIVE_CLIENT_SECRET", "")
PIPEDRIVE_REDIRECT_URI = os.getenv("PIPEDRIVE_REDIRECT_URI", "")
CRM_SYNC_DEDUP_ENABLED = (
    os.getenv("CRM_SYNC_DEDUP_ENABLED", "TRUE").upper() == "TRUE"
)
CRM_SYNC_WRITEBACK_ENABLED = (
    os.getenv("CRM_SYNC_WRITEBACK_ENABLED", "FALSE").upper() == "TRUE"
)
CRM_SYNC_BIDIRECTIONAL_ENABLED = (
    os.getenv("CRM_SYNC_BIDIRECTIONAL_ENABLED", "FALSE").upper() == "TRUE"
)
CRM_SYNC_BATCH_SIZE = max(1, _env_int("CRM_SYNC_BATCH_SIZE", 50))
CRM_SYNC_TIMEOUT_SECONDS = max(1, _env_int("CRM_SYNC_TIMEOUT_SECONDS", 30))
CRM_SYNC_TOKEN_REFRESH_LEEWAY_SECONDS = max(
    0, _env_int("CRM_SYNC_TOKEN_REFRESH_LEEWAY_SECONDS", 300)
)
# Medirus social ingress (Story 21.8 / 21.8a)
MEDIRUS_PATH = os.getenv("MEDIRUS_PATH", "")
MEDIRUS_TIMEOUT_SECONDS = _env_int("MEDIRUS_TIMEOUT_SECONDS", 30)
MEDIRUS_MCP_URL = os.getenv("MEDIRUS_MCP_URL", "http://medirus:3001/mcp")
MEDIRUS_MCP_API_KEY = os.getenv("MEDIRUS_MCP_API_KEY", "")
MEDIRUS_CONSUMER_ID = os.getenv("MEDIRUS_CONSUMER_ID", "nowing")
MEDIRUS_ADMIN_TOKEN = os.getenv("MEDIRUS_ADMIN_TOKEN", "")
MEDIRUS_FACEBOOK_ACCOUNT_ID = os.getenv("MEDIRUS_FACEBOOK_ACCOUNT_ID", "")
# Deprecated: use MEDIRUS_FACEBOOK_ACCOUNT_ID (per-account pool)
MEDIRUS_FACEBOOK_C_USER = os.getenv("MEDIRUS_FACEBOOK_C_USER", "")
MEDIRUS_FACEBOOK_XS = os.getenv("MEDIRUS_FACEBOOK_XS", "")
# Transport: "streamable-http" (default) or "stdio" (legacy fallback)
MEDIRUS_TRANSPORT = os.getenv("MEDIRUS_TRANSPORT", "streamable-http").strip().lower()
# Mode: "local" (default, uses local browser pool) or "remote" (uses Medirus cloud API)
MEDIRUS_MODE = os.getenv("MEDIRUS_MODE", "local").strip().lower()
# Local root for resolving Medirus datasetArtifactPath (must be absolute)
MEDIRUS_ARTIFACT_ROOT = os.getenv("MEDIRUS_ARTIFACT_ROOT", "")
# Single-writer stream gate (Story 36.4 / AD-4)
MEDIRUS_STREAM_SINGLE_WRITER_ENABLED = (
    os.getenv("MEDIRUS_STREAM_SINGLE_WRITER_ENABLED", "false").strip().lower()
    in ("true", "1", "yes", "t", "on")
)
# Medirus stream data-plane Redis (Story 36.4 / REQ-X2). The single-writer
# social raw-posts stream (stream:social:raw_posts) lives on the Medirus-side
# Redis instance, which may differ from the app-level REDIS_APP_URL used for
# cache/queues. Leave empty to fall back to REDIS_APP_URL (same instance).
MEDIRUS_STREAM_REDIS_URL = os.getenv("MEDIRUS_STREAM_REDIS_URL", "").strip()
# Unified dispatch gate (Story 36.6a / AD-1, AD-2, AD-6)
# When ON: UniversalScrapeTargetMapper resolves platform+action from the
# CanonicalActionMatrix (medirus_list + static fallback) and dispatches
# medirus_scrape with the nested {platform, action, args, context} envelope.
# When OFF: legacy PLATFORM_TOOL_MAP path is used unchanged.
MEDIRUS_USE_UNIFIED_DISPATCH = (
    os.getenv("MEDIRUS_USE_UNIFIED_DISPATCH", "false").strip().lower()
    in ("true", "1", "yes", "t", "on")
)
# Legacy tool deprecation gate (Story 36.6b / AD-1, AD-2)
# When ON (and MEDIRUS_USE_UNIFIED_DISPATCH is also ON): UniversalScrapeTargetMapper
# routes facebook_group, facebook_page, twitter_keyword, twitter_user through
# medirus_scrape with the canonical matrix envelope instead of dedicated legacy tools.
# When OFF (or MEDIRUS_USE_UNIFIED_DISPATCH is OFF): legacy tool calls are preserved.
MEDIRUS_LEGACY_TOOL_DEPRECATION = (
    os.getenv("MEDIRUS_LEGACY_TOOL_DEPRECATION", "false").strip().lower()
    in ("true", "1", "yes", "t", "on")
)



__all__ = [
    "BETTERCONTACT_API_KEY",
    "CANONICAL_EMBEDDING_OUTBOX_FAILURE_THRESHOLD",
    "CLEANLIST_API_KEY",
    "CONTACT_ENRICHMENT_CACHE_TTL_SECONDS",
    "CONTACT_ENRICHMENT_MAX_CONTACTS_PER_LEAD",
    "CONTACT_ENRICHMENT_MICROS_PER_CONTACT",
    "CONTACT_ENRICHMENT_PRIMARY_PROVIDER",
    "CONTACT_ENRICHMENT_REQUEST_TIMEOUT_SECONDS",
    "CONTACT_ENRICHMENT_RETRY_ATTEMPTS",
    "CRM_SYNC_BATCH_SIZE",
    "CRM_SYNC_BIDIRECTIONAL_ENABLED",
    "CRM_SYNC_DEDUP_ENABLED",
    "CRM_SYNC_TIMEOUT_SECONDS",
    "CRM_SYNC_TOKEN_REFRESH_LEEWAY_SECONDS",
    "CRM_SYNC_WRITEBACK_ENABLED",
    "CRUNCHBASE_API_KEY",
    "HUBSPOT_CLIENT_ID",
    "HUBSPOT_CLIENT_SECRET",
    "HUBSPOT_REDIRECT_URI",
    "HUBSPOT_WEBHOOK_SECRET",
    "LEAD_SCORING_MICROS_PER_CALL",
    "MEDIRUS_ADMIN_TOKEN",
    "MEDIRUS_ARTIFACT_ROOT",
    "MEDIRUS_CONSUMER_ID",
    "MEDIRUS_FACEBOOK_ACCOUNT_ID",
    "MEDIRUS_FACEBOOK_C_USER",
    "MEDIRUS_FACEBOOK_XS",
    "MEDIRUS_LEGACY_TOOL_DEPRECATION",
    "MEDIRUS_MCP_API_KEY",
    "MEDIRUS_MCP_URL",
    "MEDIRUS_MODE",
    "MEDIRUS_PATH",
    "MEDIRUS_STREAM_REDIS_URL",
    "MEDIRUS_STREAM_SINGLE_WRITER_ENABLED",
    "MEDIRUS_TIMEOUT_SECONDS",
    "MEDIRUS_TRANSPORT",
    "MEDIRUS_USE_UNIFIED_DISPATCH",
    "NEWSAPI_KEY",
    "PIPEDRIVE_CLIENT_ID",
    "PIPEDRIVE_CLIENT_SECRET",
    "PIPEDRIVE_REDIRECT_URI",
    "SALESFORCE_CLIENT_ID",
    "SALESFORCE_CLIENT_SECRET",
    "SALESFORCE_REDIRECT_URI",
    "SALESFORCE_WEBHOOK_SECRET",
    "SIGNAL_EVENT_RETENTION_DAYS",
    "SIGNAL_EXECUTIVE_MOVE_ENABLED",
    "SIGNAL_SCAN_MICROS_PER_SIGNAL",
]
