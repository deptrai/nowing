"""Web builder deploy utilities."""

from __future__ import annotations

import re
import uuid


def disambiguate_slug(
    base_slug: str,
    existing_slugs: set[str] | list[str],
    max_length: int = 63,
    max_attempts: int = 100_000,
) -> str:
    """Generate a collision-free, DNS-label-safe slug.

    The result is always <= ``max_length`` and has a bounded number of suffix
    attempts to avoid an infinite loop (P15).
    """
    existing = set(existing_slugs)
    # Sanitize and truncate base_slug to DNS label safe format
    cleaned = re.sub(r"[^a-z0-9-]", "-", base_slug.strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-") or "app"
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].strip("-") or "app"

    if cleaned not in existing:
        return cleaned

    # Base is in existing; strip any trailing numeric suffix before incrementing
    base_without_num = re.sub(r"-\d+$", "", cleaned).strip("-") or "app"
    for counter in range(1, max_attempts + 1):
        suffix = f"-{counter}"
        avail = max_length - len(suffix)
        candidate = f"{base_without_num[:avail].strip('-')}{suffix}"
        if candidate not in existing:
            return candidate

    # Collisions exhausted the numeric range; append a short random tail.
    tail = uuid.uuid4().hex[:6]
    base = base_without_num[: max_length - len(tail) - 1]
    return f"{base}-{tail}"


__all__ = ["disambiguate_slug"]
