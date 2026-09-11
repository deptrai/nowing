"""Config domain: web_builder."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from app.config._helpers import (
    BASE_DIR,
    _env_int,
    _env_json,
)

logger = logging.getLogger(__name__)

# Instant web-app hosting / builder (Story 27.1) - See line 1808 for canonical definition

# Web Builder & 1-Click Hosting (Story 27.1 / AD-113 / AD-114)
HOSTING_BASE_DOMAIN = os.getenv("HOSTING_BASE_DOMAIN", "apps.nowing.net")
CNAME_INGRESS_HOST = os.getenv(
    "CNAME_INGRESS_HOST", "cname-ingress.apps.nowing.net"
)
FILE_STORAGE_LOCAL_PATH = os.getenv(
    "FILE_STORAGE_LOCAL_PATH",
    # Anchor the default to the project root so it is independent of the
    # worker process CWD (e.g. Celery vs. web server).
    str(BASE_DIR / ".local_object_store"),
)
WEB_BUILDER_ENABLED = os.getenv("WEB_BUILDER_ENABLED", "TRUE").upper() == "TRUE"
WEB_BUILDER_MAX_PROMPT_CHARS = max(
    1, _env_int("WEB_BUILDER_MAX_PROMPT_CHARS", 2000)
)
WEB_BUILDER_PUBLIC_APPS_PATH = os.getenv(
    "WEB_BUILDER_PUBLIC_APPS_PATH",
    f"{FILE_STORAGE_LOCAL_PATH}/web-apps",
)
# Small fixed platform fee for static-snapshot deploy (default $0 for Option A).
WEB_BUILDER_DEPLOY_COST_MICROS = max(
    0, _env_int("WEB_BUILDER_DEPLOY_COST_MICROS", 0)
)
WEB_BUILDER_BUILD_COST_MICROS = max(0, _env_int("WEB_BUILDER_BUILD_COST_MICROS", 0))
WEB_BUILDER_BUILD_TIMEOUT_SECONDS = max(
    10, _env_int("WEB_BUILDER_BUILD_TIMEOUT_SECONDS", 300)
)
WEB_BUILDER_MAX_CONCURRENT_BUILDS = max(
    1, _env_int("WEB_BUILDER_MAX_CONCURRENT_BUILDS", 3)
)
WEB_BUILDER_BUILD_NODE_VERSION = os.getenv("WEB_BUILDER_BUILD_NODE_VERSION", "20")
WEB_BUILDER_BUILD_NODE_IMAGE_DIGEST = os.getenv(
    "WEB_BUILDER_BUILD_NODE_IMAGE_DIGEST", ""
).strip()
WEB_BUILDER_DOCKER_SANDBOX_ENABLED = (
    os.getenv("WEB_BUILDER_DOCKER_SANDBOX_ENABLED", "FALSE").upper() == "TRUE"
)
WEB_BUILDER_CONTAINER_DEPLOY_ENABLED = (
    os.getenv("WEB_BUILDER_CONTAINER_DEPLOY_ENABLED", "FALSE").upper() == "TRUE"
)
WEB_BUILDER_DOKPLOY_NETWORK = os.getenv(
    "WEB_BUILDER_DOKPLOY_NETWORK", "dokploy-network"
)
# Opt-in tenant-vs-tenant isolation: each app gets its own bridge network
# named nowing-app-{workspace_id}-{app_id}-net so containers cannot reach
# each other by membership. Requires WEB_BUILDER_INGRESS_PROXY_CONTAINER to
# name the proxy container (e.g. dokploy-traefik) so the deploy path can
# `docker network connect` it into each app network (Story 31.1).
WEB_BUILDER_PER_APP_NETWORK = (
    os.getenv("WEB_BUILDER_PER_APP_NETWORK", "FALSE").upper() == "TRUE"
)
WEB_BUILDER_INGRESS_PROXY_CONTAINER = os.getenv(
    "WEB_BUILDER_INGRESS_PROXY_CONTAINER", ""
)

# Per-plan-tier cgroup limits for user web-app runtime containers (Story 31.1).
# This module is the single owner of the tier -> {memory, cpus, pids_limit}
# mapping used by WebAppDeployService.deploy_container. The three
# WEB_BUILDER_TIER_*_MAP env vars are JSON objects keyed by tier name and
# merge per-key over these code defaults, e.g.
#   WEB_BUILDER_TIER_CPUS_MAP={"growth": "1.5"}
# only overrides growth.cpus; every other tier/key keeps its default.
WEB_BUILDER_TIER_LIMITS: dict[str, dict[str, Any]] = {
    "free": {"memory": "256m", "cpus": "0.25", "pids_limit": 50},
    "team": {"memory": "512m", "cpus": "0.5", "pids_limit": 100},
    "growth": {"memory": "1024m", "cpus": "1.0", "pids_limit": 200},
    "enterprise": {"memory": "2048m", "cpus": "2.0", "pids_limit": 400},
}
# Import-time snapshot of the env override maps (re-read at call time by
# get_web_builder_tier_limits so tests/late env changes still apply).
WEB_BUILDER_TIER_MEMORY_MAP = _env_json("WEB_BUILDER_TIER_MEMORY_MAP", {}) or {}
WEB_BUILDER_TIER_CPUS_MAP = _env_json("WEB_BUILDER_TIER_CPUS_MAP", {}) or {}
WEB_BUILDER_TIER_PIDS_MAP = _env_json("WEB_BUILDER_TIER_PIDS_MAP", {}) or {}


def _tier_override_map(env_name: str, import_snapshot: dict) -> dict:
    """Return the per-tier override map for ``env_name``.

    The env var is re-read at call time so monkeypatched env in tests and
    runtime overrides apply without a module reload. Malformed JSON falls
    back to an empty map (code defaults win) and ``_env_json`` logs a
    warning naming the variable; non-object JSON is rejected the same way.
    When the env var is unset, the import-time snapshot is used so patching
    the module-level constant also works.
    """
    parsed = (
        import_snapshot
        if os.getenv(env_name) is None
        else _env_json(env_name, {})
    )
    if not isinstance(parsed, dict):
        logger.warning(
            "Ignoring %s: expected a JSON object keyed by tier name", env_name
        )
        return {}
    # Normalize keys so e.g. {"Growth": ...} hits the "growth" tier.
    return {str(key).strip().lower(): value for key, value in parsed.items()}


# docker run memory sizes always carry a unit suffix — a bare number is
# interpreted as bytes, which is almost certainly not what an operator meant.
_TIER_MEMORY_RE = re.compile(r"^\d+[bkmgBKMG]$")
# Kernel-side ceiling for --pids-limit; 0/-1 would disable the cap entirely.
_TIER_PIDS_MAX = 4194304


def _validate_tier_override(
    env_name: str, tier: str, key: str, raw: Any, default: Any
) -> Any:
    """Validate one env-map override value; warn + return default if invalid.

    - ``memory``: docker size with unit suffix, e.g. ``256m``/``1g``.
    - ``cpus``: positive float (``0.25``, ``1.5``); zero/negative rejected.
    - ``pids_limit``: int in ``1..4194304``; ``0``/``-1`` rejected (they
      disable the pids cap entirely).
    """
    if isinstance(raw, bool):
        pass  # JSON true/false is never a valid limit value
    elif key == "memory":
        if isinstance(raw, str) and _TIER_MEMORY_RE.fullmatch(raw.strip()):
            return raw.strip()
    elif key == "cpus":
        try:
            if float(raw) > 0:
                return str(raw).strip()
        except (TypeError, ValueError):
            pass
    elif key == "pids_limit":
        try:
            pids = int(raw)
            if 1 <= pids <= _TIER_PIDS_MAX:
                return pids
        except (TypeError, ValueError):
            pass
    logger.warning(
        "Invalid %s[%r]=%r; using default %r", env_name, tier, raw, default
    )
    return default


def get_web_builder_tier_limits(plan_tier: str | None) -> dict[str, Any]:
    """Resolve cgroup limits for a workspace plan tier.

    Normalizes ``(plan_tier or "free").strip().lower()`` — unknown/empty/None
    tiers fall back to ``free`` (same rule as workspace_limits.py). Env-map
    overrides apply per-key over the resolved tier's code defaults.

    Returns ``{"memory": str, "cpus": str, "pids_limit": int}`` ready to be
    interpolated into ``docker run --memory/--cpus/--pids-limit`` flags.
    """
    normalized = str(plan_tier or "").strip().lower()
    if normalized and normalized not in WEB_BUILDER_TIER_LIMITS:
        logger.warning(
            "Unknown plan_tier %r for web-builder container limits; "
            "falling back to 'free'",
            plan_tier,
        )
    tier = normalized if normalized in WEB_BUILDER_TIER_LIMITS else "free"
    defaults = WEB_BUILDER_TIER_LIMITS[tier]

    memory_map = _tier_override_map(
        "WEB_BUILDER_TIER_MEMORY_MAP", WEB_BUILDER_TIER_MEMORY_MAP
    )
    cpus_map = _tier_override_map(
        "WEB_BUILDER_TIER_CPUS_MAP", WEB_BUILDER_TIER_CPUS_MAP
    )
    pids_map = _tier_override_map(
        "WEB_BUILDER_TIER_PIDS_MAP", WEB_BUILDER_TIER_PIDS_MAP
    )

    return {
        "memory": _validate_tier_override(
            "WEB_BUILDER_TIER_MEMORY_MAP",
            tier,
            "memory",
            memory_map.get(tier, defaults["memory"]),
            defaults["memory"],
        ),
        "cpus": _validate_tier_override(
            "WEB_BUILDER_TIER_CPUS_MAP",
            tier,
            "cpus",
            cpus_map.get(tier, defaults["cpus"]),
            defaults["cpus"],
        ),
        "pids_limit": _validate_tier_override(
            "WEB_BUILDER_TIER_PIDS_MAP",
            tier,
            "pids_limit",
            pids_map.get(tier, defaults["pids_limit"]),
            defaults["pids_limit"],
        ),
    }


# Container healthcheck / lifecycle tuning.
WEB_BUILDER_CONTAINER_HEALTHCHECK_TIMEOUT = max(
    5, _env_int("WEB_BUILDER_CONTAINER_HEALTHCHECK_TIMEOUT", 60)
)
WEB_BUILDER_CONTAINER_HEALTHCHECK_RETRIES = max(
    1, _env_int("WEB_BUILDER_CONTAINER_HEALTHCHECK_RETRIES", 10)
)

# Self-host Caddy dynamic snippet config.
# Operators enable these for the Caddy 2 file-provider fallback (Story 27.1c).
WEB_BUILDER_CADDY_SNIPPETS_ENABLED = (
    os.getenv("WEB_BUILDER_CADDY_SNIPPETS_ENABLED", "FALSE").upper() == "TRUE"
)
WEB_BUILDER_CADDY_SNIPPETS_PATH = os.getenv(
    "WEB_BUILDER_CADDY_SNIPPETS_PATH",
    "docker/proxy/web-apps.Caddyfile",
)
WEB_BUILDER_CADDY_RELOAD_ENABLED = (
    os.getenv("WEB_BUILDER_CADDY_RELOAD_ENABLED", "FALSE").upper() == "TRUE"
)
WEB_BUILDER_CADDY_CONTAINER_NAME = os.getenv("WEB_BUILDER_CADDY_CONTAINER_NAME", "")
WEB_BUILDER_CADDY_BACKEND_TARGET = os.getenv(
    "WEB_BUILDER_CADDY_BACKEND_TARGET", "backend:8000"
)

# Health probe targets for optional infrastructure components.
# When unset, the probe reports "not_configured" instead of failing against localhost.
CADDY_ADMIN_URL = os.getenv("CADDY_ADMIN_URL", "")
ZERO_CACHE_KEEPALIVE_URL = os.getenv("ZERO_CACHE_KEEPALIVE_URL", "")

# Production Traefik label overrides.
WEB_BUILDER_TRAEFIK_ENTRYPOINT = os.getenv(
    "WEB_BUILDER_TRAEFIK_ENTRYPOINT", "websecure"
)
WEB_BUILDER_TRAEFIK_CERTRESOLVER = os.getenv(
    "WEB_BUILDER_TRAEFIK_CERTRESOLVER", "default"
)
WEB_BUILDER_TRAEFIK_USE_TLS = (
    os.getenv("WEB_BUILDER_TRAEFIK_USE_TLS", "TRUE").upper() == "TRUE"
)

# Reserved domain blacklist (comma-separated) in addition to the configured base domain.
WEB_BUILDER_DOMAIN_BLACKLIST = os.getenv("WEB_BUILDER_DOMAIN_BLACKLIST", "")

USE_DYNAMIC_SCRAPER_RULES = (
    os.getenv("USE_DYNAMIC_SCRAPER_RULES", "FALSE").upper() == "TRUE"
)

PRESENTATION_STUDIO_ENABLED = (
    os.getenv("PRESENTATION_STUDIO_ENABLED", "FALSE").upper() == "TRUE"
)
PRESENTATION_MAX_PROMPT_CHARS = max(
    1, _env_int("PRESENTATION_MAX_PROMPT_CHARS", 2000)
)
PRESENTATION_FILE_STORAGE_SUBDIR = os.getenv(
    "PRESENTATION_FILE_STORAGE_SUBDIR", "presentations"
)

MEETING_MINUTES_ENABLED = (
    os.getenv("MEETING_MINUTES_ENABLED", "FALSE").upper() == "TRUE"
)
MEETING_MINUTES_MAX_PROMPT_CHARS = max(
    1, _env_int("MEETING_MINUTES_MAX_PROMPT_CHARS", 2000)
)
MEETING_MINUTES_MAX_DURATION_SECONDS = max(
    1, _env_int("MEETING_MINUTES_MAX_DURATION_SECONDS", 600)
)
MEETING_MINUTES_TRANSCRIPTION_MICROS_PER_SECOND = max(
    0, _env_int("MEETING_MINUTES_TRANSCRIPTION_MICROS_PER_SECOND", 0)
)
MEETING_MINUTES_MAX_AUDIO_BYTES = max(
    1, _env_int("MEETING_MINUTES_MAX_AUDIO_BYTES", 100 * 1024 * 1024)
)
MEETING_MINUTES_DIARIZATION_ENGINE = os.getenv(
    "MEETING_MINUTES_DIARIZATION_ENGINE", "pyannote"
).lower()
MEETING_MINUTES_MAX_SPEAKER_LABELS = max(
    1, _env_int("MEETING_MINUTES_MAX_SPEAKER_LABELS", 10)
)
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN", "")

__all__ = ['CADDY_ADMIN_URL', 'CNAME_INGRESS_HOST', 'FILE_STORAGE_LOCAL_PATH', 'HOSTING_BASE_DOMAIN', 'HUGGINGFACE_TOKEN', 'MEETING_MINUTES_DIARIZATION_ENGINE', 'MEETING_MINUTES_ENABLED', 'MEETING_MINUTES_MAX_AUDIO_BYTES', 'MEETING_MINUTES_MAX_DURATION_SECONDS', 'MEETING_MINUTES_MAX_PROMPT_CHARS', 'MEETING_MINUTES_MAX_SPEAKER_LABELS', 'MEETING_MINUTES_TRANSCRIPTION_MICROS_PER_SECOND', 'PRESENTATION_FILE_STORAGE_SUBDIR', 'PRESENTATION_MAX_PROMPT_CHARS', 'PRESENTATION_STUDIO_ENABLED', 'USE_DYNAMIC_SCRAPER_RULES', 'WEB_BUILDER_BUILD_COST_MICROS', 'WEB_BUILDER_BUILD_NODE_IMAGE_DIGEST', 'WEB_BUILDER_BUILD_NODE_VERSION', 'WEB_BUILDER_BUILD_TIMEOUT_SECONDS', 'WEB_BUILDER_CADDY_BACKEND_TARGET', 'WEB_BUILDER_CADDY_CONTAINER_NAME', 'WEB_BUILDER_CADDY_RELOAD_ENABLED', 'WEB_BUILDER_CADDY_SNIPPETS_ENABLED', 'WEB_BUILDER_CADDY_SNIPPETS_PATH', 'WEB_BUILDER_CONTAINER_DEPLOY_ENABLED', 'WEB_BUILDER_CONTAINER_HEALTHCHECK_RETRIES', 'WEB_BUILDER_CONTAINER_HEALTHCHECK_TIMEOUT', 'WEB_BUILDER_DEPLOY_COST_MICROS', 'WEB_BUILDER_DOCKER_SANDBOX_ENABLED', 'WEB_BUILDER_DOKPLOY_NETWORK', 'WEB_BUILDER_DOMAIN_BLACKLIST', 'WEB_BUILDER_ENABLED', 'WEB_BUILDER_INGRESS_PROXY_CONTAINER', 'WEB_BUILDER_MAX_CONCURRENT_BUILDS', 'WEB_BUILDER_MAX_PROMPT_CHARS', 'WEB_BUILDER_PER_APP_NETWORK', 'WEB_BUILDER_PUBLIC_APPS_PATH', 'WEB_BUILDER_TIER_CPUS_MAP', 'WEB_BUILDER_TIER_LIMITS', 'WEB_BUILDER_TIER_MEMORY_MAP', 'WEB_BUILDER_TIER_PIDS_MAP', 'WEB_BUILDER_TRAEFIK_CERTRESOLVER', 'WEB_BUILDER_TRAEFIK_ENTRYPOINT', 'WEB_BUILDER_TRAEFIK_USE_TLS', 'ZERO_CACHE_KEEPALIVE_URL', 'get_web_builder_tier_limits']
