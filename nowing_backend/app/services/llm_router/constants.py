"""Shared constants and content helpers for LLM routing."""

from __future__ import annotations

import re
from typing import Any

# Special ID for Auto mode - uses router for load balancing
AUTO_MODE_ID = 0

_CONTEXT_OVERFLOW_PATTERNS = re.compile(
    r"(input tokens exceed|context.{0,20}(length|window|limit)|"
    r"maximum context length|token.{0,20}(limit|exceed)|"
    r"too many tokens|reduce the length)",
    re.IGNORECASE,
)

_UNIVERSAL_CONTENT_TYPES = {
    "text",
    "image_url",
    "input_audio",
    "refusal",
    "audio",
    "file",
}


def _is_context_overflow_error(exc: Exception) -> bool:
    """Check if a BadRequestError is actually a context window overflow."""
    return bool(_CONTEXT_OVERFLOW_PATTERNS.search(str(exc)))


def _sanitize_content(content: Any) -> Any:
    """Normalise a LangChain message ``content`` field so it is safe for any
    downstream provider (Azure, OpenAI, OpenRouter, etc.).

    * Strips provider-specific block types (e.g. ``thinking`` from
      reasoning models).
    * Removes text blocks with blank text (Bedrock rejects
      ``{"type":"text","text":""}``).
    * Converts bare strings inside a list to
      ``{"type": "text", "text": ...}`` objects (Azure rejects raw strings in
      a content array).
    * Collapses a single-text-block list to a plain string for maximum
      compatibility.
    """
    if not isinstance(content, list):
        return content

    filtered: list[dict] = []
    for block in content:
        if isinstance(block, str):
            if block:
                filtered.append({"type": "text", "text": block})
        elif isinstance(block, dict):
            block_type = block.get("type", "text")
            if block_type not in _UNIVERSAL_CONTENT_TYPES:
                continue
            # Drop blank text blocks. Anthropic rejects whitespace-only system
            # blocks ("text content blocks must contain non-whitespace text"),
            # so treat whitespace-only as empty rather than only "".
            if block_type == "text" and not str(block.get("text") or "").strip():
                continue
            filtered.append(block)

    if not filtered:
        return ""
    if len(filtered) == 1 and filtered[0].get("type") == "text":
        return filtered[0].get("text", "")
    return filtered


__all__ = ["AUTO_MODE_ID"]
