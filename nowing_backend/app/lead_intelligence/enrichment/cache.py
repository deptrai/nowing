"""Redis result cache for contact enrichment (Story 21.3, AC-5).

Key scheme: ``enrichment:v1:{workspace_id}:{client_id}:{lead_id}``. A hit
returns the verified-contact ids for an already-enriched lead so repeat calls
skip the provider waterfall and billing. The cache is best-effort: any Redis
failure is treated as a miss and never degrades enrichment results.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

import redis

from app.config import config

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


def get_enrichment_cache_client() -> redis.Redis:
    """Get or create the Redis client used for enrichment result caching."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(config.REDIS_APP_URL, decode_responses=True)
    return _redis_client


def cache_key(
    workspace_id: int,
    client_id: str | None,  # pragma: no mutate
    lead_id: UUID,
) -> str:
    """Return the Redis key for an enriched lead (AC-5)."""
    client_part = f"client:{client_id}" if client_id else "global"
    return f"enrichment:v1:{workspace_id}:{client_part}:{lead_id}"


def get_cached_contact_ids(
    workspace_id: int,
    client_id: str | None,  # pragma: no mutate
    lead_id: UUID,
) -> list[UUID] | None:  # pragma: no mutate
    """Return cached verified-contact ids, or ``None`` on miss/error."""
    try:
        raw = get_enrichment_cache_client().get(
            cache_key(workspace_id, client_id, lead_id)
        )
        if not raw:
            return None
        ids = json.loads(raw)
        if not isinstance(ids, list):
            return None
        return [UUID(str(item)) for item in ids if item]
    except Exception as exc:  # pragma: no cover - cache is best-effort
        logger.warning("enrichment cache read failed: %s", exc)
        return None


def set_cached_contact_ids(
    workspace_id: int,
    client_id: str | None,  # pragma: no mutate
    lead_id: UUID,
    contact_ids: list[UUID],
    ttl_seconds: int | None = None,  # pragma: no mutate
) -> None:
    """Store verified-contact ids under the enrichment cache key (AC-5)."""
    try:
        get_enrichment_cache_client().set(
            cache_key(workspace_id, client_id, lead_id),
            json.dumps([str(item) for item in contact_ids]),
            ex=ttl_seconds or config.CONTACT_ENRICHMENT_CACHE_TTL_SECONDS,
        )
    except Exception as exc:  # pragma: no cover - cache is best-effort
        logger.warning("enrichment cache write failed: %s", exc)
