"""PII redaction helpers for canonical entity storage.

These helpers are the last line of defence before canonical data, source
snapshots, merge history, or outbox payloads are written. Domain aggregators
are still expected to redact their own output; this module ensures every
persistence path ends up PII-free regardless of caller.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.services.pii.redact import redact_job_pii

# Domain-specific PII keys that must not be stored verbatim.
_BDS_PII_KEYS = {
    "contact",
    "phone",
    "phone_key",
    "owner_phone",
    "seller_phone",
    "seller_name",
    "owner_name",
}

# A one-way digest may be retained when the field is needed for matching.
_BDS_DIGEST_KEYS = {"phone_key"}

_JOBS_PII_KEYS = {
    "job_description",
    "job_requirement",
    "contact",
    "email",
}


def _is_pii_key(key: str) -> bool:
    """Return True for known PII heuristics such as *phone* or *email*."""
    lower = key.lower()
    return "phone" in lower or "email" in lower


def _is_pii_field(entity_type: str, key: str) -> bool:
    """Return True if ``key`` is a PII field for the given entity type."""
    return (
        _is_pii_key(key)
        or (entity_type == "bds_listing" and key in _BDS_PII_KEYS)
        or (entity_type == "vn_job" and key in _JOBS_PII_KEYS)
    )


def _looks_like_digest(value: str) -> bool:
    """Keep the value untouched if it already looks like a sha256 hex digest."""
    if len(value) != 64:
        return False
    return all(c in "0123456789abcdef" for c in value.lower())


def _one_way_digest(value: str) -> str:
    """Return a one-way digest of ``value``.

    ponytail: plain sha256 keeps tests deterministic without adding a secret.
    If the value is already a sha256 hex string, keep it.
    """
    if _looks_like_digest(value):
        return value
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _redact_text_value(value: Any, entity_type: str, key: str) -> Any:
    """Redact a single scalar based on entity type and key name."""
    if entity_type == "bds_listing":
        if key in _BDS_DIGEST_KEYS and isinstance(value, str):
            return _one_way_digest(value)
        # Drop every other known PII key (including phone-number heuristics).
        return None

    if entity_type == "vn_job" and key in ("job_description", "job_requirement"):
        if isinstance(value, str):
            return redact_job_pii(value).text
        return None

    if key in _JOBS_PII_KEYS or _is_pii_key(key):
        return None

    return value


def _redact_value(value: Any, entity_type: str) -> Any:
    """Recursively redact PII from a JSON-like value."""
    if isinstance(value, dict):
        return _redact_dict(value, entity_type)
    if isinstance(value, list):
        return [_redact_value(item, entity_type) for item in value]
    return value


def _redact_dict(data: dict[str, Any], entity_type: str) -> dict[str, Any]:
    """Recursively redact PII keys from a dictionary."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if _is_pii_field(entity_type, key):
            redacted = _redact_text_value(value, entity_type, key)
            if redacted is not None:
                result[key] = redacted
        elif isinstance(value, dict):
            result[key] = _redact_dict(value, entity_type)
        elif isinstance(value, list):
            result[key] = [_redact_value(item, entity_type) for item in value]
        else:
            result[key] = value
    return result


def redact_canonical_data(entity_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Return a PII-redacted copy of ``data`` for canonical storage.

    For ``bds_listing`` structured PII fields are removed; ``phone_key`` is
    converted to a one-way digest because it is still required for matching.
    For ``vn_job`` ``job_description`` / ``job_requirement`` are masked using
    the AD-25 redactor; ``contact`` / ``email`` fields are removed.
    """
    if not isinstance(data, dict):
        return data
    return _redact_dict(dict(data), entity_type)


def redact_source_snapshot(
    entity_type: str, snapshot: dict[str, Any]
) -> dict[str, Any]:
    """Return a source snapshot that is safe for provenance storage.

    Source snapshots do not need matching keys, so even one-way digests of
    phone-derived fields are removed here. Canonical data keeps the digest.
    """
    if not isinstance(snapshot, dict):
        return snapshot
    redacted = redact_canonical_data(entity_type, snapshot)
    # ponytail: source provenance should retain no phone-derived keys at all;
    # address_key is also excluded because the snapshot is not used for matching.
    if entity_type == "bds_listing":
        for key in ("phone_key", "address_key"):
            redacted.pop(key, None)
    return redacted
