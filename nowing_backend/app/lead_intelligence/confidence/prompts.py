"""Prompt builders for the micro-extraction LLM fallback worker."""

from __future__ import annotations

import re
from typing import Any

from app.lead_intelligence.adapters.base import (
    _PHONE_TOKEN_PATTERN,
    NormalizedLead,
)

# Contact / word-number anchors used to locate ambiguous snippets.
_ANCHOR_RE = re.compile(
    r"\b(lh|liên hệ|sđt|số điện thoại|đt|alo|zalo|tel|phone|"
    r"không|chín|tám|một|hai|ba|bốn|năm|sáu|bảy)\b",
    re.IGNORECASE,
)

# Short, token-efficient prompts. Vietnamese is required for local listing text.
_SYSTEM_PROMPT = (
    "Trích xuất SĐT, giá, quận/huyện, diện tích từ đoạn tiếng Việt. Trả về JSON."
)

_MAX_SNIPPET_LEN = 250


def _extract_snippet(record: NormalizedLead) -> str:
    """Return the first 250-char window around a contact/word-number anchor."""
    parts = [
        record.raw_data.get("description") or "",
        record.address or "",
        record.title or "",
    ]
    text = " | ".join(p.strip() for p in parts if p.strip())
    if not text:
        return ""

    # Bound input to keep regex fast.
    bounded = text[:1000]
    for match in _ANCHOR_RE.finditer(bounded):
        start = max(0, match.start() - 40)
        end = min(len(bounded), match.end() + 210)
        snippet = bounded[start:end].strip()
        if len(snippet) > _MAX_SNIPPET_LEN:
            # Cut at the last space before the cap to avoid mid-token breaks.
            cut = snippet.rfind(" ", 0, _MAX_SNIPPET_LEN)
            snippet = (
                snippet[:cut] if cut > 0 else snippet[: _MAX_SNIPPET_LEN - 1] + "…"
            )
        return snippet
    return ""


def _mask_phone_numbers(text: str) -> str:
    """Replace any 10-11 digit Vietnamese phone pattern with ``[PHONE]``.

    Masking keeps the prompt in the public tier for ``HybridLLMRouter``; real
    digits are restored from ``primary_phone`` / ``raw_data`` after validation.
    """

    def _replacer(match: re.Match) -> str:
        return "[PHONE]"

    return _PHONE_TOKEN_PATTERN.sub(_replacer, text)


def build_prompt(record: NormalizedLead) -> str:
    """Build a single masked prompt for one record. Returns '' if no anchor."""
    snippet = _extract_snippet(record)
    if not snippet:
        return ""
    masked = _mask_phone_numbers(snippet)
    return f"{_SYSTEM_PROMPT}\nText: {masked}\nJSON:"


def build_batch_prompt(records: list[NormalizedLead]) -> tuple[str, list[int]]:
    """Build a masked prompt for a batch of records.

    Returns the combined prompt and the list of record indices that contributed
    a non-empty snippet (used to map the LLM response back to the records).
    """
    snippets: list[str] = []
    indices: list[int] = []
    for idx, record in enumerate(records):
        snippet = _extract_snippet(record)
        if snippet:
            masked = _mask_phone_numbers(snippet)
            snippets.append(f"[{idx}] {masked}")
            indices.append(idx)
    if not snippets:
        return "", []

    body = "\n".join(snippets)
    prompt = f"{_SYSTEM_PROMPT}\nCác đoạn:\n{body}\nTrả JSON theo index."
    return prompt, indices


def build_response_schema(batch_size: int = 1) -> dict[str, Any]:
    """Return a plain JSON Schema object for the micro-extraction result.

    For a single record the schema is a flat object. For a batch it is an
    object keyed by record index; this avoids ``json_object`` providers that
    struggle with top-level ``array`` schemas while still allowing one call
    per batch.
    """
    field_schema = {
        "type": "object",
        "properties": {
            "phone": {"type": "string"},
            "price": {"type": "number"},
            "district": {"type": "string"},
            "area": {"type": "number"},
            "title": {"type": "string"},
        },
        "required": [],
        "additionalProperties": False,
    }
    if batch_size == 1:
        return field_schema

    properties: dict[str, Any] = {}
    required: list[str] = []
    for i in range(batch_size):
        key = str(i)
        properties[key] = field_schema
        required.append(key)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
