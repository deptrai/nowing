"""Config domain: etl."""

from __future__ import annotations

import os

# ETL Service
ETL_SERVICE = os.getenv("ETL_SERVICE")

if ETL_SERVICE == "UNSTRUCTURED":
    # Unstructured API Key
    UNSTRUCTURED_API_KEY = os.getenv("UNSTRUCTURED_API_KEY")

elif ETL_SERVICE == "LLAMACLOUD":
    LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")
    # Optional: Azure Document Intelligence accelerator for supported file types
    AZURE_DI_ENDPOINT = os.getenv("AZURE_DI_ENDPOINT")
    AZURE_DI_KEY = os.getenv("AZURE_DI_KEY")

# ETL parse cache: reuse parser output for identical bytes across workspaces.
ETL_CACHE_ENABLED = (
    os.getenv("ETL_CACHE_ENABLED", "false").strip().lower() == "true"
)
# Bump to invalidate every cached entry after a parser/behaviour change.
ETL_CACHE_PARSER_VERSION = int(os.getenv("ETL_CACHE_PARSER_VERSION", "1"))
ETL_CACHE_TTL_DAYS = int(os.getenv("ETL_CACHE_TTL_DAYS", "90"))
ETL_CACHE_MAX_TOTAL_MB = int(os.getenv("ETL_CACHE_MAX_TOTAL_MB", "5120"))
ETL_CACHE_EVICTION_BATCH = int(os.getenv("ETL_CACHE_EVICTION_BATCH", "500"))
# Optional dedicated blob storage; unset reuses the main file_storage backend.
ETL_CACHE_STORAGE_BACKEND = os.getenv("ETL_CACHE_STORAGE_BACKEND")
ETL_CACHE_STORAGE_CONTAINER = os.getenv("ETL_CACHE_STORAGE_CONTAINER")
ETL_CACHE_STORAGE_LOCAL_PATH = os.getenv("ETL_CACHE_STORAGE_LOCAL_PATH")

# Embedding cache: reuse chunk+embedding output for identical markdown across
# workspaces. Blobs share the ETL_CACHE_STORAGE_* backend.
EMBEDDING_CACHE_ENABLED = (
    os.getenv("EMBEDDING_CACHE_ENABLED", "false").strip().lower() == "true"
)
# Bump to invalidate every cached embedding set after a chunker change.
EMBEDDING_CACHE_CHUNKER_VERSION = int(
    os.getenv("EMBEDDING_CACHE_CHUNKER_VERSION", "1")
)
EMBEDDING_CACHE_TTL_DAYS = int(os.getenv("EMBEDDING_CACHE_TTL_DAYS", "90"))
EMBEDDING_CACHE_MAX_TOTAL_MB = int(
    os.getenv("EMBEDDING_CACHE_MAX_TOTAL_MB", "5120")
)
EMBEDDING_CACHE_EVICTION_BATCH = int(
    os.getenv("EMBEDDING_CACHE_EVICTION_BATCH", "500")
)

# Incremental re-indexing: on document edits, keep chunk rows whose text is
# unchanged (reusing their embeddings) and embed only new/changed chunks.
# Kill switch -- disabling falls back to delete-all + full re-embed.
CHUNK_RECONCILE_ENABLED = (
    os.getenv("CHUNK_RECONCILE_ENABLED", "true").strip().lower() == "true"
)
INDEXING_CHUNK_INSERT_BATCH_SIZE = int(
    os.getenv("INDEXING_CHUNK_INSERT_BATCH_SIZE", "200")
)

# Proxy provider selection. Maps to a ProxyProvider implementation registered
# in app/utils/proxy/registry.py. Add new vendors there and switch via this var.
PROXY_PROVIDER = os.getenv("PROXY_PROVIDER", "custom")

# Proxy endpoint(s), shared across all providers — PROXY_PROVIDER selects how
# they're interpreted, not a different env name. PROXY_URL is a single full
# http://user:pass@host:port endpoint (used by every provider); e.g. DataImpulse
# encodes country as a "__cr.<country>" username suffix that its provider parses
# for geoip-match. PROXY_URLS is a comma-separated pool that the "custom" provider
# rotates client-side (server-side-rotating gateways ignore it). Leave unset to
# disable proxying.
PROXY_URL = os.getenv("PROXY_URL")
PROXY_URLS = os.getenv("PROXY_URLS")

# =====================================================================
# Phase 3d — Captcha solving (reCAPTCHA v2/v3, hCaptcha, v2-Enterprise) via
# the in-house solver seam (app/utils/captcha/solvers.py).
# The LAST-resort bypass tier: only fires on the StealthyFetcher browser
# tier, only when a sitekey is detected, and only when explicitly enabled.
# Phase 3e — Stealth hardening (Slice A): runtime/config-level levers
# layered on Scrapling's patchright-Chromium StealthyFetcher tier. All are
# consumed by the centralized kwargs builder in
# app/proprietary/web_crawler/stealth.py (proprietary — bypass tuning), which
# is the single source of truth imported by the crawler AND the 03f harness
# (no test-vs-prod drift). Defaults preserve today's behavior /
# introduce no crawl-speed regression. See plans/backend/03e-stealth-hardening.md.
# =====================================================================
# Map the active proxy provider's exit region (ProxyProvider.get_location())
# -> browser locale/timezone so the fingerprint coheres with the proxy exit
# geo. No exit-IP lookup (zero added latency); unknown/empty region => skip.
CRAWL_GEOIP_MATCH_ENABLED = (
    os.getenv("CRAWL_GEOIP_MATCH_ENABLED", "FALSE").upper() == "TRUE"
)
# Force WebRTC to respect the proxy (prevents real-local-IP leak). Cheap +
# safe => default TRUE.
CRAWL_BLOCK_WEBRTC = os.getenv("CRAWL_BLOCK_WEBRTC", "TRUE").upper() == "TRUE"
# Random canvas noise. An UNSTABLE canvas hash is itself a fingerprint tell,
# so default FALSE (opt-in + 03f-validated). See 03e §2.
CRAWL_HIDE_CANVAS = os.getenv("CRAWL_HIDE_CANVAS", "FALSE").upper() == "TRUE"
# Set a Google referer so the first hit looks like organic arrival.
CRAWL_GOOGLE_SEARCH_REFERER = (
    os.getenv("CRAWL_GOOGLE_SEARCH_REFERER", "TRUE").upper() == "TRUE"
)
# Route DNS via Cloudflare DoH (anti DNS-leak behind proxies). Adds a DNS
# round-trip => default FALSE to honor the "no speed regression" bar; flip on
# when leak-safety outweighs the marginal latency.
CRAWL_DNS_OVER_HTTPS = os.getenv("CRAWL_DNS_OVER_HTTPS", "FALSE").upper() == "TRUE"
# Promises an Xvfb display so the browser can run headful (TikTok's profile
# feed is empty to headless Chromium). Off keeps every browser headless.
CRAWL_HEADED_XVFB_ENABLED = (
    os.getenv("CRAWL_HEADED_XVFB_ENABLED", "FALSE").upper() == "TRUE"
)



__all__ = ['CHUNK_RECONCILE_ENABLED', 'CRAWL_BLOCK_WEBRTC', 'CRAWL_DNS_OVER_HTTPS', 'CRAWL_GEOIP_MATCH_ENABLED', 'CRAWL_GOOGLE_SEARCH_REFERER', 'CRAWL_HEADED_XVFB_ENABLED', 'CRAWL_HIDE_CANVAS', 'EMBEDDING_CACHE_CHUNKER_VERSION', 'EMBEDDING_CACHE_ENABLED', 'EMBEDDING_CACHE_EVICTION_BATCH', 'EMBEDDING_CACHE_MAX_TOTAL_MB', 'EMBEDDING_CACHE_TTL_DAYS', 'ETL_CACHE_ENABLED', 'ETL_CACHE_EVICTION_BATCH', 'ETL_CACHE_MAX_TOTAL_MB', 'ETL_CACHE_PARSER_VERSION', 'ETL_CACHE_STORAGE_BACKEND', 'ETL_CACHE_STORAGE_CONTAINER', 'ETL_CACHE_STORAGE_LOCAL_PATH', 'ETL_CACHE_TTL_DAYS', 'ETL_SERVICE', 'INDEXING_CHUNK_INSERT_BATCH_SIZE', 'PROXY_PROVIDER', 'PROXY_URL', 'PROXY_URLS']
