"""Redact credentials from JSON provenance before it becomes OKF content.

Export is a trust boundary: ``document_metadata`` and ``Memory.source_input`` may
contain connector-specific JSON that carries keys like ``api_key`` or ``token``.
This module recursively redacts those values and common token-shaped strings
without mutating the database rows.
"""

from __future__ import annotations

import re
from typing import Any

# Substring match, case-insensitive.
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(api_key|token|secret|password|access_token|refresh_token|bearer|"
    r"authorization|credentials|private_key|client_secret)",
    re.IGNORECASE,
)

# Common token-bearing string patterns.
_TOKEN_PATTERN = re.compile(
    r"\b(?:sk-[a-zA-Z0-9_-]+|pat_[a-zA-Z0-9_-]+|nw_pat_[a-zA-Z0-9_-]+|"
    r"Bearer\s+[a-zA-Z0-9_\-\.]+)\b",
    re.IGNORECASE,
)

# Long hex-like secrets.
_HEX_SECRET_PATTERN = re.compile(r"\b[0-9a-fA-F]{20,}\b")

_REDACTED = "[REDACTED]"


def _redact_string(value: str) -> str:
    if _TOKEN_PATTERN.search(value) or _HEX_SECRET_PATTERN.search(value):
        return _REDACTED
    return value


def redact_secrets(value: Any) -> Any:
    """Recursively redact credentials and tokens from a JSON-like value.

    Redacts values for keys matching common secret names (case-insensitive,
    substring match) and string values matching common token patterns
    (``sk-...``, ``pat_...``, ``Bearer ...``, ``nw_pat_...``, and hex-like
    secrets of 20 or more characters). Returns a deep copy; the original value
    is left untouched.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if _SENSITIVE_KEY_PATTERN.search(str(key)):
                result[key] = _REDACTED
            else:
                result[key] = redact_secrets(item)
        return result
    # Fallback: leave unknown types as-is.
    return value


def redact_text(value: Any) -> Any:
    """Backward-compatible alias for :func:`redact_secrets`."""
    return redact_secrets(value)
