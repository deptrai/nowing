"""Canonical Action Matrix — dynamic dispatch catalog for XActions unified scrape.

Fetched live from the `x_actions_list` MCP tool with a TTL cache. When XActions
is unavailable or returns a partial catalog, the matrix falls back to a
conservative `STATIC_FALLBACK_MATRIX` covering only platforms that are known
to work today (per `PLATFORM_TOOL_MAP`).

Consumers call `await CanonicalActionMatrix.get(client)` for the live-refresh
path, or `CanonicalActionMatrix.get_sync()` when already inside a sync context
(the latter only ever returns the cache or the static fallback — it never
touches the network).
"""

from __future__ import annotations

import asyncio
import logging
import time
import weakref
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ActionDescriptor(BaseModel):
    """One entry returned by `x_actions_list`.

    Field names mirror the XActions descriptor schema (REQ-X3):
    ``platform``, ``action``, ``description``, ``requiredArgs``, ``optionalArgs``,
    ``example``, ``outputType``, ``requiresAuth``, plus the optional ``match``
    hint used to bind a Nowing ``target_kind`` suffix to the right action.
    """

    platform: str
    action: str
    description: str = ""
    requiredArgs: list[str] = Field(default_factory=list)
    optionalArgs: list[str] = Field(default_factory=list)
    example: dict[str, Any] = Field(default_factory=dict)
    outputType: str = ""
    requiresAuth: bool = False
    match: dict[str, Any] = Field(default_factory=dict)


# Static fallback matrix — conservative; only platforms that are known to work
# via `x_scrape` (or legacy tools) today. Action names here use the *canonical*
# XActions spelling (per REQ-X4) rather than the legacy mistakes still sitting
# in ``PLATFORM_TOOL_MAP``.
STATIC_FALLBACK_MATRIX: dict[str, dict[str, dict[str, Any]]] = {
    "tiktok": {
        "posts_by_hashtag": {
            "requiredArgs": ["hashtag"],
            "optionalArgs": ["limit"],
            "match": {"target_kind": "hashtag"},
        }
    },
    "chotot": {
        "search_listings": {
            "requiredArgs": ["category"],
            "optionalArgs": ["limit"],
            "match": {"target_kind": "category"},
        }
    },
    "shopee": {
        "search_products": {
            "requiredArgs": ["keyword"],
            "optionalArgs": ["limit"],
            "match": {"target_kind": "keyword"},
        }
    },
    "topcv": {
        "search_jobs": {
            "requiredArgs": ["query"],
            "optionalArgs": ["limit"],
            "match": {"target_kind": "search"},
        }
    },
    "vietnamworks": {
        "search_jobs": {
            "requiredArgs": ["query"],
            "optionalArgs": ["limit"],
            "match": {"target_kind": "search"},
        }
    },
    "linkedin": {
        "company_profile": {
            "requiredArgs": ["company"],
            "optionalArgs": [],
            "match": {"target_kind": "company"},
        }
    },
    "batdongsan": {
        "search_listings": {
            "requiredArgs": ["category"],
            "optionalArgs": ["limit"],
            "match": {"target_kind": "category"},
        }
    },
    "masothue": {
        "company_by_taxcode": {
            "requiredArgs": ["taxCode"],
            "optionalArgs": [],
            "match": {"target_kind": "lookup"},
        }
    },
    "b2b_registry": {
        "search": {
            "requiredArgs": ["query"],
            "optionalArgs": ["limit"],
            "match": {"target_kind": "search"},
        }
    },
    # facebook/twitter descriptors — routed through x_scrape when both
    # XACTIONS_USE_UNIFIED_DISPATCH and XACTIONS_LEGACY_TOOL_DEPRECATION are ON
    # (Story 36.6b), and for platform validation when unified dispatch is ON.
    "facebook": {
        "group_posts": {
            "requiredArgs": ["url"],
            "optionalArgs": ["limit"],
            "match": {"target_kind": "group"},
        },
        "page_posts": {
            "requiredArgs": ["url"],
            "optionalArgs": ["limit"],
            "match": {"target_kind": "page"},
        },
    },
    "twitter": {
        "search_tweets": {
            "requiredArgs": ["query"],
            "optionalArgs": ["limit"],
            "match": {"target_kind": "keyword"},
        },
        "user_tweets": {
            "requiredArgs": ["username"],
            "optionalArgs": ["limit"],
            "match": {"target_kind": "user"},
        },
    },
}


def parse_action_descriptors(raw: Any) -> dict[str, dict[str, dict[str, Any]]]:
    """Parse `x_actions_list` response into the canonical matrix shape.

    Accepts the MCP envelope dict ``{"actions": [...]}``, a plain list of
    descriptors, or a dict keyed by platform. Returns
    ``{platform: {action: descriptor_dict}}``.
    """
    if raw is None:
        return {}

    # Unwrap common envelopes.
    if isinstance(raw, dict):
        for key in ("actions", "data", "result", "descriptors"):
            if key in raw:
                raw = raw[key]
                break

    if isinstance(raw, dict):
        # Already keyed by platform — pass through nested dict.
        return {
            platform: dict(actions)
            for platform, actions in raw.items()
            if isinstance(actions, dict)
        }

    if not isinstance(raw, list):
        return {}

    matrix: dict[str, dict[str, dict[str, Any]]] = {}
    for entry in raw:
        try:
            desc = ActionDescriptor.model_validate(entry)
        except Exception:
            logger.warning("Skipping malformed ActionDescriptor: %r", entry)
            continue
        platform_map = matrix.setdefault(desc.platform, {})
        platform_map[desc.action] = desc.model_dump()
    return matrix


def _merge_with_static(live: dict[str, dict[str, dict[str, Any]]]) -> dict[str, dict[str, dict[str, Any]]]:
    """Merge a (possibly partial) live catalog with the static fallback.

    Live descriptors win on (platform, action) collisions; missing platforms
    are filled from ``STATIC_FALLBACK_MATRIX``. A live descriptor without a
    ``match`` hint inherits it from the static entry when available so
    ``target_kind`` derivation still works.
    """
    merged: dict[str, dict[str, dict[str, Any]]] = {}
    for platform, actions in STATIC_FALLBACK_MATRIX.items():
        merged[platform] = {action: dict(meta) for action, meta in actions.items()}

    for platform, actions in live.items():
        platform_map = merged.setdefault(platform, {})
        for action, meta in actions.items():
            meta = dict(meta)
            # Inherit match hint from static when live descriptor lacks one.
            if not meta.get("match"):
                static_match = (
                    STATIC_FALLBACK_MATRIX.get(platform, {}).get(action, {}).get("match")
                )
                if static_match:
                    meta["match"] = dict(static_match)
            platform_map[action] = meta
    return merged


class CanonicalActionMatrix:
    """TTL-cached registry of platform → action descriptors.

    ``get(client)`` refreshes the cache by calling ``x_actions_list`` via the
    provided MCP client, merging the result with ``STATIC_FALLBACK_MATRIX``.
    On fetch failure or empty catalog it serves the stale cache or the static
    matrix — never raises for the catalog path.
    """

    TTL_SECONDS: float = 300.0

    _cache: dict[str, dict[str, dict[str, Any]]] | None = None
    _cache_timestamp: float = 0.0
    _lock: asyncio.Lock | None = None
    _lock_loop_ref: weakref.ReferenceType | None = None

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        # Loop-scoped lock — a lock created inside one event loop cannot be
        # awaited from another (AD-5 / celery per-task loop rule). Rebind when
        # the running loop changes.
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if (
            cls._lock is None
            or cls._lock_loop_ref is None
            or cls._lock_loop_ref() is not current_loop
        ):
            cls._lock = asyncio.Lock()
            cls._lock_loop_ref = (
                weakref.ref(current_loop) if current_loop is not None else None
            )
        return cls._lock

    @classmethod
    def _is_cache_fresh(cls) -> bool:
        return (
            cls._cache is not None
            and (time.monotonic() - cls._cache_timestamp) < cls.TTL_SECONDS
        )

    @classmethod
    def get_sync(cls) -> dict[str, dict[str, dict[str, Any]]]:
        """Synchronous read — never touches the network.

        Returns the live cache if still fresh, otherwise the static fallback.
        """
        if cls._is_cache_fresh():
            assert cls._cache is not None
            return cls._cache
        return STATIC_FALLBACK_MATRIX

    @classmethod
    async def get(cls, client: Any | None = None) -> dict[str, dict[str, dict[str, Any]]]:
        """Async read — refresh via ``x_actions_list`` when cache is stale."""
        if cls._is_cache_fresh():
            assert cls._cache is not None
            return cls._cache

        if client is None:
            # No way to refresh — serve stale cache or fallback.
            if cls._cache is not None:
                return cls._cache
            return STATIC_FALLBACK_MATRIX

        async with cls._get_lock():
            # Re-check inside the lock — another caller may have refreshed.
            if cls._is_cache_fresh():
                assert cls._cache is not None
                return cls._cache

            try:
                raw = await client.call_tool("x_actions_list", {})
            except Exception as exc:
                logger.warning(
                    "x_actions_list fetch failed (%s); serving stale/static fallback",
                    exc,
                )
                if cls._cache is not None:
                    return cls._cache
                return STATIC_FALLBACK_MATRIX

            live = parse_action_descriptors(raw)
            if not live:
                logger.warning(
                    "x_actions_list returned empty catalog; serving stale/static fallback"
                )
                if cls._cache is not None:
                    return cls._cache
                return STATIC_FALLBACK_MATRIX

            merged = _merge_with_static(live)
            cls._cache = merged
            cls._cache_timestamp = time.monotonic()
            return merged

    @classmethod
    def reset(cls) -> None:
        """Test helper — drop the cache and lock state so next ``get`` refetches."""
        cls._cache = None
        cls._cache_timestamp = 0.0
        cls._lock = None
        cls._lock_loop_ref = None


def derive_platform_action(
    platform_kind: str,
    matrix: dict[str, dict[str, dict[str, Any]]],
) -> tuple[str, str]:
    """Resolve ``platform_kind`` (e.g. ``"tiktok_hashtag"``) → ``(platform, action)``.

    Splits on the last underscore to obtain a ``kind`` hint, then picks the
    action whose ``match.target_kind`` matches, falling back to the first
    declared action when there is exactly one. Raises ``ValueError`` for
    unsupported platforms or ambiguous kind-less matches.
    """
    if not platform_kind:
        raise ValueError("platform_kind is required")

    # Exact platform match (no kind suffix).
    if platform_kind in matrix:
        platform, kind = platform_kind, None
    elif "_" in platform_kind:
        platform, kind = platform_kind.rsplit("_", 1)
        if platform not in matrix:
            raise ValueError(f"Unsupported platform: {platform_kind}")
    else:
        raise ValueError(f"Unsupported platform: {platform_kind}")

    actions = matrix.get(platform) or {}
    if not actions:
        raise ValueError(f"Unsupported platform: {platform_kind}")

    if kind is None:
        if len(actions) == 1:
            return platform, next(iter(actions.keys()))
        raise ValueError(
            f"Ambiguous action for platform {platform} — expected {platform}_<kind>"
        )

    # Prefer actions whose match.target_kind equals the kind hint.
    for action, meta in actions.items():
        match = meta.get("match") or {}
        if match.get("target_kind") == kind:
            return platform, action

    # Fall back to a single-action platform.
    if len(actions) == 1:
        return platform, next(iter(actions.keys()))

    raise ValueError(
        f"Unsupported action kind '{kind}' for platform {platform} — "
        f"expected one of: {sorted({(m.get('match') or {}).get('target_kind') for m in actions.values()})}"
    )
