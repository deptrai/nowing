"""Deduplicate and merge Vietnamese company records from multiple sources."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any


def normalize(text: str | None) -> str:
    """Return a lowercase, NFKC-normalized, whitespace-collapsed string.

    Strips leading/trailing whitespace and removes punctuation so fingerprints
    stay stable across minor formatting differences.
    """
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


def fingerprint(raw_data: dict[str, Any]) -> str:
    """Stable canonical fingerprint for a company record.

    Uses the normalized tax code (MST) when available; falls back to a hash of
    the normalized name and address.
    """
    tax_code = raw_data.get("tax_code")
    if tax_code:
        normalized = tax_code.strip().replace(" ", "").replace("-", "")
        if normalized:
            return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    name = normalize(raw_data.get("name"))
    address = normalize(raw_data.get("address"))
    payload = f"{name}|{address}" if name or address else str(raw_data)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def search_text(raw_data: dict[str, Any]) -> str:
    """Return a single searchable text string for a company record."""
    keys = [
        "name",
        "tax_code",
        "address",
        "legal_representative",
        "status",
        "company_type",
        "main_industry",
        "managed_by",
    ]
    return " ".join(str(raw_data.get(k) or "") for k in keys).strip()


def merge(
    canonical: dict[str, Any] | Any,
    new_raw: dict[str, Any],
) -> dict[str, Any]:
    """Merge ``new_raw`` into ``canonical``.

    V1 pass-through: the newest record wins. Future multi-source company data
    can extend this with field-level conflict detection.
    """
    if not isinstance(canonical, dict):
        canonical = dict(new_raw)
    merged = dict(canonical)
    merged.update(new_raw)
    return merged
